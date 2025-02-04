#!/usr/bin/env python

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from datetime import datetime
import logging
from pathlib import Path
import os
import json
from fnmatch import fnmatch
import typer
from rich.console import Console
from typing import List, Optional
import signal
import platform

console = Console()

DEFAULT_PATTERNS = [
    "EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
    "Sample*/Sample.dm",
]


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
    def __init__(self, patterns: List[str], log_interval: float = 10.0, verbose: bool = False):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.changed_files = {}  # Track latest change for each file
        self.patterns = patterns
        self.verbose = verbose

    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = str(Path(path).relative_to(self.watch_dir))
            rel_path = rel_path.replace('\\', '/')  # Normalize path separators
            return any(fnmatch(rel_path, pattern) for pattern in self.patterns)
        except ValueError:
            return False

    def set_watch_dir(self, path: Path):
        self.watch_dir = path.absolute()

    def on_any_event(self, event):
        if event.is_directory:
            return

        if not self.matches_pattern(event.src_path):
            if self.verbose:
                console.print(f"[dim]Skipping non-matching path: {event.src_path}[/dim]")
            return

        current_time = time.time()
        file_stat = None
        try:
            if os.path.exists(event.src_path):
                file_stat = os.stat(event.src_path)
        except (FileNotFoundError, PermissionError) as e:
            if self.verbose:
                console.print(f"[yellow]Warning:[/yellow] {str(e)}")

        # Store only the latest event for each file
        self.changed_files[event.src_path] = (event, current_time, file_stat)

        if current_time - self.last_log_time >= self.log_interval:
            self._flush_events()

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


def setup_logging(log_file: Optional[str], verbose: bool):
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
        patterns: List[str] = typer.Option(
            DEFAULT_PATTERNS,
            "--pattern", "-p",
            help="File patterns to watch (can be specified multiple times)"
        ),
        log_file: Optional[str] = typer.Option(
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
        observer.stop()
        logging.info({
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
