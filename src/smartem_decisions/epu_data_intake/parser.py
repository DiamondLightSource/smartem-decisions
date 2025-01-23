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


@dataclass
class MicrographManifest:
    acquisition_datetime: datetime
    magnification: float
    defocus: float
    pixel_size: float
    dose_rate: float
    dose: float
    exposure_time: float
    detector_name: str
    acceleration_voltage: int
    spherical_aberration: Optional[float]
    energy_filter: bool
    phase_plate: bool
    beam_shift_x: float
    beam_shift_y: float
    beam_tilt_x: float
    beam_tilt_y: float
    image_size_x: int
    image_size_y: int
    binning_x: int
    binning_y: int
    number_of_fractions: Optional[int]
    super_resolution_factor: int
    electron_counting: bool


@dataclass
class MicrographData:
    id: str
    gridsquare_id: str
    foilhole_id: str
    manifest_file: Path
    manifest: MicrographManifest


@dataclass
class FoilHoleData:
    id: str
    gridsquare_id: str
    files: dict = field(default_factory=lambda: {"foilholes_dir": [], "data_dir": []})


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


class EpuParser:
    DEBUG = False
    root_dir: Path
    imagedisc_dirs: List[Path]
    epu_session: EPUSessionData
    gridsquares = dict()  # indexed by gridsquare_id: str, contains GridSquareData objects
    foilholes = dict()  # indexed by foilhole_id: str, contains FoilHoleData objects
    micrographs = dict() # indexed by micrograph_id: str, if such a thing exists?


    def __init__(self, path):
        self.root_dir = Path(path)

        # Find all Images-Disc directories
        self.imagedisc_dirs = sorted([
            self.root_dir / Path(d.name) for d in self.root_dir.iterdir()
            if d.is_dir() and d.name.startswith('Images-Disc')
        ])


    def print_summary(self):
        print(f"\nEPU Session Summary")
        print(f"==================")
        print(f"Session Name: {self.epu_session.name}")
        print(f"Session ID: {self.epu_session.id}")
        print(f"Start Time: {self.epu_session.start_time}")
        print(f"Root directory: {self.root_dir}")

        # TODO
        # print("\nAcquisition Settings:")
        # for mode, settings in self.epu_session.acquisition_settings.items():
        #     print(f"  {mode}:")
        #     for key, value in settings.items():
        #         print(f"    {key}: {value}")
        print(f"\nSession Statistics:")
        print(f"  Total Grid Squares: {len(self.gridsquares)}")
        print(f"  Active Grid Squares: {sum(1 for gs in self.gridsquares.values() if gs.is_active)}")
        print(f"  Total Foil Holes: {len(self.foilholes)}")
        print(f"  Total Micrographs: {len(self.micrographs)}")

        print(f"\nMicrographs info")
        print(f"==================")
        pprint(self.micrographs)


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

        # Parse GridSquare IDs from `/Metadata` directory files.
        for file_path in metadata_gridsquare_files:
            match = dm_file_pattern.search(file_path.name)
            if match:
                self.gridsquares[match.group(1)] = GridSquareData(
                    id = match.group(1),
                    is_active = False,
                )

        # TODO simplify finding gridsquare dir to a one-liner glob
        # Find all GridSquare_<id> dirs under `/Images-Disc*` dirs
        for disc_dir in self.imagedisc_dirs:
            if not disc_dir.is_dir():
                continue

            # Look for `GridSquare_*` directories in each disc dir
            for gridsquare_dir in disc_dir.glob("GridSquare_*"):
                if not gridsquare_dir.is_dir():
                    continue

                match = dir_pattern.search(gridsquare_dir.name)
                if match:
                    gridsquare_id = match.group(1)
                    self.gridsquares[gridsquare_id].is_active = True
                    self.gridsquares[gridsquare_id].data_dir = gridsquare_dir
                    self.gridsquares[gridsquare_id].manifest = self.parse_gridsquare_manifest(gridsquare_id)
                    self.scan_foilholes(gridsquare_id, gridsquare_dir)


    def parse_gridsquare_manifest(self, gridsquare_id: str) -> GridSquareManifest:
        manifest_path = next(self.root_dir.glob(f"Images-Disc*/GridSquare_{gridsquare_id}/GridSquare_*.xml"))
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
        self.DEBUG and print(f"\n Scanning square {gridsquare_id} for foilholes...")
        self.DEBUG and print(f"  GridSquare dir: {gridsquare_dir}")
        # Check for required subdirectories
        gridsquare_data_dir = gridsquare_dir / "Data"
        gridsquare_foilholes_dir = gridsquare_dir / "FoilHoles"
        if not gridsquare_data_dir.is_dir():
            self.DEBUG and print(f"  Missing required directory: {gridsquare_data_dir}, skipping")
            return
        if not gridsquare_foilholes_dir.is_dir():
            self.DEBUG and print(f"  Missing required directory: {gridsquare_foilholes_dir}, skipping")
            return
        self.DEBUG and print(f"  Data dir: {gridsquare_data_dir}")
        self.DEBUG and print(f"  FoilHoles dir: {gridsquare_foilholes_dir}")

        # Scan `/FoilHoles` directory for initial foilhole metadata
        # TODO grab timestamp from the filename?
        foilhole_pattern = re.compile(r'FoilHole_(\d+)_(\d+)_(\d+)\.xml$')
        for xml_file in gridsquare_foilholes_dir.glob("*.xml"):
            match = foilhole_pattern.search(xml_file.name)
            if match:
                foilhole_id = match.group(1)
                if foilhole_id not in self.foilholes:
                    self.foilholes[foilhole_id] = FoilHoleData(
                        id = foilhole_id,
                        gridsquare_id = gridsquare_id,
                        files = {"foilholes_dir": [], "data_dir": [],}
                    )
                self.foilholes[foilhole_id].files["foilholes_dir"].append(xml_file.name)
                # TODO between multiple files relating to the same foilhole keep latest one as
                #   encoded by timestamp in filename,
                #   e.g. between `FoilHole_9016620_20250108_181906.xml` and `FoilHole_9016620_20250108_181916.xml`
                #   pick the latter.

        # Scan `/Data` directory for detailed acquisition data
        # TODO consider removing this logic as it is actually micrograph scanning logic not foilhole scanning
        # TODO grab timestamp from the filename?
        # TODO grab foilhole_zone_id from filename? (This is `match.group(2)`)
        data_pattern = re.compile(r'FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$')
        for xml_file in gridsquare_data_dir.glob("*.xml"):
            match = data_pattern.search(xml_file.name)
            if match:
                foilhole_id = match.group(1)
                if foilhole_id not in self.foilholes:
                    self.foilholes[foilhole_id] = FoilHoleData(
                        id=foilhole_id,
                        gridsquare_id=gridsquare_id,
                        files={"foilholes_dir": [], "data_dir": [], }
                    )
                self.foilholes[foilhole_id].files["data_dir"].append(xml_file.name)
                self.scan_micrographs(gridsquare_id, foilhole_id)

        # TODO rewrite this note, these files are actually micrographs
        # Note: here `match.group(2)` is the ID that tells us where in the foil hole the image was captured.
        # We should see it repeating across different foil holes. For that reason we keep all of these files.
        # pprint(self.foil_holes[foilhole_id])


    def scan_micrographs(self, gridsquare_id: str, foilhole_id: str):
        # there is one file in data_dir per micrograph, so the unique combinations of foil hole and position in foil hole
        micrograph_manifest_paths = list(
            self.root_dir.glob(
                f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_{foilhole_id}_Data_*_*_*_*.xml"
            )
        )
        self.DEBUG and pprint(micrograph_manifest_paths)
        for micrograph_path in micrograph_manifest_paths:
            micrograph_id, micrograph_manifest = self.parse_micrograph_manifest(micrograph_path)
            self.micrographs[micrograph_id] = MicrographData(
                id = micrograph_id,
                gridsquare_id = gridsquare_id,
                foilhole_id = foilhole_id,
                manifest_file = micrograph_path,
                manifest = micrograph_manifest,
            )

    def parse_micrograph_manifest(self, path: Path) -> tuple[str, MicrographManifest]:
        """Parse EPU micrograph metadata XML file.

        Args:
            path (Path): Path to the XML metadata file

        Returns:
            tuple[str, MicrographManifest]: Tuple of (micrograph_id, metadata)
        """
        tree = ET.parse(path)
        root = tree.getroot()

        ns = {
            'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
            'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
        }

        def get_custom_value(key: str, default=None):
            custom_data = root.find('.//ms:CustomData', ns)
            if custom_data is None:
                return default
            for item in custom_data.findall('.//arr:KeyValueOfstringanyType', ns):
                if item.find('arr:Key', ns).text == key:
                    value_elem = item.find('arr:Value', ns)
                    return value_elem.text if value_elem is not None else default
            return default

        def safe_find_text(xpath: str, parent=root, default=None):
            elem = parent.find(xpath, ns)
            return elem.text if elem is not None else default

        def safe_float(xpath: str, parent=root, default=0.0):
            try:
                value = safe_find_text(xpath, parent)
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        def safe_int(xpath: str, parent=root, default=0):
            try:
                value = safe_find_text(xpath, parent)
                return int(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        def safe_bool(value: str, default=False):
            if value is None:
                return default
            return value.lower() == 'true'

        # Extract camera settings
        camera = root.find('.//ms:camera', ns)
        if camera is None:
            raise ValueError(f"No camera data found in {path}")

        binning = camera.find('.//ms:Binning', ns)
        readout_area = camera.find('.//ms:ReadoutArea', ns)

        # Extract camera specific settings safely
        camera_specific = {}
        for item in camera.findall('.//ms:CameraSpecificInput/arr:KeyValueOfstringanyType', ns):
            key = safe_find_text('arr:Key', item)
            if key:
                value_elem = item.find('arr:Value', ns)
                camera_specific[key] = value_elem.text if value_elem is not None else None

        # Get number of fractions if available
        n_fractions = None
        fractionation = camera_specific.get('FractionationSettings')
        if fractionation and 'NumberOffractions' in fractionation:
            try:
                n_fractions = int(fractionation.split('>')[1].split('<')[0])
            except (ValueError, IndexError):
                pass

        # Get micrograph ID
        micrograph_id = safe_find_text('.//ms:uniqueID', default='unknown')

        # Create MicrographManifest object with safe value extraction
        return micrograph_id, MicrographManifest(
            # TODO: `acquisition_datetime=datetime.datetime(2025, 1, 8, 23, 24, 58, 783791, tzinfo=datetime.timezone.utc),`
            #   what's "783791" - debug?
            acquisition_datetime=datetime.fromisoformat(
                safe_find_text('.//ms:acquisitionDateTime', default='1970-01-01T00:00:00+00:00').replace('Z', '+00:00')
            ),
            magnification=safe_float('.//ms:TemMagnification/ms:NominalMagnification'),
            defocus=safe_float('.//ms:optics/ms:Defocus'),
            pixel_size=safe_float('.//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue'),
            dose_rate=float(get_custom_value('DoseRate', '0.0')),
            dose=float(get_custom_value('Dose', '0.0')),
            exposure_time=safe_float('.//ms:ExposureTime', camera),
            detector_name=get_custom_value('DetectorCommercialName', 'Unknown'),
            acceleration_voltage=safe_int('.//ms:gun/ms:AccelerationVoltage'),
            spherical_aberration=None,
            energy_filter=safe_bool(safe_find_text('.//ms:optics/ms:EFTEMOn')),
            phase_plate=safe_bool(get_custom_value('PhasePlateUsed', 'false')),
            beam_shift_x=safe_float('.//ms:optics/ms:BeamShift/ms:_x'),
            beam_shift_y=safe_float('.//ms:optics/ms:BeamShift/ms:_y'),
            beam_tilt_x=safe_float('.//ms:optics/ms:BeamTilt/ms:_x'),
            beam_tilt_y=safe_float('.//ms:optics/ms:BeamTilt/ms:_y'),
            image_size_x=safe_int('ms:width', readout_area) if readout_area is not None else 0,
            image_size_y=safe_int('ms:height', readout_area) if readout_area is not None else 0,
            binning_x=safe_int('ms:x', binning) if binning is not None else 1,
            binning_y=safe_int('ms:y', binning) if binning is not None else 1,
            number_of_fractions=n_fractions,
            super_resolution_factor=int(camera_specific.get('SuperResolutionFactor', '1')),
            electron_counting=safe_bool(camera_specific.get('ElectronCountingEnabled', 'false')),
        )

epu_parser_cli = typer.Typer()


@epu_parser_cli.command()
def validate(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Validate dataset directory structure
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
def parse(epu_dir: str = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"):
    """Parse entire session dataset and print summary
    """
    acq = EpuParser(epu_dir)
    acq.parse_epu_manifest()
    acq.scan_gridsquares() # triggers scan_foilholes() and scan_micrographs() internally

    # acq.scan_micrographs("8999138", "9015883")

    acq.print_summary()
    pass


if __name__ == "__main__":
    epu_parser_cli()
