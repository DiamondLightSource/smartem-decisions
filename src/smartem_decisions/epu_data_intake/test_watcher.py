#!/usr/bin/env python

import os
import random
import time
import string
from pathlib import Path
import xml.etree.ElementTree as ET
import typer
from rich.console import Console
from typing import Optional

console = Console()


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_content(size_kb=1):
    return os.urandom(size_kb * 1024)


def create_xml_content():
    root = ET.Element("MicroscopeImage")
    ET.SubElement(root, "Timestamp").text = time.strftime("%Y-%m-%d %H:%M:%S")
    return ET.tostring(root)


def create_dm_content():
    return random_content(10)


def create_epu_structure(base_dir: Path, verbose: bool = False):
    if verbose:
        console.print(f"[blue]Creating EPU structure in {base_dir}[/blue]")

    (base_dir / "EpuSession.dm").write_bytes(create_dm_content())

    for i in range(random.randint(1, 3)):
        sample_dir = base_dir / f"Sample{i + 1}"
        sample_dir.mkdir(exist_ok=True)
        (sample_dir / "Sample.dm").write_bytes(create_dm_content())

        atlas_dir = sample_dir / "Atlas"
        atlas_dir.mkdir(exist_ok=True)
        (atlas_dir / "Atlas.dm").write_bytes(create_dm_content())

    for i in range(random.randint(1, 2)):
        disc_dir = base_dir / f"Images-Disc{i + 1}"
        disc_dir.mkdir(exist_ok=True)

        for j in range(random.randint(1, 3)):
            grid_dir = disc_dir / f"GridSquare_{j + 1}"
            grid_dir.mkdir(exist_ok=True)
            (grid_dir / f"GridSquare_{j + 1}_{random.randint(1, 100)}.xml").write_bytes(create_xml_content())
            (base_dir / "Metadata" / f"GridSquare_{j + 1}.dm").write_bytes(create_dm_content())

            foil_dir = grid_dir / "FoilHoles"
            foil_dir.mkdir(exist_ok=True)
            for k in range(random.randint(1, 3)):
                (foil_dir / f"FoilHole_{k + 1}_{random.randint(1, 100)}_{random.randint(1, 100)}.xml").write_bytes(
                    create_xml_content())

            data_dir = grid_dir / "Data"
            data_dir.mkdir(exist_ok=True)
            for k in range(random.randint(1, 3)):
                data_file = f"FoilHole_{k + 1}_Data_{random.randint(1, 100)}_{random.randint(1, 100)}_{random.randint(1, 100)}_{random.randint(1, 100)}.xml"
                (data_dir / data_file).write_bytes(create_xml_content())


def create_random_structure(directory: Path, verbose: bool = False):
    if verbose:
        console.print(f"[blue]Creating random files in {directory}[/blue]")
    num_files = random.randint(1, 5)
    for _ in range(num_files):
        file_path = directory / f"random_{random_string()}.txt"
        file_path.write_bytes(random_content(random.randint(1, 100)))


def test_filesystem_changes(
        directory: Path = typer.Argument(..., help="Test directory to create and modify files in"),
        duration: int = typer.Option(60, "--duration", "-d", help="Test duration in seconds"),
        interval: float = typer.Option(0.1, "--interval", "-i", help="Interval between changes in seconds"),
        seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed for reproducible tests"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes")
):
    """
    Generate test data simulating EPU microscope file changes.
    Creates and modifies both EPU-specific files (.dm, .xml) and random files.
    """
    if seed is not None:
        random.seed(seed)
        if verbose:
            console.print(f"[blue]Using seed: {seed}[/blue]")

    directory = Path(directory)
    if dry_run:
        console.print(f"Would create test structure in: {directory}")
        console.print(f"Duration: {duration}s, Interval: {interval}s")
        return

    directory.mkdir(exist_ok=True)
    (directory / "Metadata").mkdir(exist_ok=True)

    create_epu_structure(directory, verbose)
    create_random_structure(directory, verbose)

    actions = ['modify_epu', 'modify_random', 'create_epu', 'create_random', 'delete_random']

    with console.status("[bold green]Running file system changes...") as status:
        end_time = time.time() + duration
        while time.time() < end_time:
            action = random.choice(actions)
            if verbose:
                console.print(f"[dim]Action: {action}[/dim]")

            elif action == 'modify_epu':
                epu_files = list(directory.glob('**/*.dm')) + list(directory.glob('**/*.xml'))
                if epu_files:
                    file_to_modify = random.choice(epu_files)
                    with open(file_to_modify, 'ab') as f:  # Append mode
                        f.write(b'\n' + create_dm_content() if file_to_modify.suffix == '.dm' else create_xml_content())


            elif action == 'modify_random':
                random_files = list(directory.glob('**/*.txt'))
                if random_files:
                    file_to_modify = random.choice(random_files)
                    with open(file_to_modify, 'ab') as f:
                        f.write(random_content())

            elif action == 'create_epu':
                create_epu_structure(directory, verbose)

            elif action == 'create_random':
                create_random_structure(directory, verbose)

            elif action == 'delete_random':
                random_files = list(directory.glob('**/*.txt'))
                if random_files:
                    to_delete = random.choice(random_files)
                    to_delete.unlink()

            time.sleep(interval)


if __name__ == "__main__":
    typer.run(test_filesystem_changes)
