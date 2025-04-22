#!/usr/bin/env python

# TODO: move to tools
# TODO: this is redundant, better done with ripgrep + xq
#  - https://github.com/sibprogrammer/xq

import xml.dom.minidom
import pathlib
import typer
from rich import print
from rich.progress import track
from rich.console import Console
import shutil
from datetime import datetime

XML_EXTENSIONS = {".dm", ".xml"}
console = Console()


def format_xml_files(paths: list[pathlib.Path], recursive: bool, dry_run: bool, verbose: bool, backup: bool) -> None:
    files = []
    for path in paths:
        if path.is_file() and path.suffix in XML_EXTENSIONS:
            files.append(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            files.extend(f for f in path.glob(pattern) if f.suffix in XML_EXTENSIONS)

    if not files:
        print("[yellow]No .dm or .xml files found[/yellow]")
        return

    for file in track(files, description="Processing files"):
        try:
            content = file.read_text(encoding="utf-8")
            parsed = xml.dom.minidom.parseString(content)
            formatted = parsed.toprettyxml(indent="  ")
            formatted = "\n".join(line for line in formatted.split("\n") if line.strip())

            if verbose:
                console.print(f"[blue]Processing:[/blue] {file}")

            if dry_run:
                print(f"[yellow]Would format:[/yellow] {file}")
                continue

            if backup:
                backup_path = file.with_suffix(f"{file.suffix}.{datetime.now():%Y%m%d_%H%M%S}.bak")
                shutil.copy2(file, backup_path)
                if verbose:
                    print(f"[blue]Created backup:[/blue] {backup_path}")

            file.write_text(formatted, encoding="utf-8")
            print(f"[green]✓[/green] Formatted: {file}")

        except Exception as e:
            print(f"[red]✗[/red] Error processing {file}: {e}")


def main(
    paths: list[pathlib.Path] = typer.Argument(
        ..., help="Files or directories to process", exists=True, readable=True, allow_dash=True
    ),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Process directories recursively"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be formatted without making changes"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed processing information"),
    backup: bool = typer.Option(False, "--backup", "-b", help="Create backup files before formatting"),
) -> None:
    """
    Format XML files (.dm and .xml) with proper indentation.

    Processes files in-place by default. Use --dry-run to preview changes,
    --backup to create backups, and --verbose for detailed output.
    """
    format_xml_files(paths, recursive, dry_run, verbose, backup)


if __name__ == "__main__":
    typer.run(main)
