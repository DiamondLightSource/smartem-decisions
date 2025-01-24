import os
import random
import time
import string
from pathlib import Path
import shutil


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_content(size_kb=1):
    return os.urandom(size_kb * 1024)


def create_random_structure(directory, max_depth=3, current_depth=0):
    if current_depth >= max_depth:
        return

    num_dirs = random.randint(0, 3)
    num_files = random.randint(1, 5)

    dir_path = Path(directory)

    # Create files
    for _ in range(num_files):
        file_path = dir_path / f"file_{random_string()}.txt"
        file_path.write_bytes(random_content(random.randint(1, 100)))

    # Create and populate subdirectories
    for _ in range(num_dirs):
        new_dir = dir_path / f"dir_{random_string()}"
        new_dir.mkdir(exist_ok=True)
        create_random_structure(new_dir, max_depth, current_depth + 1)


def test_filesystem_changes(directory, duration=60, interval=0.5):
    test_dir = Path(directory)
    test_dir.mkdir(exist_ok=True)

    end_time = time.time() + duration

    while time.time() < end_time:
        action = random.choice(['create_file', 'create_dir', 'modify', 'delete', 'create_nested'])

        if action == 'create_file':
            target_dir = random.choice(list(test_dir.glob('**')))
            file_path = target_dir / f"file_{random_string()}.txt"
            file_path.write_bytes(random_content(random.randint(1, 100)))

        elif action == 'create_dir':
            target_dir = random.choice(list(test_dir.glob('**')))
            dir_path = target_dir / f"dir_{random_string()}"
            dir_path.mkdir(exist_ok=True)

        elif action == 'create_nested':
            target_dir = random.choice(list(test_dir.glob('**')))
            create_random_structure(target_dir, max_depth=2)

        elif action == 'modify':
            files = list(test_dir.glob('**/*.txt'))
            if files:
                file_to_modify = random.choice(files)
                file_to_modify.write_bytes(random_content(random.randint(1, 100)))

        elif action == 'delete':
            items = list(test_dir.glob('**/*'))
            if items:
                to_delete = random.choice(items)
                if to_delete != test_dir:  # Don't delete root test directory
                    if to_delete.is_file():
                        to_delete.unlink()
                    else:
                        shutil.rmtree(to_delete)

        time.sleep(interval)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python test_script.py <test_directory>")
        sys.exit(1)

    test_filesystem_changes(sys.argv[1])