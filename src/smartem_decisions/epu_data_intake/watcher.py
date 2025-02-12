#!/usr/bin/env python

import json
import logging
import os
import platform
import re
import signal
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from pprint import pprint

from rich.console import Console
import typer
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from data_model import (
    EpuSession,
    GridSquareData,
    GridSquareMetadata,
    MicrographData,
)
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
    """File system event handler with rate limiting capabilities.

    This handler processes file system events from watchdog, specifically watching
    for file creation and modification events. The implementation ensures reliable
    file write detection across both Windows and Linux platforms.

    :cvar watched_event_types: List of event types to monitor
    :type watched_event_types: list[str]
    :ivar acquisition: EPU session data store handler
    :type acquisition: EpuSession | None
    :ivar watch_dir: Directory path being monitored for changes
    :type watch_dir: Path | None
    :ivar last_log_time: Timestamp of the last logging event
    :type last_log_time: float
    :ivar log_interval: Minimum time between logging events in seconds
    :type log_interval: float
    :ivar patterns: List of file patterns to watch for
    :type patterns: list[str]
    :ivar verbose: Enable detailed logging output
    :type verbose: bool
    :ivar changed_files: Dictionary tracking file modification states
    :type changed_files: dict
    :ivar gridsquare_dm_file_pattern: Regex for matching GridSquare DM files
    :type gridsquare_dm_file_pattern: Pattern[str]
    :ivar gridsquare_dir_pattern: Regex for matching GridSquare directories
    :type gridsquare_dir_pattern: Pattern[str]
    :ivar foilhole_xml_file_pattern: Regex for matching FoilHole XML files
    :type foilhole_xml_file_pattern: Pattern[str]
    :ivar micrograph_xml_file_pattern: Regex for matching Micrograph XML files
    :type micrograph_xml_file_pattern: Pattern[str]
    """

    watched_event_types = ["created", "modified"]
    datastore: EpuSession | None = None
    watch_dir: Path | None = None

    def __init__(self, patterns: list[str], log_interval: float = 10.0, verbose: bool = False):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.patterns = patterns
        self.verbose = verbose

        # Distinguish between new and previously seen files.
        # TODO See if this has any benefit or if same can same be achieved through "created" / "modified" file status
        self.changed_files = {}

        self.gridsquare_dm_file_pattern = re.compile(r"GridSquare_(\d+)\.dm$")  # under "Metadata/"
        self.gridsquare_dir_pattern = re.compile(r"/GridSquare_(\d+)/")  # under Images-Disc*/
        self.foilhole_xml_file_pattern = re.compile(r'/FoilHole_(\d+)_(\d+)_(\d+)\.xml$')
        self.micrograph_xml_file_pattern = re.compile(r'/FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$')

    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = str(Path(path).relative_to(self.watch_dir))
            rel_path = rel_path.replace('\\', '/')  # Normalize path separators
            return any(fnmatch(rel_path, pattern) for pattern in self.patterns)
        except ValueError:
            return False


    def set_watch_dir(self, path: Path):
        self.watch_dir = path.absolute()


    def init_datastore(self):
        self.datastore = EpuSession(
            EpuParser.resolve_project_dir(self.watch_dir),
            EpuParser.resolve_atlas_dir(self.watch_dir),
        )

    # TODO this method does not logically belong to `watcher` but is coupled to it by shared datastore - refactor
    def scan_existing_content(self):
        if self.watch_dir is None:
            raise RuntimeError("watch_dir not initialized - call set_watch_dir() first")
        if self.datastore is None:
            raise RuntimeError("datastore not initialized - call init_datastore() first")

        # 1. locate and parse EpuSession.dm
        epu_manifest_paths = list( # TODO yes - it's possible to have more than one. problem for later
            self.datastore.project_dir.glob(f"EpuSession.dm")
        )
        if len(epu_manifest_paths) > 0:
            self.datastore.session_data = EpuParser.parse_epu_session_manifest(epu_manifest_paths[0])
        else:
            # TODO establish if it's possible to have anything worth parsing written to fs
            #   before `EpuSession.dm` materialises. if not - return early; if yes -
            #   create a temporary placeholder for epu_data until we can get the real thing
            pass

        # 2. scan all gridsquare IDs from /Metadata directory files - this includes "inactive" and "active" gridsquares
        metadata_dir_paths = list(  # TODO it's possible to have multiple `/Metadata` parent dirs. problem for later
            self.datastore.project_dir.glob(f"Metadata/")
        )
        if len(metadata_dir_paths) > 0:
            gridsquares = EpuParser.parse_gridsquares_metadata_dir(metadata_dir_paths[0])
            for gridsquare_id, filename in gridsquares:
                if self.verbose: console.print(f"[dim]Discovered gridsquare {gridsquare_id} from file {filename}[/dim]")
                gridsquare_metadata = EpuParser.parse_gridsquare_metadata(filename)

                # Here we are not worried about overwriting an existing gridsquare
                #   because this is where they are first discovered and added to collection
                assert not self.datastore.gridsquares.exists(gridsquare_id)

                self.datastore.gridsquares.add(gridsquare_id, GridSquareData(
                    id=gridsquare_id,
                    metadata=gridsquare_metadata
                ))
                console.print(self.datastore.gridsquares.get(gridsquare_id))

        # 3. scan all image-disc dir sub-dirs to get a list of active gridsquares. for each gridsquare subdir:
        for gridsquare_manifest_path in list(
            self.datastore.project_dir.glob("Images-Disc*/GridSquare_*/GridSquare_*_*.xml")
        ):
            # 3.1 scan gridsquare manifest (take care to check for existing gridsquare record and not overwrite it)
            gridsquare_manifest = EpuParser.parse_gridsquare_manifest(gridsquare_manifest_path)
            gridsquare_id = re.search(self.gridsquare_dir_pattern, str(gridsquare_manifest_path)).group(1)

            assert self.datastore.gridsquares.exists(gridsquare_id)
            gridsquare_data = self.datastore.gridsquares.get(gridsquare_id)
            gridsquare_data.manifest = gridsquare_manifest
            self.datastore.gridsquares.add(gridsquare_id, gridsquare_data)
            console.print(self.datastore.gridsquares.get(gridsquare_id))

            # 3.2 scan that gridsquare's Foilholes/ dir to get foilholes
            for foilhole_manifest_path in list(
                self.datastore.project_dir.glob(
                    f"Images-Disc*/GridSquare_{gridsquare_id}/FoilHoles/FoilHole_*_*_*.xml"
                )
            ):
                foilhole_id = re.search(self.foilhole_xml_file_pattern, str(foilhole_manifest_path)).group(1)
                self.datastore.foilholes.add(foilhole_id, EpuParser.parse_foilhole_manifest(foilhole_manifest_path))
                console.print(self.datastore.foilholes.get(foilhole_id))

            # 3.3 scan that gridsquare's Foilholes/ dir to get micrographs
            for micrograph_manifest_path in list(
                self.datastore.project_dir.glob(
                    f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_*_Data_*_*_*_*.xml"
                )
            ):
                micrograph_manifest = EpuParser.parse_micrograph_manifest(micrograph_manifest_path)
                match = re.search(self.micrograph_xml_file_pattern, str(micrograph_manifest_path))
                foilhole_id = match.group(1)
                location_id = match.group(2)
                self.datastore.micrographs.add(micrograph_manifest.unique_id, MicrographData(
                    id = micrograph_manifest.unique_id,
                    gridsquare_id = gridsquare_id,
                    foilhole_id = foilhole_id,
                    location_id=location_id,
                    high_res_path=Path(""),
                    manifest_file = micrograph_manifest_path,
                    manifest = micrograph_manifest,
                ))
                console.print(self.datastore.micrographs.get(micrograph_manifest.unique_id))


    def on_any_event(self, event):
        if self.watch_dir is None:
            raise RuntimeError("watch_dir not initialized - call set_watch_dir() first")
        if self.datastore is None:
            raise RuntimeError("datastore not initialized - call init_datastore() first")

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

        # Optimise: if not `new_file_detected` - `event.modified` and `event.size` could be
        #   a good indicator if any interesting changes happened
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
        self.datastore.session_data = data


    def _on_session_updated(self, path: str):
        print(f"Session updated: {path}")
        new_data = EpuParser.parse_epu_session_manifest(path)
        pprint(new_data)
        if self.datastore.session_data != new_data:
            self.datastore.session_data = new_data


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


    # TODO this should be split into 2 events: Gridsquare Metadata and Gridsquare Manifest,
    #   because the dm file in Metadata and the Images-Disk<N>/Gridsquare_<ID>/ dir are
    #   unlikely to be written simultaneously
    def _on_gridsquare_detected(self, path: str):
        print(f"Gridsquare detected: {path}")
        match = self.gridsquare_dm_file_pattern.search(path) # get Gridsquare ID from filename
        gridsquare_id = match.group(1)
        gridsquare_manifest = EpuParser.parse_gridsquare_manifest(path)
        gridsquare_data = GridSquareData(
            id=gridsquare_id,
            manifest=gridsquare_manifest,
        )
        pprint(gridsquare_data)
        self.datastore.gridsquares.add(gridsquare_id, gridsquare_data)


    def _on_gridsquare_updated(self, path: str):
        print(f"Gridsquare updated: {path}")
        manifest = EpuParser.parse_gridsquare_manifest(path)
        pprint(manifest)


    def _on_foilhole_detected(self, path: str):
        print(f"Foilhole detected: {path}")
        data = EpuParser.parse_foilhole_manifest(path)
        pprint(data)
        self.datastore.foilholes.add(data.id, data)


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
            id=manifest.unique_id,
            location_id=location_id,
            gridsquare_id="", # TODO
            high_res_path=Path(""),
            foilhole_id = foilhole_id,
            manifest_file = Path(path),
            manifest = manifest,
        )
        pprint(data)
        self.datastore.micrographs.add(data.id, data)


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
    handler.init_datastore()

    # TODO settle race condition: buffer fs events that occur while `scan_existing_content()` is running
    #   and make sure incremental parser operates on the buffer before moving on to new events
    handler.scan_existing_content()
    observer.schedule(handler, str(path), recursive=True)

    def handle_exit(signum, frame):
        nonlocal handler
        console.print(handler.datastore)
        observer.stop()
        logging.info({ # consider adding stack frame info: `frame`
            "message": "Watching stopped",
            "timestamp": datetime.now().isoformat()
        })
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
