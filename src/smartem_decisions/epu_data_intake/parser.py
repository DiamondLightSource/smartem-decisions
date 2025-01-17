#!/usr/bin/env python

import re
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pprint import pprint
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import typer

epu_parser_cli = typer.Typer()

@dataclass
class FoilHoleData:
    id: str


@dataclass
class GridSquareManifest:
    acquisition_datetime: datetime
    defocus: float  # in meters
    magnification: float
    dose_rate: float  # e⁻/Å²/s
    dose: float  # total dose
    exposure_time: float  # seconds
    pixel_size: float  # in meters
    beam_shift_x: float
    beam_shift_y: float
    detector_name: str
    applied_defocus: float
    data_dir: Optional[Path] = None


@dataclass
class GridSquareData:
    id: str
    is_active: bool  # Does additional data exist for this GridSquare under `/Images-Disc<n>`
    data_dir: Optional[Path] = None
    manifest: Optional[GridSquareManifest] = None


@dataclass
class EPUSessionData:
    name: str
    id: str
    start_time: datetime
    # acquisition_settings: Dict[str, dict] = field(
    #     default_factory=dict)  # Settings for different modes like Acquisition, AutoFocus etc.
    # storage_folders: List[str] = field(default_factory=list)


class XMLNamespaceManager:
    """Helper class to handle XML namespaces in EPU files"""
    def __init__(self, root):
        self.namespaces = {
            'ns': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
            'types': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types'
        }
        # Add any additional namespaces found in the document
        for key, value in root.attrib.items():
            if key.startswith('xmlns:'):
                ns_name = key.split(':')[1]
                self.namespaces[ns_name] = value

    def find(self, element, path):
        """Find element using proper namespace"""
        for ns in self.namespaces.values():
            try:
                # Try with each namespace
                elem = element.find(f".//{{{ns}}}{path}")
                if elem is not None:
                    return elem
            except ET.ParseError:
                continue
        return None


def get_dir_tree(target_dir: str, prefix = ""):
    output = []
    path = Path(target_dir)
    items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        output.append(f"{prefix}{connector}{item.name}")
        if item.is_dir():
            extension = "    " if is_last else "│   "
            output.extend(
                get_dir_tree(item, prefix + extension)
            )
    return output


class EpuParser:
    root_dir: Path
    imagedisc_dirs: List[Path]
    epu_session: EPUSessionData
    grid_squares = dict()  # indexed by gridsquare_id: str, contains GridSquareData objects
    foil_holes = dict()  # indexed by foilhole_id: str, contains FoilHoleData objects


    def __init__(self, path):
        self.root_dir = Path(path)

        # Find all Images-Disc directories
        self.imagedisc_dirs = sorted([
            self.root_dir / Path(d.name) for d in self.root_dir.iterdir()
            if d.is_dir() and d.name.startswith('Images-Disc')
        ])

        # List all GridSquare IDs
        # self.all_grid_square_ids = self.parse_metadata_dir()
        # print(self.all_grid_square_ids)

        # List active GridSquare IDs
        # self.active_grid_square_ids, self.active_gridsquare_paths = self.parse_active_gridsquares()
        # for grid_id, grid_path in zip(self.active_grid_square_ids, self.active_gridsquare_paths):
        #     print(f"GridSquare {grid_id} is located at {grid_path}")
        #     is_valid, errors = self.parse_gridsquare_dir(grid_id)
        #     if is_valid:
        #         print(f"GridSquare {grid_id} directory structure is valid")
        #     else:
        #         print(f"GridSquare {grid_id} directory structure is invalid:")
        #         for error in errors:
        #             print(f"  - {error}")


    def validate_dir(self) -> tuple[bool, list[str]]:
        """
        Validates the EPU acquisition directory structure.

        Returns:
            tuple: (is_valid: bool, errors: list[str])
            - is_valid: True if all checks pass, False otherwise
            - errors: List of error messages if any checks fail
        """
        errors = []

        # 1. Check for `/EpuSession.dm` file
        epu_session_path = self.root_dir / "EpuSession.dm"
        if not epu_session_path.is_file():
            errors.append("Missing required file: EpuSession.dm")

        # 2. Check for `/Metadata` directory
        metadata_path = self.root_dir / "Metadata"
        if not metadata_path.is_dir():
            errors.append("Missing required directory: Metadata")

        # 3. Check for `/Images-Disk*` directories (at least `/Images-Disc1`)
        if not self.imagedisc_dirs:
            errors.append("No Images-Disc directories found. At least Images-Disc1 should exist.")
        else:
            # Validate the format of Images-Disk directories
            for dir_path in self.imagedisc_dirs:
                if not dir_path.is_dir():
                    continue

                # Check if the directory name matches the expected pattern
                match = re.match(r"Images-Disc(\d+)$", dir_path.name)
                if not match:
                    errors.append(f"Invalid directory name format: {dir_path.name}")
                    continue

                # Verify the disk numbers are valid integers
                try:
                    disk_num = int(match.group(1))
                    if disk_num < 1:
                        errors.append(f"Invalid disk number in {dir_path.name}: must be >= 1")
                except ValueError:
                    errors.append(f"Invalid disk number format in {dir_path.name}")

        return len(errors) == 0, errors


    def parse_epu_manifest(self):
        """
        Parse `/EpuSession.dm` manifest
        TODO parse out more types of information out of the root XML files
        """
        epu_session_file = self.root_dir / 'EpuSession.dm'
        tree = ET.parse(epu_session_file)
        root = tree.getroot()

        # Initialize namespace manager
        ns_mgr = XMLNamespaceManager(root)

        # Extract basic session info
        session_name = ns_mgr.find(root, 'Name').text
        session_id = ns_mgr.find(root, 'Id').text
        start_time_str = ns_mgr.find(root, 'StartDateTime').text
        self.epu_session = EPUSessionData(
            name = session_name,
            id = session_id,
            start_time = datetime.fromisoformat(start_time_str.rstrip('Z'))
        )


    def scan_gridsquares(self):
        metadata_path = self.root_dir / "Metadata"
        metadata_gridsquare_files = metadata_path.glob("GridSquare_*.dm")
        dm_file_pattern = re.compile(r"GridSquare_(\d+)\.dm$")
        dir_pattern = re.compile(r"GridSquare_(\d+)$")

        # Parse GridSquare IDs from metadata directory files.
        for file_path in metadata_gridsquare_files:
            match = dm_file_pattern.search(file_path.name)
            if match:
                self.grid_squares[match.group(1)] = GridSquareData(
                    id = match.group(1),
                    is_active = False,
                )

        # TODO simplify finding gridsquare dir to a one-liner glob
        # Find all GridSquare_<id> dirs under Images-Disc* dirs
        for disc_dir in self.imagedisc_dirs:
            if not disc_dir.is_dir():
                continue

            # Look for GridSquare_* directories in each disc dir
            for gridsquare_dir in disc_dir.glob("GridSquare_*"):
                if not gridsquare_dir.is_dir():
                    continue

                match = dir_pattern.search(gridsquare_dir.name)
                if match:
                    gridsquare_id = match.group(1)
                    self.grid_squares[gridsquare_id].is_active = True
                    self.grid_squares[gridsquare_id].data_dir = gridsquare_dir
                    self.grid_squares[gridsquare_id].manifest = self.parse_gridsquare_manifest(gridsquare_id)
                    self.scan_foilholes(gridsquare_id, gridsquare_dir)


    def parse_gridsquare_manifest(self, gridsquare_id: str) -> GridSquareManifest:
        manifest_path = next(self.root_dir.glob(f"Images-Disc*/GridSquare_{gridsquare_id}/GridSquare_*.xml"))
        # print(f"\n\n Parsing {manifest_path}..")

        manifest_tree = ET.parse(manifest_path)
        root = manifest_tree.getroot()

        ns = {
            'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
            'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
        }

        custom_data = root.find('.//ms:CustomData', ns)
        optics = root.find('.//ms:optics', ns)
        acquisition = root.find('.//ms:acquisition', ns)
        spatial_scale = root.find('.//ms:SpatialScale', ns)

        def get_custom_value(key: str, default=None):
            for item in custom_data.findall('.//arr:KeyValueOfstringanyType', ns):
                if item.find('arr:Key', ns).text == key:
                    value_elem = item.find('arr:Value', ns)
                    return value_elem.text if value_elem is not None else default
            return default

        def safe_float(element_path, parent_elem, default=0.0):
            elem = parent_elem.find(element_path, ns)
            try:
                return float(elem.text) if elem is not None and elem.text else default
            except (ValueError, AttributeError):
                return default

        acq_datetime = datetime.fromisoformat(
            acquisition.find('.//ms:acquisitionDateTime', ns).text.replace('Z', '+00:00')
        )

        pixel_size = safe_float('.//ms:pixelSize/ms:x/ms:numericValue', spatial_scale)

        beam_shift_x = safe_float('.//ms:BeamShift/ms:_x', optics)
        beam_shift_y = safe_float('.//ms:BeamShift/ms:_y', optics)

        return GridSquareManifest(
            acquisition_datetime=acq_datetime,
            defocus=safe_float('.//ms:Defocus', optics),
            magnification=safe_float('.//ms:TemMagnification/ms:NominalMagnification', optics),
            dose_rate=float(get_custom_value('DoseRate', '0.0')),
            dose=float(get_custom_value('Dose', '0.0')),
            exposure_time=safe_float('.//ms:camera/ms:ExposureTime', acquisition),
            pixel_size=pixel_size,
            beam_shift_x=beam_shift_x,
            beam_shift_y=beam_shift_y,
            detector_name=get_custom_value('DetectorCommercialName', 'Unknown'),
            applied_defocus=float(get_custom_value('AppliedDefocus', '0.0')),
            data_dir=manifest_path.parent
        )


    def scan_foilholes(self, gridsquare_id: str, gridsquare_dir: Path):
        print(f"\n Scanning square {gridsquare_id} for foilholes...")
        print(f"  GridSquare dir: {gridsquare_dir}")
        # TODO establish what the relationship is between `/FoilHoles` and `/Data`
        # Check for required subdirectories
        gridsquare_data_dir = gridsquare_dir / "Data"
        gridsquare_foilholes_dir = gridsquare_dir / "FoilHoles"
        if not gridsquare_data_dir.is_dir():
            print(f"  Missing required directory: {gridsquare_data_dir}, skipping")
            return
        if not gridsquare_foilholes_dir.is_dir():
            print(f"  Missing required directory: {gridsquare_foilholes_dir}, skipping")
            return
        print(f"  Data dir: {gridsquare_data_dir}")
        print(f"  FoilHoles dir: {gridsquare_foilholes_dir}")

        # Scan `/FoilHoles` directory for initial foilhole metadata
        # TODO grab timestamp from the filename?
        # foilhole_pattern = re.compile(r'FoilHole_(\d+)_(\d+)_(\d+)\.xml$')
        # for xml_file in gridsquare_foilholes_dir.glob("*.xml"):
        #     match = foilhole_pattern.search(xml_file.name)
        #     if match:
        #         foilhole_id = match.group(1)
        #         if foilhole_id not in self.foil_holes:
        #             self.foil_holes[foilhole_id] = FoilHoleData(
        #                 id = foilhole_id,
        #             )
        #         else:
        #             print(f"  !!! found duplicate foilhole file: {xml_file}")

        # Scan `/Data` directory for detailed acquisition data
        # TODO grab timestamp from the filename?
        data_pattern = re.compile(r'FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$')
        for xml_file in gridsquare_data_dir.glob("*.xml"):
            match = data_pattern.search(xml_file.name)
            if match:
                foilhole_id = match.group(1)

                if foilhole_id not in self.foil_holes:
                    self.foil_holes[foilhole_id] = FoilHoleData(
                        id=foilhole_id,
                    )
                else:
                    print(f"  !!! found duplicate foilhole file: {xml_file}")


@epu_parser_cli.command()
def validate(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Validate directory structure
    """
    acq = EpuParser(epu_dir)
    is_valid, errors = acq.validate_dir()
    print(f"\nValidating EPU dir: {epu_dir}")
    if is_valid:
        print("✓ Directory structure is valid")
    else:
        print("✗ Directory structure is invalid:")
        for error in errors:
            print(f"  - {error}")


@epu_parser_cli.command()
def parse_session(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Parse `EpuSession.dm`
    """
    acq = EpuParser(epu_dir)
    acq.parse_epu_manifest()
    pprint(acq.epu_session)
    pass


@epu_parser_cli.command()
def parse_gridsquares(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Parse grid squares
    """
    acq = EpuParser(epu_dir)
    acq.scan_gridsquares()
    pprint(acq.grid_squares)


@epu_parser_cli.command()
def parse_foilholes(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Parse foil holes
    """
    acq = EpuParser(epu_dir)
    # acq.scan_gridsquares()
    # for gridsquare in acq.grid_squares:
    #     if gridsquare.is_active:
    #         acq.scan_foilholes(gridsquare.id, gridsquare.data_dir)
    acq.scan_foilholes(
        str(8999138),
        Path("../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU/Images-Disc1/GridSquare_8999138")
    )
    pprint(acq.foil_holes)

@epu_parser_cli.command()
def tree(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    output = get_dir_tree(epu_dir)
    print("\n".join(output))


if __name__ == "__main__":
    epu_parser_cli()
