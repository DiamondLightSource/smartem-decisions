#!/usr/bin/env python

# TODO move to tests

import os
import random
import time
import string
from pathlib import Path
import xml.etree.ElementTree as ET
import typer
from rich.console import Console
import shutil

console = Console()


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class EPUTemplates:
    def __init__(self, template_dir: Path):
        self.template_dir = Path(template_dir)
        self._cache = {}
        self._load_templates()

    def _load_templates(self):
        """Load template files into memory"""
        # Load DM files
        self._cache['dm'] = {}
        for dm_file in self.template_dir.rglob('*.dm'):
            with open(dm_file, 'rb') as f:
                self._cache['dm'][dm_file.name] = f.read()

        # Load XML files
        self._cache['xml'] = {}
        for xml_file in self.template_dir.rglob('*.xml'):
            with open(xml_file, 'rb') as f:
                self._cache['xml'][xml_file.name] = f.read()

    def get_dm_content(self, filename=None):
        """Get content for a .dm file, either specific or random"""
        if not self._cache['dm']:
            return os.urandom(10 * 1024)  # Fallback to random if no templates

        if filename and filename in self._cache['dm']:
            return self._cache['dm'][filename]
        return random.choice(list(self._cache['dm'].values()))

    def get_xml_content(self, filename=None):
        """Get content for an .xml file, either specific or random"""
        if not self._cache['xml']:
            root = ET.Element("MicroscopeImage")
            ET.SubElement(root, "Timestamp").text = time.strftime("%Y-%m-%d %H:%M:%S")
            return ET.tostring(root)

        if filename and filename in self._cache['xml']:
            return self._cache['xml'][filename]
        return random.choice(list(self._cache['xml'].values()))


def create_epu_structure(base_dir: Path, templates: EPUTemplates, verbose: bool = False):
    if verbose:
        console.print(f"[blue]Creating EPU structure in {base_dir}[/blue]")

    # Create EpuSession.dm
    (base_dir / "EpuSession.dm").write_bytes(templates.get_dm_content("EpuSession.dm"))

    # Create Images-Disc directories
    for i in range(random.randint(1, 2)):
        disc_dir = base_dir / f"Images-Disc{i + 1}"
        disc_dir.mkdir(exist_ok=True)

        for j in range(random.randint(1, 3)):
            grid_dir = disc_dir / f"GridSquare_{random.randint(8999000, 8999999)}"
            grid_dir.mkdir(exist_ok=True)

            # Create GridSquare files
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            grid_xml = f"GridSquare_{timestamp}.xml"
            (grid_dir / grid_xml).write_bytes(templates.get_xml_content())

            # Create metadata
            metadata_dir = base_dir / "Metadata"
            metadata_dir.mkdir(exist_ok=True)
            (metadata_dir / f"{grid_dir.name}.dm").write_bytes(templates.get_dm_content())

            # Create FoilHoles directory
            foil_dir = grid_dir / "FoilHoles"
            foil_dir.mkdir(exist_ok=True)

            # Create Data directory
            data_dir = grid_dir / "Data"
            data_dir.mkdir(exist_ok=True)

            # Create foil hole files
            for k in range(random.randint(1, 3)):
                foil_id = random.randint(9015000, 9029999)
                timestamp = time.strftime("%Y%m%d_%H%M%S")

                # FoilHoles files
                foil_xml = f"FoilHole_{foil_id}_{timestamp}.xml"
                (foil_dir / foil_xml).write_bytes(templates.get_xml_content())

                # Data files
                data_timestamp = time.strftime("%Y%m%d_%H%M%S")
                for data_suffix in range(2):
                    data_xml = f"FoilHole_{foil_id}_Data_9017{347 + data_suffix}_{k + 1}_{data_timestamp}.xml"
                    (data_dir / data_xml).write_bytes(templates.get_xml_content())


def create_random_structure(directory: Path, verbose: bool = False):
    if verbose:
        console.print(f"[blue]Creating random files in {directory}[/blue]")
    num_files = random.randint(1, 5)
    for _ in range(num_files):
        file_path = directory / f"random_{random_string()}.txt"
        file_path.write_bytes(os.urandom(random.randint(1, 100) * 1024))


def test_filesystem_changes(
        directory: Path = typer.Argument(..., help="Test directory to create and modify files in"),
        template_dir: Path = typer.Option(None, "--template-dir", "-t",
                                          help="Directory containing template files"),
        duration: int = typer.Option(60, "--duration", "-d",
                                     help="Test duration in seconds"),
        interval: float = typer.Option(0.1, "--interval", "-i",
                                       help="Interval between changes in seconds"),
        seed: int | None = typer.Option(None, "--seed", "-s",
                                        help="Random seed for reproducible tests"),
        verbose: bool = typer.Option(False, "--verbose", "-v",
                                     help="Show detailed progress"),
        dry_run: bool = typer.Option(False, "--dry-run",
                                     help="Show what would be done without making changes")
):
    """
    Generate test data simulating EPU microscope file changes.
    Creates and modifies both EPU-specific files (.dm, .xml) and random files.
    Uses template files from the specified template directory if provided.
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

    templates = EPUTemplates(template_dir) if template_dir else None

    create_epu_structure(directory, templates, verbose)
    create_random_structure(directory, verbose)

    actions = ['modify_epu', 'modify_random', 'create_epu', 'create_random', 'delete_random']

    with console.status("[bold green]Running file system changes...") as status:
        end_time = time.time() + duration
        while time.time() < end_time:
            action = random.choice(actions)
            if verbose:
                console.print(f"[dim]Action: {action}[/dim]")

            if action == 'modify_epu':
                epu_files = list(directory.glob('**/*.dm')) + list(directory.glob('**/*.xml'))
                if epu_files:
                    file_to_modify = random.choice(epu_files)
                    content = (templates.get_dm_content() if file_to_modify.suffix == '.dm'
                               else templates.get_xml_content())
                    with open(file_to_modify, 'wb') as f:
                        f.write(content)

            elif action == 'modify_random':
                random_files = list(directory.glob('**/*.txt'))
                if random_files:
                    file_to_modify = random.choice(random_files)
                    with open(file_to_modify, 'ab') as f:
                        f.write(os.urandom(random.randint(1, 100) * 1024))

            elif action == 'create_epu':
                create_epu_structure(directory, templates, verbose)

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