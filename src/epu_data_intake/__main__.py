#!/usr/bin/env python3

import platform
import signal
import time
import typer
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer

from src.epu_data_intake.data_model import EpuSession
from src.epu_data_intake.fs_parser import EpuParser
from src.epu_data_intake.fs_watcher import (
    DEFAULT_PATTERNS,
    RateLimitedHandler,
)
from src.epu_data_intake.utils import (
    logging,
    setup_logging,
)

epu_data_intake_cli = typer.Typer(help="EPU Data Intake Tools")
parse_cli = typer.Typer(help="Commands for parsing EPU data")
epu_data_intake_cli.add_typer(parse_cli, name="parse")


@parse_cli.command("dir")
def parse_epu_dir(dir_path: str):
    """Parse an entire EPU directory structure."""
    datastore = EpuSession(
        EpuParser.resolve_project_dir(Path(dir_path)),
        EpuParser.resolve_atlas_dir(Path(dir_path)),
    )
    datastore = EpuParser.parse_acquisition_dir(datastore)
    print(datastore)


@parse_cli.command("session")
def parse_epu_session(path: str):
    """Parse an EPU session manifest file."""
    epu_session_data = EpuParser.parse_epu_session_manifest(path)
    print(epu_session_data)


@parse_cli.command("atlas")
def parse_atlas(path: str):
    """Parse an atlas manifest file."""
    atlas_data = EpuParser.parse_atlas_manifest(path)
    print(atlas_data)


@parse_cli.command("gridsquare-metadata")
def parse_gridsquare_metadata(path: str):
    """Parse grid square metadata."""
    metadata = EpuParser.parse_gridsquare_metadata(path)
    print(metadata)


@parse_cli.command("gridsquare")
def parse_gridsquare(path: str):
    """Parse a grid square manifest file."""
    gridsquare_manifest_data = EpuParser.parse_gridsquare_manifest(path)
    print(gridsquare_manifest_data)


@parse_cli.command("foilhole")
def parse_foilhole(path: str):
    """Parse a foil hole manifest file."""
    foilhole_data = EpuParser.parse_foilhole_manifest(path)
    print(foilhole_data)


@parse_cli.command("micrograph")
def parse_micrograph(path: str):
    """Parse a micrograph manifest file."""
    micrograph_data = EpuParser.parse_micrograph_manifest(path)
    print(micrograph_data)


@epu_data_intake_cli.command("validate")
def validate_epu_dir(path: str):
    """Validate the structure of an EPU project directory. Note - this only asserts
    that the structure is valid, does not validate content of files within."""
    is_valid, errors = EpuParser.validate_project_dir(Path(path))

    if is_valid:
        print("EPU project dir is structurally valid")
    else:
        print("Invalid EPU project dir. Found the following issues:\n")
        for error in errors:
            print(f"- {error}")

    return not is_valid  # Return non-zero exit code if validation fails


@epu_data_intake_cli.command("watch")
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
    """Watch directory for file changes and log them in JSON format."""
    path = Path(path).absolute()
    if not path.exists():
        print(f"Error: Directory {path} does not exist")
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
        print(handler.datastore)
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
    pass


if __name__ == "__main__":
    epu_data_intake_cli()
