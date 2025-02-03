import os
import random
import time
import string
from pathlib import Path
import xml.etree.ElementTree as ET


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_content(size_kb=1):
    return os.urandom(size_kb * 1024)


def create_xml_content():
    root = ET.Element("MicroscopeImage")
    ET.SubElement(root, "Timestamp").text = time.strftime("%Y-%m-%d %H:%M:%S")
    return ET.tostring(root)


def create_dm_content():
    return random_content(10)  # Simple binary content for .dm files


def create_epu_structure(base_dir):
    base_path = Path(base_dir)

    # Create EpuSession.dm
    (base_path / "EpuSession.dm").write_bytes(create_dm_content())

    # Create Sample directories
    for i in range(random.randint(1, 3)):
        sample_dir = base_path / f"Sample{i + 1}"
        sample_dir.mkdir(exist_ok=True)

        # Sample.dm
        (sample_dir / "Sample.dm").write_bytes(create_dm_content())

        # Atlas structure
        atlas_dir = sample_dir / "Atlas"
        atlas_dir.mkdir(exist_ok=True)
        (atlas_dir / "Atlas.dm").write_bytes(create_dm_content())

    # Create Images-Disc directories
    for i in range(random.randint(1, 2)):
        disc_dir = base_path / f"Images-Disc{i + 1}"
        disc_dir.mkdir(exist_ok=True)

        # Create GridSquare directories
        for j in range(random.randint(1, 3)):
            grid_dir = disc_dir / f"GridSquare_{j + 1}"
            grid_dir.mkdir(exist_ok=True)

            # GridSquare XML and dm files
            (grid_dir / f"GridSquare_{j + 1}_{random.randint(1, 100)}.xml").write_bytes(create_xml_content())
            (base_path / "Metadata" / f"GridSquare_{j + 1}.dm").write_bytes(create_dm_content())

            # FoilHoles structure
            foil_dir = grid_dir / "FoilHoles"
            foil_dir.mkdir(exist_ok=True)
            for k in range(random.randint(1, 3)):
                (foil_dir / f"FoilHole_{k + 1}_{random.randint(1, 100)}_{random.randint(1, 100)}.xml").write_bytes(
                    create_xml_content())

            # Data structure
            data_dir = grid_dir / "Data"
            data_dir.mkdir(exist_ok=True)
            for k in range(random.randint(1, 3)):
                (
                            data_dir / f"FoilHole_{k + 1}_Data_{random.randint(1, 100)}_{random.randint(1, 100)}_{random.randint(1, 100)}_{random.randint(1, 100)}.xml").write_bytes(
                    create_xml_content())


def create_random_structure(directory):
    """Creates random files that don't match EPU patterns"""
    dir_path = Path(directory)

    num_files = random.randint(1, 5)
    for _ in range(num_files):
        file_path = dir_path / f"random_{random_string()}.txt"
        file_path.write_bytes(random_content(random.randint(1, 100)))


def test_filesystem_changes(directory, duration=60, interval=1.0):
    test_dir = Path(directory)
    test_dir.mkdir(exist_ok=True)
    (test_dir / "Metadata").mkdir(exist_ok=True)

    # Initial EPU structure
    create_epu_structure(test_dir)
    create_random_structure(test_dir)

    end_time = time.time() + duration

    while time.time() < end_time:
        action = random.choice([
            'modify_epu', 'modify_random',
            'create_epu', 'create_random',
            'delete_random'
        ])

        if action == 'modify_epu':
            # Modify an existing EPU file
            epu_files = list(test_dir.glob('**/*.dm')) + list(test_dir.glob('**/*.xml'))
            if epu_files:
                file_to_modify = random.choice(epu_files)
                content = create_dm_content() if file_to_modify.suffix == '.dm' else create_xml_content()
                file_to_modify.write_bytes(content)

        elif action == 'modify_random':
            # Modify a random non-EPU file
            random_files = list(test_dir.glob('**/*.txt'))
            if random_files:
                file_to_modify = random.choice(random_files)
                file_to_modify.write_bytes(random_content())

        elif action == 'create_epu':
            # Create new EPU structure
            create_epu_structure(test_dir)

        elif action == 'create_random':
            # Create new random files
            create_random_structure(test_dir)

        elif action == 'delete_random':
            # Delete random files
            random_files = list(test_dir.glob('**/*.txt'))
            if random_files:
                to_delete = random.choice(random_files)
                to_delete.unlink()

        time.sleep(interval)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python test_script.py <test_directory>")
        sys.exit(1)

    test_filesystem_changes(sys.argv[1])
