#!/usr/bin/env python
"""Setup script to handle version file copying and dotenv instantiation."""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info
from setuptools.command.install import install


def copy_version_files():
    """Copy src/_version.py to other package locations."""
    source_file = Path("src/_version.py")
    if not source_file.exists():
        print(f"Warning: {source_file} does not exist, nothing to copy")
        return

    target_files = [Path("src/smartem_decisions/_version.py"), Path("src/epu_data_intake/_version.py")]

    # Make sure target directories exist
    for target in target_files:
        target.parent.mkdir(parents=True, exist_ok=True)

    # Copy the file to each target location
    for target in target_files:
        shutil.copy2(source_file, target)
        print(f"Copied version file to {target}")


def copy_dotenv():
    """Copy .env.example to .env if .env doesn't exist."""
    source_file = Path(".env.example")
    target_file = Path(".env")

    if not source_file.exists():
        print(f"Warning: {source_file} does not exist, nothing to copy")
        return

    if target_file.exists():
        print(f"{target_file} already exists, skipping copy")
        return

    shutil.copy2(source_file, target_file)
    print(f"Copied {source_file} to {target_file}")


class CustomDevelop(develop):
    def run(self):
        develop.run(self)
        copy_version_files()
        copy_dotenv()


class CustomInstall(install):
    def run(self):
        install.run(self)
        copy_version_files()
        copy_dotenv()


class CustomEggInfo(egg_info):
    def run(self):
        egg_info.run(self)
        copy_version_files()
        copy_dotenv()


# Keep this minimal - config is in pyproject.toml
setup(
    name="smartem-decisions",  # Required for some setuptools versions
    cmdclass={
        "develop": CustomDevelop,
        "install": CustomInstall,
        "egg_info": CustomEggInfo,
    },
    # We're using pyproject.toml for the rest
)
