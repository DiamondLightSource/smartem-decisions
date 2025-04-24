#!/usr/bin/env python3

import logging
import platform
import signal
import time
import typer
from pathlib import Path
from watchdog.observers import Observer

from src.epu_data_intake.data_model import EpuAcquisitionSessionStore
from src.epu_data_intake.fs_parser import EpuParser
from src.epu_data_intake.fs_watcher import (
    DEFAULT_PATTERNS,
    RateLimitedHandler,
)

# Create a callback to handle the verbose flag at the root level
def verbose_callback(ctx: typer.Context, param: typer.CallbackParam, value: bool):
    if value:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True,
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True,
        )
    # Store verbose setting in context for child commands to access
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = value
    return value

epu_data_intake_cli = typer.Typer(help="EPU Data Intake Tools")
parse_cli = typer.Typer(help="Commands for parsing EPU data")
epu_data_intake_cli.add_typer(parse_cli, name="parse")

# Add verbose flag to root command
shared_verbose_option = typer.Option(
    False,
    "--verbose",
    "-v",
    help="Enable verbose output",
    callback=verbose_callback,
    is_eager=True,  # Process this flag before other parameters
)

# Add callbacks to all command groups to support -v flag
# The callback functions themselves don't need to do anything special since our `verbose_callback` function
# does the actual work of configuring the logging.
# They just need to exist to allow Typer to recognize the flag at that command level.
@epu_data_intake_cli.callback()
def main_callback(verbose: bool = shared_verbose_option):
    """Main callback to enable verbose flag on root command"""
    pass

@parse_cli.callback()
def parse_callback(verbose: bool = shared_verbose_option):
    """Parse group callback to enable verbose flag on parse command"""
    pass

@parse_cli.command("dir")
def parse_epu_output_dir(
    epu_output_dir: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse an entire EPU output directory structure. May contain multiple grids"""
    datastore = EpuAcquisitionSessionStore(epu_output_dir)
    datastore = EpuParser.parse_epu_output_dir(datastore)
    logging.info(datastore)


@parse_cli.command("grid")
def parse_grid(
    grid_data_dir: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    is_valid, errors = EpuParser.validate_project_dir(Path(grid_data_dir))

    if not is_valid:
        logging.info("Grid data dir dir is structurally invalid. Found the following issues:\n")
        for error in errors:
            logging.info(f"- {error}")
    else:
        gridstore = EpuParser.parse_grid_dir(grid_data_dir)
        logging.info(gridstore)


@parse_cli.command("session")
def parse_epu_session(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse an EPU session manifest file."""
    epu_session_data = EpuParser.parse_epu_session_manifest(path)
    logging.info(epu_session_data)


@parse_cli.command("atlas")
def parse_atlas(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse an atlas manifest file."""
    atlas_data = EpuParser.parse_atlas_manifest(path)
    logging.info(atlas_data)


@parse_cli.command("gridsquare-metadata")
def parse_gridsquare_metadata(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse grid square metadata."""
    metadata = EpuParser.parse_gridsquare_metadata(path)
    logging.info(metadata)


@parse_cli.command("gridsquare")
def parse_gridsquare(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse a grid square manifest file."""
    gridsquare_manifest_data = EpuParser.parse_gridsquare_manifest(path)
    logging.info(gridsquare_manifest_data)


@parse_cli.command("foilhole")
def parse_foilhole(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse a foil hole manifest file."""
    foilhole_data = EpuParser.parse_foilhole_manifest(path)
    logging.info(foilhole_data)


@parse_cli.command("micrograph")
def parse_micrograph(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
):
    """Parse a micrograph manifest file."""
    micrograph_data = EpuParser.parse_micrograph_manifest(path)
    logging.info(micrograph_data)


@epu_data_intake_cli.command("validate")
def validate_epu_dir(
    path: str,
    verbose: bool = shared_verbose_option, # Used by Typer for CLI context, do not remove
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
    path: Path = typer.Argument(..., help="Directory to watch"),
    dry_run: bool = typer.Option(
        False, "--dry_run", "-n", help="Enables dry run mode, writing data in-memory and not posting to Core's HTTP API"
    ),
    # TODO consider providing via env but allowing override via CLI. Investigate how Win env vars work or if they do even
    api_url: str = typer.Option(
        "http://127.0.0.1:8000", "--api-url", "-a", help="URL for the Core API (required unless in dry run mode)"
    ),
    # TODO currently unused because logging should come from `~smartem_decisions~` `shared` module,
    #  and the log filename should be wired to `log_manager` instantiation once that's in place.
    log_file: str | None = typer.Option("fs_changes.log", "--log-file", "-l", help="Log file path (optional)"),
    log_interval: float = typer.Option(
        10.0, "--interval", "-i", help="Minimum interval between log entries in seconds"
    ),
    # TODO decide if there's ever a use-case when we might want to override the defaults - drop otherwise
    patterns: list[str] = typer.Option(
        DEFAULT_PATTERNS, "--pattern", "-p", help="File patterns to watch (can be specified multiple times)"
    ),
    verbose: bool = shared_verbose_option,
):
    """Watch directory for file changes and log them in JSON format."""
    path = Path(path).absolute()
    if not path.exists():
        logging.error(f"Error: Directory {path} does not exist")
        raise typer.Exit(1)

    if not dry_run and not api_url:
        logging.error("Error: API URL must be provided when not in dry run mode")
        raise typer.Exit(1)

    logging.info(f"Starting to watch directory: {str(path)} (including subdirectories) for patterns: {patterns}")

    observer = Observer()

    # TODO verify verbose parameter is still needed If it's *only* used for logging verbosity - check if logging
    #   that's already set up here is being used, making this param redundant
    handler = RateLimitedHandler(patterns, log_interval, verbose)
    handler.set_watch_dir(path)
    handler.init_datastore(dry_run, api_url)

    logging.info("Parsing existing directory contents...")
    # TODO settle a potential race condition if one exists:
    handler.datastore = EpuParser.parse_epu_output_dir(handler.datastore, verbose)
    # TODO ^ verify verbose parameter is still needed If it's *only* used for logging verbosity - check if logging
    #   that's already set up here is being used, making this param redundant
    logging.info("..done! Now listening for new filesystem events")
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
