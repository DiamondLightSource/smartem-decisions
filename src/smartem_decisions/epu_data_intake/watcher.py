#!/usr/bin/env python

from pprint import pprint

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from datetime import datetime
import logging
from pathlib import Path
import os
import re
import json
from fnmatch import fnmatch
import typer
from rich.console import Console
import signal
import platform

from data_model import EpuSession, MicrographData, GridSquareData
from fs_parser import EpuParser


"""Default glob patterns for EPU data files.

A list of patterns that match the standard EPU file structure for cryo-EM data
collection, including session files, grid squares, foil holes, and atlas images.

Patterns match the following files:
* Main EPU session file
* Grid square metadata files
* Grid square image XML files
* Foil hole data XML files
* Foil hole location XML files
* Atlas overview files
* Sample metadata files

:type: list[str]
"""
DEFAULT_PATTERNS = [
    "EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
    "Sample*/Sample.dm",
]


console = Console()


class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            log_entry = record.msg
        else:
            log_entry = {
                "message": record.msg,
                "level": record.levelname,
                "timestamp": datetime.now().isoformat()
            }
        return json.dumps(log_entry, indent=2)


class RateLimitedHandler(FileSystemEventHandler):
    def __init__(self, patterns: list[str], log_interval: float = 10.0, verbose: bool = False):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.patterns = patterns
        self.verbose = verbose
        # These events should reliably indicate file writes across both Windows and Linux when using watchdog:
        self.watched_event_types = ["created", "modified"]
        # Distinguish between new and previously seen files.
        # TODO See if this has any benefit or if same can same be achieved through "created" / "modified" file status
        self.changed_files = {}
        self.watch_dir = None

        self.gridsquare_dm_file_pattern = re.compile(r"GridSquare_(\d+)\.dm$") # under "Metadata/"
        self.gridsquare_dir_pattern = re.compile(r"GridSquare_(\d+)$") # under Images-Disc*/
        self.foilhole_xml_file_pattern = re.compile(r'FoilHole_(\d+)_(\d+)_(\d+)\.xml$')
        self.micrograph_xml_file_pattern = re.compile(r'FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$')


    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = str(Path(path).relative_to(self.watch_dir))
            rel_path = rel_path.replace('\\', '/')  # Normalize path separators
            return any(fnmatch(rel_path, pattern) for pattern in self.patterns)
        except ValueError:
            return False


    def set_watch_dir(self, path: Path):
        self.watch_dir = path.absolute()
        self._init_acquisition()


    def _init_acquisition(self):
        self.acquisition = EpuSession(
            EpuParser.resolve_project_dir(self.watch_dir),
            EpuParser.resolve_atlas_dir(self.watch_dir),
        )


    def on_any_event(self, event):
        # Enhancement: record all events to graylog (if reachable) for session debugging and playback

        if event.is_directory or not self.matches_pattern(event.src_path):
            if self.verbose and not event.is_directory:
                console.print(f"[dim]Skipping non-matching path: {event.src_path}[/dim]")
            return

        if event.event_type not in self.watched_event_types:
            if self.verbose and not event.is_directory:
                console.print(f"[dim]Skipping non-matching event type: {event.event_type}[/dim]")
            return

        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval:
            self._flush_events()

        file_stat = None
        try:
            if os.path.exists(event.src_path):
                file_stat = os.stat(event.src_path)
        except (FileNotFoundError, PermissionError) as e:
            if self.verbose:
                console.print(f"[yellow]Warning:[/yellow] {str(e)}")

        # if not new_file_detected - `event.modified` and `event.size` could be a good indicator if
        # any interesting changes happened
        new_file_detected = event.src_path in self.changed_files

        self.changed_files[event.src_path] = (event, current_time, file_stat)

        match event.src_path:
            case path if path.endswith("EpuSession.dm"):
                # Needs testing to see if this is a practical way to detect session start or if there's an
                #   alternative / additional way, e.g. appearance of a project dir
                self._on_session_detected(path) if new_file_detected else self._on_session_updated(path)
            case path if path.endswith("Sample.dm"):
                self._on_sample_detected(path) if new_file_detected else self._on_sample_updated(path)
            case path if path.endswith("Atlas/Atlas.dm"):
                self._on_atlas_detected(path) if new_file_detected else self._on_atlas_updated(path)
            case path if re.match(r".*/GridSquare_[^/]*\.dm$", path):
                self._on_gridsquare_detected(path) if new_file_detected else self._on_gridsquare_updated(path)
            case path if re.match(r".*/FoilHole_[^/]*_[^/]*_[^/]*\.xml$", path):
                # TODO between multiple files relating to the same foilhole keep latest one as encoded by timestamp in filename,
                #   e.g. between `FoilHole_9016620_20250108_181906.xml` and `FoilHole_9016620_20250108_181916.xml` pick the latter.
                self._on_foilhole_detected(path) if new_file_detected else self._on_foilhole_updated(path)
            case path if re.match(r".*/FoilHole_[^/]*_Data_[^/]*_[^/]*_[^/]*_[^/]*\.xml$", path):
                self._on_micrograph_detected(path) if new_file_detected else self._on_micrograph_updated(path)


    def _on_session_detected(self, path: str):
        print(f"Session detected: {path}")
        data = EpuParser.parse_epu_session_manifest(path)
        pprint(data)
        self.acquisition.session_data = data


    def _on_session_updated(self, path: str):
        print(f"Session updated: {path}")
        new_data = EpuParser.parse_epu_session_manifest(path)
        pprint(new_data)
        if self.acquisition.session_data != new_data:
            self.acquisition.session_data = new_data


    def _on_sample_detected(self, path: str):
        print(f"Sample detected: {path}")
        # though we're not yet sure if there's anything interesting there we might want


    def _on_sample_updated(self, path: str):
        print(f"Sample updated: {path}")
        # though we're not yet sure if there's anything interesting there we might want


    def _on_atlas_detected(self, path: str):
        print(f"Atlas detected: {path}")
        manifest = EpuParser.parse_atlas_manifest(path)
        pprint(manifest)


    def _on_atlas_updated(self, path: str):
        print(f"Atlas updated: {path}")
        manifest = EpuParser.parse_atlas_manifest(path)
        pprint(manifest)


    def _on_gridsquare_detected(self, path: str):
        print(f"Gridsquare detected: {path}")
        match = self.gridsquare_dm_file_pattern.search(path) # get Gridsquare ID from filename
        gridsquare_id = match.group(1)
        gridsquare_manifest = EpuParser.parse_gridsquare_manifest(path)
        gridsquare_data = GridSquareData(
            id=gridsquare_id,
            is_active=False,
            manifest=gridsquare_manifest,
        )
        pprint(gridsquare_data)
        self.acquisition.gridsquares.add(gridsquare_id, gridsquare_data)


    def _on_gridsquare_updated(self, path: str):
        print(f"Gridsquare updated: {path}")
        manifest = EpuParser.parse_gridsquare_manifest(path)
        pprint(manifest)


    def _on_foilhole_detected(self, path: str):
        print(f"Foilhole detected: {path}")
        data = EpuParser.parse_foilhole_manifest(path)
        pprint(data)
        self.acquisition.foilholes.add(data.id, data)


    # def scan_foilholes(self, gridsquare_id: str, gridsquare_dir: Path):
    # # Check for required subdirectories
    # gridsquare_data_dir = gridsquare_dir / "Data"
    # gridsquare_foilholes_dir = gridsquare_dir / "FoilHoles"
    # if not gridsquare_data_dir.is_dir():
    #     return
    # if not gridsquare_foilholes_dir.is_dir():
    #     return
    #
    # # Scan `/FoilHoles` directory for initial foilhole metadata
    # # OLDTODO grab timestamp from the filename?
    # foilhole_pattern = re.compile(r'FoilHole_(\d+)_(\d+)_(\d+)\.xml$')
    # for xml_file in gridsquare_foilholes_dir.glob("*.xml"):
    #     match = foilhole_pattern.search(xml_file.name)
    #     if match:
    #         foilhole_id = match.group(1)
    #         if foilhole_id not in self.foilholes:
    #             self.foilholes[foilhole_id] = FoilHoleData(
    #                 id = foilhole_id,
    #                 gridsquare_id = gridsquare_id,
    #                 files = {"foilholes_dir": [], "data_dir": [],}
    #             )
    #         self.foilholes[foilhole_id].files["foilholes_dir"].append(xml_file.name)
    #
    #
    # # Scan `/Data` directory for detailed acquisition data
    # # OLD
    # data_pattern = re.compile(r'FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$')
    # for xml_file in gridsquare_data_dir.glob("*.xml"):
    #     match = data_pattern.search(xml_file.name)
    #     if match:
    #         foilhole_id = match.group(1)
    #         if foilhole_id not in self.foilholes:
    #             self.foilholes[foilhole_id] = FoilHoleData(
    #                 id=foilhole_id,
    #                 gridsquare_id=gridsquare_id,
    #                 files={"foilholes_dir": [], "data_dir": [], }
    #             )
    #         self.foilholes[foilhole_id].files["data_dir"].append(xml_file.name)
    #         self.scan_micrographs(gridsquare_id, foilhole_id)


    def _on_foilhole_updated(self, path: str):
        print(f"Foilhole updated: {path}")
        manifest = EpuParser.parse_foilhole_manifest(path)
        pprint(manifest)


    def _on_micrograph_detected(self, path: str):
        print(f"Micrograph detected: {path}")

        match = re.match(r"FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+).xml$", path)
        foilhole_id = match.group(1)
        location_id = match.group(2)

        manifest = EpuParser.parse_micrograph_manifest(path)

        data = MicrographData(
            id="", # TODO
            location_id=location_id,
            gridsquare_id="", # TODO
            high_res_path=Path(""), # TODO
            foilhole_id = foilhole_id,
            manifest_file = Path(path),
            manifest = manifest,
        )
        pprint(data)
        self.acquisition.micrographs.add(data.id, data)

    # def scan_micrographs(self, gridsquare_id: str, foilhole_id: str):
    # # there is one file in data_dir per micrograph, so the unique combinations of foil hole and position in foil hole
    # micrograph_manifest_paths = list(
    #     self.project_dir.glob(
    #         f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_{foilhole_id}_Data_*_*_*_*.xml"
    #     )
    # )
    # for micrograph_path in micrograph_manifest_paths:
    #     micrograph_id, micrograph_manifest = self.parse_micrograph_manifest(micrograph_path)
    #     self.micrographs[micrograph_id] = MicrographData(
    #         id = micrograph_id,
    #         gridsquare_id = gridsquare_id,
    #         foilhole_id = foilhole_id,
    #         manifest_file = micrograph_path,
    #         manifest = micrograph_manifest,
    #     )


    def _on_micrograph_updated(self, path: str):
        print(f"Micrograph updated: {path}")
        manifest = EpuParser.parse_micrograph_manifest(path)
        pprint(manifest)


    def _on_session_complete(self):
        """
        TODO: explore how we might reliably determine when session ended
            (and bear in mind that it could have been paused, to be resumed later)?
        """
        pass


    def _flush_events(self):
        if not self.changed_files:
            return

        batch_log = {
            "timestamp": datetime.now().isoformat(),
            "event_count": len(self.changed_files),
            "events": []
        }

        for src_path, (event, event_time, file_stat) in self.changed_files.items():
            event_data = {
                "timestamp": datetime.fromtimestamp(event_time).isoformat(),
                "event_type": event.event_type,
                "source_path": str(src_path),
                "relative_path": str(Path(src_path).relative_to(self.watch_dir)).replace('\\', '/')
            }

            if file_stat:
                event_data.update({
                    "size": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })

            if hasattr(event, 'dest_path') and event.dest_path:
                event_data["destination_path"] = str(event.dest_path)
                try:
                    if os.path.exists(event.dest_path):
                        event_data["destination_size"] = os.path.getsize(event.dest_path)
                except OSError:
                    pass

            batch_log["events"].append(event_data)

        logging.info(batch_log)
        self.changed_files.clear()
        self.last_log_time = time.time()


def setup_logging(log_file: str | None, verbose: bool):
    json_formatter = JSONFormatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if not verbose else logging.DEBUG)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)


def watch_directory(
        path: Path = typer.Argument(..., help="Directory to watch"),
        patterns: list[str] = typer.Option(
            DEFAULT_PATTERNS,
            "--pattern", "-p",
            help="File patterns to watch (can be specified multiple times)"
        ),
        log_file: str | None = typer.Option(
            "fs_changes.log",
            "--log-file", "-l",
            help="Log file path (optional)"
        ),
        log_interval: float = typer.Option(
            10.0,
            "--interval", "-i",
            help="Minimum interval between log entries in seconds"
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose", "-v",
            help="Enable verbose output"
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run", "-d",
            help="Print matching patterns without watching"
        )
):
    """
    Watch directory for file changes and log them in JSON format.
    Supports Windows/Cygwin environments.
    """
    path = Path(path).absolute()
    if not path.exists():
        console.print(f"[red]Error:[/red] Directory {path} does not exist")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[blue]Would watch directory:[/blue] {path}")
        console.print("\n[blue]Using patterns:[/blue]")
        for pattern in patterns:
            console.print(f"  {pattern}")
        return

    setup_logging(log_file, verbose)

    logging.info({
        "message": f"Starting to watch directory: {str(path)} (including subdirectories)",
        "path": str(path),
        "patterns": patterns,
        "timestamp": datetime.now().isoformat()
    })

    observer = Observer()
    handler = RateLimitedHandler(patterns, log_interval, verbose)
    handler.set_watch_dir(path)
    observer.schedule(handler, str(path), recursive=True)

    def handle_exit(signum, frame):
        nonlocal handler
        console.print(handler.acquisition)
        observer.stop()
        # logging.info({
        #     "message": "Watching stopped",
        #     "timestamp": datetime.now().isoformat()
        # }) # TODO consider adding stack frame info: `frame`
        observer.join()
        raise typer.Exit()

    # Handle both CTRL+C and Windows signals
    signal.signal(signal.SIGINT, handle_exit)
    if platform.system() == 'Windows':
        signal.signal(signal.SIGBREAK, handle_exit)

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_exit(None, None)


if __name__ == "__main__":
    typer.run(watch_directory)
