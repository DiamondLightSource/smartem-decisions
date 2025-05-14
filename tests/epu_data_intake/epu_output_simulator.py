# !/usr/bin/env python

import os
import random
import shutil
import sys
import time
from pathlib import Path

import typer

# Import rich conditionally
try:
    from rich.console import Console
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

app = typer.Typer(help="Simulate EPU data output for testing purposes")
console = Console() if RICH_AVAILABLE else None


@app.command()
def simulate(
    output_dir: Path = typer.Argument(..., help="Directory to write simulated EPU output"),
    template_dir: Path = typer.Option(..., "--template-dir", help="Path to directory containing template data"),
    interval: float = typer.Option(0.05, "--interval", "-i", help="Interval between changes in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    clean_output: bool = typer.Option(True, "--clean", help="Clean output directory before starting"),
    use_progress_bar: bool = typer.Option(False, "--progress", "-p", help="Use progress bars for visualization"),
    run_smoke_test: bool = typer.Option(True, "--smoke-test/--no-smoke-test", help="Run smoke test after simulation"),
):
    """
    Simulate EPU data output by writing files from a template directory to an output directory.

    The simulation occurs in two phases:
    1. Pre-existing data: Files that might exist prior to EPU watcher invocation if it was started
        after the EPU began writing data
    2. Live data: Files that are written incrementally during the simulated run
    """
    # Check if progress bars are requested but rich is not available
    if use_progress_bar and not RICH_AVAILABLE:
        typer.echo("Warning: Rich library is not installed. Progress bars will not be shown.")
        typer.echo("Install with: pip install rich")
        use_progress_bar = False

    # Start timing the simulation
    start_time = time.time()

    # Validate paths before proceeding
    validate_paths(template_dir, output_dir, verbose)

    # Prepare output directory
    prepare_output_directory(output_dir, clean_output, verbose)

    # Scan template directory and create manifest
    if verbose:
        typer.echo(f"Scanning template directory: {template_dir}")

    manifest = create_manifest(template_dir, verbose)

    # Write pre-existing data
    if use_progress_bar and RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            pre_task = progress.add_task(
                "[green]Writing pre-existing data...", total=len(manifest["preexisting_files"])
            )
            write_preexisting_data(template_dir, output_dir, manifest, verbose, progress, pre_task)
    else:
        if verbose:
            typer.echo("Writing pre-existing data...")
        write_preexisting_data(template_dir, output_dir, manifest, verbose)

    # Pause for user input
    typer.echo("Pre-existing data written. Press Enter to continue with live data simulation or Ctrl+C to quit...")
    try:
        input()
    except KeyboardInterrupt:
        typer.echo("\nSimulation terminated by user.")
        sys.exit(0)

    # Write live data according to manifest
    if use_progress_bar and RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            live_task = progress.add_task("[green]Writing live data...", total=len(manifest["live_groups"]))
            write_live_data(template_dir, output_dir, manifest, interval, verbose, progress, live_task)
    else:
        if verbose:
            typer.echo("Starting live data simulation...")
        write_live_data(template_dir, output_dir, manifest, interval, verbose)

    # Run smoke test if requested
    if run_smoke_test:
        typer.echo("Running smoke test...")
        smoke_test(template_dir, output_dir, verbose)

    # Calculate and display elapsed time
    elapsed_time = time.time() - start_time
    typer.echo(f"Simulation completed successfully in {elapsed_time:.2f} seconds.")


def prepare_output_directory(output_dir: Path, clean: bool, verbose: bool) -> None:
    """Prepare the output directory, creating it if it doesn't exist and optionally cleaning it."""
    if not output_dir.exists():
        if verbose:
            typer.echo(f"Creating output directory: {output_dir}")
        output_dir.mkdir(parents=True)
    elif clean:
        if verbose:
            typer.echo(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)


def create_manifest(template_dir: Path, verbose: bool) -> dict:
    """
    Scan template directory and create a manifest of files to write.

    The manifest will divide files into pre-existing and live data,
    and specify the order, grouping, and timing of live data writes.
    """
    if not template_dir.exists() or not template_dir.is_dir():
        typer.echo(f"Error: Template directory {template_dir} does not exist or is not a directory")
        sys.exit(1)

    # Collect all files in the template directory
    template_files = [f for f in template_dir.glob("**/*") if f.is_file()]

    if not template_files:
        typer.echo(f"Error: No files found in template directory {template_dir}")
        sys.exit(1)

    if verbose:
        typer.echo(f"Found {len(template_files)} files in template directory")

    # For now, randomly split files between pre-existing and live data
    # We'll refine this logic later
    random.shuffle(template_files)
    split_point = len(template_files) // 2

    preexisting_files = template_files[:split_point]
    live_files = template_files[split_point:]

    # Create groups of live files for simultaneous writing
    # For now, create random groups of 1-3 files
    live_groups = []
    remaining = live_files.copy()

    while remaining:
        group_size = min(random.randint(1, 30), len(remaining))
        group = []

        for _ in range(group_size):
            group.append(remaining.pop(0))

        live_groups.append(group)

    # Create manifest
    manifest = {
        "preexisting_files": [str(f.relative_to(template_dir)) for f in preexisting_files],
        "live_groups": [[str(f.relative_to(template_dir)) for f in group] for group in live_groups],
    }

    if verbose:
        typer.echo(
            f"Created manifest with {len(manifest['preexisting_files'])} pre-existing files "
            f"and {len(manifest['live_groups'])} live file groups"
        )

    return manifest


def write_preexisting_data(
    template_dir: Path, output_dir: Path, manifest: dict, verbose: bool, progress=None, task_id=None
) -> None:
    """Write pre-existing data files to the output directory."""
    for i, rel_path in enumerate(manifest["preexisting_files"]):
        src_file = template_dir / rel_path
        dst_file = output_dir / rel_path

        # Ensure parent directory exists
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Determine if this is a file we should copy fully or create an empty placeholder
        if is_important_file(src_file):
            # Copy the file with full content
            shutil.copy2(src_file, dst_file)
            if verbose and not progress:
                typer.echo(f"Written pre-existing file: {rel_path}")
        else:
            # Create empty placeholder file with same name
            dst_file.touch()
            if verbose and not progress:
                typer.echo(f"Written pre-existing placeholder: {rel_path}")

        # Update progress bar if available
        if progress and task_id is not None:
            progress.update(
                task_id,
                advance=1,
                description=f"[green]Writing pre-existing data... ({i + 1}/{len(manifest['preexisting_files'])})",
            )


def write_live_data(
    template_dir: Path, output_dir: Path, manifest: dict, interval: float, verbose: bool, progress=None, task_id=None
) -> None:
    """Write live data files to the output directory according to the manifest."""
    for i, group in enumerate(manifest["live_groups"]):
        if verbose and not progress:
            typer.echo(f"Writing file group {i + 1}/{len(manifest['live_groups'])}")
        elif progress and task_id is not None:
            progress.update(
                task_id, description=f"[green]Writing live data group {i + 1}/{len(manifest['live_groups'])}"
            )

        # Write each file in the group
        for rel_path in group:
            src_file = template_dir / rel_path
            dst_file = output_dir / rel_path

            # Ensure parent directory exists
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Determine if this is a file we should copy fully or create an empty placeholder
            if is_important_file(src_file):
                # Copy the file with full content
                shutil.copy2(src_file, dst_file)
                if verbose and not progress:
                    typer.echo(f"Written live file: {rel_path}")
            else:
                # Create empty placeholder file with same name
                dst_file.touch()
                if verbose and not progress:
                    typer.echo(f"Written live placeholder: {rel_path}")

        # Update progress bar if available
        if progress and task_id is not None:
            progress.update(task_id, advance=1)

        # Wait before the next group (unless it's the last group)
        if i < len(manifest["live_groups"]) - 1:
            # Add some randomness to the interval (±50%)
            actual_interval = interval * random.uniform(0.5, 1.5)

            if verbose and not progress:
                typer.echo(f"Waiting {actual_interval:.2f}s before next group...")

            time.sleep(actual_interval)


def validate_paths(template_dir: Path, output_dir: Path, verbose: bool) -> None:
    """
    Validate that the template and output directories exist and have appropriate permissions.
    Exit with an error message if validation fails.
    """
    # Validate template directory
    if not template_dir.exists():
        typer.echo(f"Error: Template directory {template_dir} does not exist", err=True)
        sys.exit(1)

    if not template_dir.is_dir():
        typer.echo(f"Error: Template path {template_dir} is not a directory", err=True)
        sys.exit(1)

    if not os.access(template_dir, os.R_OK):
        typer.echo(f"Error: No read permission for template directory {template_dir}", err=True)
        sys.exit(1)

    # Check if template directory has any files
    template_files = list(template_dir.glob("**/*"))
    if not any(f.is_file() for f in template_files):
        typer.echo(f"Error: Template directory {template_dir} does not contain any files", err=True)
        sys.exit(1)

    # Validate output directory
    if output_dir.exists():
        if not output_dir.is_dir():
            typer.echo(f"Error: Output path {output_dir} exists but is not a directory", err=True)
            sys.exit(1)

        if not os.access(output_dir, os.W_OK):
            typer.echo(f"Error: No write permission for output directory {output_dir}", err=True)
            sys.exit(1)
    else:
        # Check if we can create the output directory
        try:
            # Check if parent directory exists and is writable
            parent_dir = output_dir.parent
            if not parent_dir.exists():
                typer.echo(f"Error: Parent directory {parent_dir} for output does not exist", err=True)
                sys.exit(1)

            if not os.access(parent_dir, os.W_OK):
                typer.echo(f"Error: No write permission for parent directory {parent_dir}", err=True)
                sys.exit(1)

            if verbose:
                typer.echo(f"Output directory {output_dir} will be created")

        except Exception as e:
            typer.echo(f"Error validating output directory: {str(e)}", err=True)
            sys.exit(1)

    if verbose:
        typer.echo("Path validation successful")


def is_important_file(file_path: Path) -> bool:
    """
    Determine if a file is considered important and should be copied with full content.
    Important files are XML files (.xml or .dm extensions).
    """
    # Get lowercase file extension
    suffix = file_path.suffix.lower()
    return suffix in {".xml", ".dm"}


def smoke_test(template_dir: Path, output_dir: Path, verbose: bool) -> None:
    """
    Compare template directory with output directory to ensure all files were copied correctly.
    Checks that all important files (XML, DM) from the manifest have been properly copied.

    Returns: None, but exits with error code 1 if test fails
    """
    if verbose:
        typer.echo("Running smoke test to verify file integrity...")

    # Get list of important files from template directory
    template_files = [f for f in template_dir.glob("**/*") if f.is_file() and is_important_file(f)]

    # Track statistics
    total_files = len(template_files)
    matched_files = 0
    missing_files = []
    size_mismatches = []

    # Check each important file
    for src_file in template_files:
        rel_path = src_file.relative_to(template_dir)
        dst_file = output_dir / rel_path

        # Check if file exists in output
        if not dst_file.exists():
            missing_files.append(str(rel_path))
            continue

        # Check if size matches (for important files only)
        if src_file.stat().st_size != dst_file.stat().st_size:
            size_mismatches.append(str(rel_path))
            continue

        # If we get here, the file matches
        matched_files += 1

    # Display results
    if verbose or missing_files or size_mismatches:
        typer.echo(f"Smoke test results: {matched_files}/{total_files} files verified")

    # Report any issues
    if missing_files:
        typer.echo(f"Error: {len(missing_files)} files missing in output directory:", err=True)
        for file in missing_files[:10]:  # Show first 10 only to avoid flooding terminal
            typer.echo(f"  - {file}", err=True)
        if len(missing_files) > 10:
            typer.echo(f"  ... and {len(missing_files) - 10} more", err=True)

    if size_mismatches:
        typer.echo(f"Error: {len(size_mismatches)} files with size mismatches:", err=True)
        for file in size_mismatches[:10]:  # Show first 10 only
            typer.echo(f"  - {file}", err=True)
        if len(size_mismatches) > 10:
            typer.echo(f"  ... and {len(size_mismatches) - 10} more", err=True)

    # Exit with error if any issues found
    if missing_files or size_mismatches:
        typer.echo("Smoke test failed! Files were not copied correctly.", err=True)
        sys.exit(1)
    elif verbose:
        typer.echo("Smoke test passed successfully!")


if __name__ == "__main__":
    app()
