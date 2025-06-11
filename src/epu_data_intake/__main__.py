#!/usr/bin/env python3

import logging
import platform
import signal
import time
from pathlib import Path

import typer
from watchdog.observers import Observer

from epu_data_intake.core_http_api_client import SmartEMAPIClient as APIClient
from epu_data_intake.fs_parser import EpuParser
from epu_data_intake.fs_watcher import (
    DEFAULT_PATTERNS,
    RateLimitedFilesystemEventHandler,
)
from epu_data_intake.model.store import InMemoryDataStore

epu_data_intake_cli = typer.Typer(help="EPU Data Intake Tools")
parse_cli = typer.Typer(help="Commands for parsing EPU data")
epu_data_intake_cli.add_typer(parse_cli, name="parse")


# Add callbacks to all command groups to support -v/-vv flags
# The callback functions themselves don't need to do anything special since our `verbose_callback` function
# does the actual work of configuring the logging.
# They just need to exist to allow Typer to recognize the flag at that command level.
@epu_data_intake_cli.callback()
def main_callback():
    """Main callback to enable verbose flag on root command"""
    pass


@parse_cli.callback()
def parse_callback():
    """Parse group callback to enable verbose flag on parse command"""
    pass


@parse_cli.command("dir")
def parse_epu_output_dir(
    epu_output_dir: str,
    verbose: int = 0,
):
    """Parse an entire EPU output directory structure. May contain multiple grids"""
    # Rationale here is that parsers don't persist data to API by design - only watch command does that
    datastore = InMemoryDataStore(epu_output_dir)

    # Initialize the acquisition_rels dict with a set for the acquisition
    datastore.acquisition_rels[datastore.acquisition.uuid] = set()

    # The EpuParser.parse_epu_output_dir would need to be updated to work with the new store
    datastore = EpuParser.parse_epu_output_dir(datastore)
    False and logging.debug(datastore)


@parse_cli.command("grid")
def parse_grid(
    grid_data_dir: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    is_valid, errors = EpuParser.validate_project_dir(Path(grid_data_dir))

    if not is_valid:
        logging.warning("Grid data dir dir is structurally invalid. Found the following issues:\n")
        for error in errors:
            logging.warning(f"- {error}")
    else:
        # Rationale here is that parsers don't persist data to API by design - only watch command does that
        datastore = InMemoryDataStore(
            grid_data_dir
        )  # TODO confirm this is the dir expected here - top-level watch dir or grid root dir?
        EpuParser.parse_grid_dir(grid_data_dir, datastore)
        False and logging.debug(datastore)


@parse_cli.command("session")
def parse_epu_session(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse an EPU session manifest file."""
    epu_session_data = EpuParser.parse_epu_session_manifest(path)
    logging.info(epu_session_data)


@parse_cli.command("atlas")
def parse_atlas(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse an atlas manifest file."""
    atlas_data = EpuParser.parse_atlas_manifest(path)
    logging.info(atlas_data)


@parse_cli.command("gridsquare-metadata")
def parse_gridsquare_metadata(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse grid square metadata."""
    metadata = EpuParser.parse_gridsquare_metadata(path)
    logging.info(metadata)


@parse_cli.command("gridsquare")
def parse_gridsquare(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse a grid square manifest file."""
    gridsquare_manifest_data = EpuParser.parse_gridsquare_manifest(path)
    logging.info(gridsquare_manifest_data)


@parse_cli.command("foilhole")
def parse_foilhole(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse a foil hole manifest file."""
    foilhole_data = EpuParser.parse_foilhole_manifest(path)
    logging.info(foilhole_data)


@parse_cli.command("micrograph")
def parse_micrograph(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Parse a micrograph manifest file."""
    micrograph_data = EpuParser.parse_micrograph_manifest(path)
    logging.info(micrograph_data)


@epu_data_intake_cli.command("validate")
def validate_epu_dir(
    path: str,
    verbose: int = 0,  # Used by Typer for CLI context, do not remove
):
    """Validate the structure of an EPU project directory. Note - this only asserts
    that the structure is valid, does not validate content of files within."""
    is_valid, errors = EpuParser.validate_project_dir(Path(path))

    if is_valid:
        logging.info("EPU project dir is structurally valid")
    else:
        logging.info("Invalid EPU project dir. Found the following issues:\n")
        for error in errors:
            logging.info(f"- {error}")

    return not is_valid  # Return non-zero exit code if validation fails


@epu_data_intake_cli.command("watch")
def watch_directory(
    path: Path,
    dry_run: bool = False,
    api_url: str = "http://127.0.0.1:8000",
    log_file: str = "fs_changes.log",
    log_interval: float = 10.0,
    verbose: int = 0,
):
    """Watch directory for file changes and log them in JSON format."""

    # Configure logging based on verbosity level
    if verbose == 2:  # Debug level (most verbose)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )
    elif verbose == 1:  # Info level
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )
    else:  # Default warning level
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )

    path = Path(path).absolute()
    if not path.exists():
        logging.error(f"Error: Directory {path} does not exist")
        raise typer.Exit(1)

    if not dry_run:
        try:
            import asyncio

            async def check_api():
                async with APIClient(api_url) as client:
                    status_data = await client.get_status()
                    return status_data

            status_result = asyncio.run(check_api())
            logging.info(f"API is reachable at {api_url} - Status: {status_result.get('status', 'unknown')}")
        except Exception as e:
            logging.error(f"Error: API at {api_url} is not reachable: {str(e)}")
            raise typer.Exit(1) from None

    logging.info(
        f"Starting to watch directory: {str(path)} (including subdirectories) for patterns: {DEFAULT_PATTERNS}"
    )

    handler = RateLimitedFilesystemEventHandler(path, dry_run, api_url, log_interval, DEFAULT_PATTERNS)

    logging.info("Parsing existing directory contents...")
    # TODO settle a potential race condition between parser and watcher if one exists:
    handler.datastore = EpuParser.parse_epu_output_dir(handler.datastore)

    logging.info("..done! Now listening for new filesystem events")
    observer = Observer()
    observer.schedule(handler, str(path), recursive=True)

    def handle_exit(signum, frame):
        nonlocal handler
        logging.info(handler.datastore)

        observer.stop()
        logging.info("Watching stopped")
        observer.join()
        raise typer.Exit()

    # Handle both CTRL+C and Windows signals
    signal.signal(signal.SIGINT, handle_exit)
    if platform.system() == "Windows":
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
