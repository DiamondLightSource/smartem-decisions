#!/usr/bin/env python3

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from rich.table import Table

# Initialize rich console
console = Console()
app = typer.Typer(help="Find FoilHole XML files with matching numbers but different timestamps.")


def find_foilhole_duplicates(directory: Path, verbose: bool):
    """Find duplicate FoilHole XML files with matching numbers but different timestamps."""

    if verbose:
        console.print(f"\n[bold blue]Searching in directory:[/] {directory}")

    # Find all XML files using ripgrep
    rg_cmd = ["rg", "--files", "--glob", "*.xml", str(directory)]

    try:
        result = subprocess.run(rg_cmd, capture_output=True, text=True)
        all_files = result.stdout.splitlines()

        if verbose:
            console.print(f"\nFound [bold green]{len(all_files)}[/] XML files")

        # Filter for FoilHole files
        pattern = re.compile(r".*/FoilHoles/FoilHole_(\d+)_(\d{8}_\d{6})\.xml$")

        # Group files by their FoilHole number
        grouped_files = defaultdict(list)

        # Use rich's track for progress indication in verbose mode
        file_iterator = track(all_files, description="Processing files...") if verbose else all_files

        for file_path in file_iterator:
            match = pattern.search(file_path)
            if match:
                foilhole_num, timestamp = match.groups()
                grouped_files[foilhole_num].append((timestamp, file_path))

        if verbose:
            console.print(f"Found [bold green]{len(grouped_files)}[/] unique FoilHole numbers")

        # Filter for only those with different timestamps
        duplicates = {
            num: entries
            for num, entries in grouped_files.items()
            if len(entries) > 1 and len({timestamp for timestamp, _ in entries}) > 1
        }

        return duplicates

    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running ripgrep command:[/] {e}", file=sys.stderr)
        raise typer.Exit(code=1) from e


def create_summary_table(duplicates):
    """Create a rich table with summary information."""
    table = Table(title="Duplicate Files Summary")

    table.add_column("FoilHole Number", style="cyan")
    table.add_column("File Count", justify="right", style="green")
    table.add_column("Timestamps", style="yellow")

    for foilhole_num, entries in sorted(duplicates.items()):
        timestamps = ", ".join(sorted(ts.split("_")[1] for ts, _ in entries))
        table.add_row(f"FoilHole_{foilhole_num}", str(len(entries)), timestamps)

    return table


@app.command()
def main(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Directory to search",
            exists=True,
            dir_okay=True,
            file_okay=False,
        ),
    ] = Path("."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress and statistics"),
    output_format: str = typer.Option("standard", "--format", "-f", help="Output format (standard, json, or summary)"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
):
    """
    Find and report FoilHole XML files that have matching numbers but different timestamps

    This tool recursively searches through directories to find XML files in FoilHoles
    directories and identifies cases where files share the same FoilHole number but
    have different timestamps. Assumes ripgrep is installed on the system
    and is on PATH: https://github.com/BurntSushi/ripgrep
    """

    if no_color:
        console.no_color = True

    try:
        with console.status("[bold green]Searching for duplicate files..."):
            duplicates = find_foilhole_duplicates(directory, verbose)

        if not duplicates:
            console.print("[yellow]No duplicates found[/]")
            return

        total_groups = len(duplicates)
        total_files = sum(len(entries) for entries in duplicates.values())

        if output_format == "json":
            result = {
                "summary": {
                    "total_groups": total_groups,
                    "total_files": total_files,
                    "average_files_per_group": total_files / total_groups,
                },
                "duplicates": {
                    f"FoilHole_{num}": [{"timestamp": ts, "path": path} for ts, path in sorted(entries)]
                    for num, entries in duplicates.items()
                },
            }
            console.print_json(data=result)

        elif output_format == "summary":
            table = create_summary_table(duplicates)
            console.print(table)
            console.print(f"\nTotal groups with duplicates: [bold green]{total_groups}[/]")
            console.print(f"Total files involved: [bold green]{total_files}[/]")
            console.print(f"Average files per group: [bold green]{total_files / total_groups:.2f}[/]")

        else:  # standard output
            for foilhole_num, entries in duplicates.items():
                panel_content = "\n".join(f"  {path}" for _, path in sorted(entries))
                console.print(
                    Panel(
                        panel_content,
                        title=f"[bold cyan]FoilHole_{foilhole_num}[/]",
                        subtitle=f"[bold yellow]{len(entries)} files[/]",
                    )
                )

            if verbose:
                console.print("\n[bold]Statistics:[/]")
                console.print(f"  Total groups with duplicates: [bold green]{total_groups}[/]")
                console.print(f"  Total files involved: [bold green]{total_files}[/]")
                console.print(f"  Average files per group: [bold green]{total_files / total_groups:.2f}[/]")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {str(e)}", file=sys.stderr)
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()
