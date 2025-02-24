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

from rich.console import Console
import typer
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from data_model import (
    EpuSession,
    GridSquareData,
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

:type: list[str]
"""
DEFAULT_PATTERNS = [ # TODO consider merging with props in EpuParser
    "EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
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
        # TODO See if this has any benefit or if same can same be achieved through "created" / "modified" file status.
        #   Maybe useful for: https://github.com/DiamondLightSource/smartem-decisions/issues/52
        self.changed_files = {}


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
        new_file_detected = event.src_path not in self.changed_files
        self.changed_files[event.src_path] = (event, current_time, file_stat)

        match event.src_path:
            case path if re.search(EpuParser.session_dm_pattern, path):
                # Needs testing to see if this is a practical way to detect session start or if there's an
                #   alternative / additional way, e.g. appearance of a project dir. TODO: not a valid way!!!!
                self._on_session_detected(path, new_file_detected)
            case path if re.search(EpuParser.atlas_dm_pattern, path):
                self._on_atlas_detected(path, new_file_detected)
            case path if re.search(EpuParser.gridsquare_dm_file_pattern, path):
                self._on_gridsquare_metadata_detected(path, new_file_detected)
            case path if re.search(EpuParser.gridsquare_xml_file_pattern, path):
                self._on_gridsquare_manifest_detected(path, new_file_detected)
            case path if re.search(EpuParser.foilhole_xml_file_pattern, path):
                self._on_foilhole_detected(path, new_file_detected)
            case path if re.search(EpuParser.micrograph_xml_file_pattern, path):
                self._on_micrograph_detected(path, new_file_detected)


    def _on_session_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Session manifest {'detected' if is_new_file else 'updated'}: {path}")
        session_data = EpuParser.parse_epu_session_manifest(path)
        if session_data != self.datastore.session_data:
            self.datastore.session_data = session_data
            console.print(self.datastore.session_data)


    def _on_atlas_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Atlas {'detected' if is_new_file else 'updated'}: {path}")
        atlas_data = EpuParser.parse_atlas_manifest(path)
        if atlas_data != self.datastore.atlas_data:
            self.datastore.atlas_data = atlas_data
            console.print(self.datastore.atlas_data)


    def _on_gridsquare_metadata_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Gridsquare metadata {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = EpuParser.gridsquare_dm_file_pattern.search(path).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridsquare_metadata = EpuParser.parse_gridsquare_metadata(path)

        if not self.datastore.gridsquares.exists(gridsquare_id):
            gridsquare_data = GridSquareData(
                id=gridsquare_id,
                metadata=gridsquare_metadata,
            )
        else:
            gridsquare_data = self.datastore.gridsquares.get(gridsquare_id)
            gridsquare_data.metadata = gridsquare_metadata

        self.datastore.gridsquares.add(gridsquare_id, gridsquare_data)
        console.print(gridsquare_data)


    def _on_gridsquare_manifest_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Gridsquare manifest {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = re.search(EpuParser.gridsquare_dir_pattern, str(path)).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridsquare_manifest = EpuParser.parse_gridsquare_manifest(path)

        if not self.datastore.gridsquares.exists(gridsquare_id):
            gridsquare_data = GridSquareData(
                id=gridsquare_id,
                manifest=gridsquare_manifest,
            )
        else:
            gridsquare_data = self.datastore.gridsquares.get(gridsquare_id)
            gridsquare_data.manifest = gridsquare_manifest

        self.datastore.gridsquares.add(gridsquare_id, gridsquare_data)
        console.print(gridsquare_data)


    def _on_foilhole_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Foilhole {'detected' if is_new_file else 'updated'}: {path}")
        data = EpuParser.parse_foilhole_manifest(path)
        # Here it is by intent that any previously recorded data for given foilhole is overwritten as
        # there are instances of multiple manifest files written to fs and in these cases
        # only the newest (by timestamp) is relevant.
        # TODO It is assumed that latest foilhole manifest by timestamp in filename will also be
        #  last to be written to fs, but additional filename-based checks wouldn't hurt - resolve latest
        #  based on timestamp found in filename.
        self.datastore.foilholes.add(data.id, data)
        console.print(data)


    def _on_micrograph_detected(self, path: str, is_new_file: bool = True):
        console.print(f"Micrograph {'detected' if is_new_file else 'updated'}: {path}")

        match = re.search(EpuParser.micrograph_xml_file_pattern, path)
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
        self.datastore.micrographs.add(data.id, data)
        console.print(data)


    def _on_session_complete(self):
        """
        TODO: explore how to reliably determine when session ended
            (and bear in mind that it could have been paused, to be resumed later)?
            Could Athena API be queried for this?
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
):
    """Watch directory for file changes and log them in JSON format. Supports Windows/Cygwin environments.
    """
    path = Path(path).absolute()
    if not path.exists():
        console.print(f"[red]Error:[/red] Directory {path} does not exist")
        raise typer.Exit(1)

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

    # TODO settle a potential race condition, test if exists:
    handler.datastore = EpuParser.parse_acquisition_dir(handler.datastore, verbose)
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
