import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime


@dataclass
class FoilHole:
    id: str
    timestamp: datetime
    xml_path: str
    data_files: List[Dict[str, str]]  # List of pairs of jpg/xml paths

    @staticmethod
    def parse_timestamp(filename: str) -> datetime:
        """
        Parse timestamp from an EPU filename.
        Expected format is either YYYYMMDD_HHMMSS in filename or just HHMMSS for legacy timestamps.
        """
        # First try to find YYYYMMDD_HHMMSS pattern
        date_parts = filename.split('_')
        for part in date_parts:
            if len(part) == 8 and part.isdigit():  # YYYYMMDD
                # Look for the next part which should be HHMMSS
                idx = date_parts.index(part)
                if idx + 1 < len(date_parts) and len(date_parts[idx + 1]) >= 6:
                    time_part = date_parts[idx + 1][:6]  # Take first 6 chars in case there's more
                    if time_part.isdigit():
                        try:
                            return datetime.strptime(f"{part}_{time_part}", "%Y%m%d_%H%M%S")
                        except ValueError:
                            pass

        # If we can't find the full pattern, look for just HHMMSS
        for part in date_parts:
            if len(part) >= 6 and part[:6].isdigit():
                try:
                    return datetime.strptime(part[:6], "%H%M%S")
                except ValueError:
                    continue

        raise ValueError(f"Could not find timestamp in filename: {filename}")


@dataclass
class GridSquare:
    id: str
    metadata_path: str
    timestamp: datetime
    foil_holes: List[FoilHole]


@dataclass
class EPUSession:
    root_dir: str
    session_name: str
    session_id: str
    start_time: datetime
    grid_squares: List[GridSquare]
    image_discs: List[str]
    acquisition_settings: Dict[str, dict] = field(
        default_factory=dict)  # Settings for different modes like Acquisition, AutoFocus etc.
    storage_folders: List[str] = field(default_factory=list)


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


class GridSquareParser:
    def __init__(self, grid_square_dir: str, metadata_file: str):
        self.grid_square_dir = Path(grid_square_dir)
        self.metadata_file = Path(metadata_file)

    def parse(self) -> GridSquare:
        # Extract ID from directory name
        grid_square_id = self.grid_square_dir.name.split('_')[1]

        # Parse timestamp from GridSquare xml file
        xml_files = list(self.grid_square_dir.glob('GridSquare_*.xml'))
        timestamp = None
        if xml_files:
            try:
                timestamp = FoilHole.parse_timestamp(xml_files[0].stem)
            except ValueError:
                print(f"Warning: Could not parse timestamp from {xml_files[0].name}")
                timestamp = datetime.min

        # Parse FoilHoles
        foil_holes = []
        foil_holes_dir = self.grid_square_dir / 'FoilHoles'
        data_dir = self.grid_square_dir / 'Data'

        if foil_holes_dir.exists():
            # Group files by foil hole ID
            foil_hole_files = {}
            for file in foil_holes_dir.glob('FoilHole_*'):
                foil_id = file.name.split('_')[1]
                if foil_id not in foil_hole_files:
                    foil_hole_files[foil_id] = []
                foil_hole_files[foil_id].append(file)

            # Create FoilHole objects
            for foil_id, files in foil_hole_files.items():
                xml_files = [f for f in files if f.suffix == '.xml']
                if not xml_files:
                    continue

                try:
                    timestamp = FoilHole.parse_timestamp(xml_files[0].stem)
                except ValueError:
                    print(f"Warning: Could not parse timestamp from {xml_files[0].name}")
                    continue

                # Get associated data files
                data_files = []
                if data_dir.exists():
                    for data_file in data_dir.glob(f'FoilHole_{foil_id}_Data_*'):
                        base = data_file.stem
                        if data_file.suffix == '.xml':
                            jpg_path = data_file.with_suffix('.jpg')
                            if jpg_path.exists():
                                data_files.append({
                                    'xml': str(data_file),
                                    'jpg': str(jpg_path)
                                })

                foil_holes.append(FoilHole(
                    id=foil_id,
                    timestamp=timestamp,
                    xml_path=str(xml_files[0]),
                    data_files=data_files
                ))

        return GridSquare(
            id=grid_square_id,
            metadata_path=str(self.metadata_file),
            timestamp=timestamp if timestamp else datetime.min,
            foil_holes=foil_holes
        )


class EPUSessionParser:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def parse(self) -> EPUSession:
        # Validate directory structure
        epu_session_file = self.root_dir / 'EpuSession.dm'
        if not epu_session_file.exists():
            raise ValueError(f"No EpuSession.dm file found in {self.root_dir}")

        if not (self.root_dir / 'Metadata').is_dir():
            raise ValueError(f"No Metadata directory found in {self.root_dir}")

        # Parse EpuSession.dm
        tree = ET.parse(epu_session_file)
        root = tree.getroot()

        # Initialize namespace manager
        ns_mgr = XMLNamespaceManager(root)

        # Extract basic session info
        session_name = ns_mgr.find(root, 'Name').text
        session_id = ns_mgr.find(root, 'Id').text
        start_time_str = ns_mgr.find(root, 'StartDateTime').text
        start_time = datetime.fromisoformat(start_time_str.rstrip('Z'))

        # Extract storage folders
        storage_folders = []
        storage_folders_elem = ns_mgr.find(root, 'StorageFolders')
        if storage_folders_elem is not None:
            for folder_elem in storage_folders_elem.findall('.//*[Path]'):
                path_elem = ns_mgr.find(folder_elem, 'Path')
                if path_elem is not None and path_elem.text:
                    storage_folders.append(path_elem.text)

        # Find all Images-Disc directories
        image_discs = sorted([
            d.name for d in self.root_dir.iterdir()
            if d.is_dir() and d.name.startswith('Images-Disc')
        ])

        # Extract microscope settings for different modes
        acquisition_settings = {}
        microscope_settings = root.find('.//MicroscopeSettings')
        if microscope_settings is not None:
            print("DEBUG: Found MicroscopeSettings")
            # Find the KeyValuePairs array in microscope settings
            key_value_pairs = microscope_settings.findall(
                './/KeyValuePairOfExperimentSettingsIdMicroscopeSettingsCG2rZ1D8')
            print(f"DEBUG: Found {len(key_value_pairs)} key-value pairs")
            for pair in key_value_pairs:
                # Extract display name
                display_name = pair.find('.//DisplayName')
                if display_name is not None and display_name.text:
                    print(f"DEBUG: Found setting for {display_name.text}")
                    # Extract acquisition and optics details
                    exposure_time_elem = pair.find('.//ExposureTime')
                    defocus_elem = pair.find('.//Defocus')

                    settings_dict = {
                        'exposure_time': float(exposure_time_elem.text) if exposure_time_elem is not None else None,
                        'defocus': float(defocus_elem.text) if defocus_elem is not None else None,
                    }
                    acquisition_settings[display_name.text] = settings_dict

        # First, collect all grid squares from Metadata directory
        grid_squares = []
        metadata_dir = self.root_dir / 'Metadata'

        # Create a mapping of grid square ID to its metadata file
        metadata_files = {}
        for metadata_file in metadata_dir.glob('GridSquare_*.dm'):
            grid_square_id = metadata_file.stem.split('_')[1]
            metadata_files[grid_square_id] = metadata_file

        # Identify active grid squares (those that have a directory in any Images-DiscN)
        active_squares = set()  # Use a set to store just the IDs of active squares
        grid_square_dirs = {}  # Map IDs to their directories for active squares

        for disc_dir in image_discs:
            disc_path = self.root_dir / disc_dir
            for grid_square_dir in disc_path.iterdir():
                if grid_square_dir.is_dir() and grid_square_dir.name.startswith('GridSquare_'):
                    grid_square_id = grid_square_dir.name.split('_')[1]
                    active_squares.add(grid_square_id)
                    grid_square_dirs[grid_square_id] = grid_square_dir

        # Process each grid square from metadata
        for grid_square_id, metadata_file in metadata_files.items():
            # If grid square has a directory in Images-DiscN, it's active
            if grid_square_id in active_squares:
                parser = GridSquareParser(grid_square_dirs[grid_square_id], metadata_file)
                grid_squares.append(parser.parse())
            else:
                # For inactive grid squares, create a minimal GridSquare object
                grid_squares.append(GridSquare(
                    id=grid_square_id,
                    metadata_path=str(metadata_file),
                    timestamp=datetime.min,
                    foil_holes=[]
                ))

        return EPUSession(
            root_dir=str(self.root_dir),
            session_name=session_name,
            session_id=session_id,
            start_time=start_time,
            grid_squares=grid_squares,
            image_discs=image_discs,
            acquisition_settings=acquisition_settings,
            storage_folders=storage_folders
        )


def format_timestamp(dt: datetime) -> str:
    """Format datetime in a consistent, readable way"""
    if dt == datetime.min:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def print_session_summary(session: EPUSession):
    print(f"\nEPU Session Summary")
    print(f"==================")
    print(f"Session Name: {session.session_name}")
    print(f"Session ID: {session.session_id}")
    print(f"Start Time: {session.start_time}")
    print(f"Root directory: {session.root_dir}")
    print(f"Storage folders: {', '.join(session.storage_folders)}")
    print(f"Image discs found: {', '.join(session.image_discs)}")

    print("\nAcquisition Settings:")
    for mode, settings in session.acquisition_settings.items():
        print(f"  {mode}:")
        for key, value in settings.items():
            print(f"    {key}: {value}")

    # Calculate total statistics
    total_foil_holes = sum(len(gs.foil_holes) for gs in session.grid_squares)
    total_images = sum(sum(len(fh.data_files) for fh in gs.foil_holes) for gs in session.grid_squares)
    active_squares = sum(1 for gs in session.grid_squares if gs.foil_holes)

    print(f"\nSession Statistics:")
    print(f"  Total Grid Squares: {len(session.grid_squares)}")
    print(f"  Active Grid Squares: {active_squares}")
    print(f"  Total Foil Holes: {total_foil_holes}")
    print(f"  Total Images: {total_images}")

    for grid_square in session.grid_squares:
        print(f"\nGrid Square {grid_square.id}")
        print(f"  Timestamp: {format_timestamp(grid_square.timestamp)}")
        print(f"  Metadata file: {grid_square.metadata_path}")
        print(f"  Foil holes: {len(grid_square.foil_holes)}")

        for foil_hole in grid_square.foil_holes:
            print(f"    Foil Hole {foil_hole.id}")
            print(f"      Timestamp: {format_timestamp(foil_hole.timestamp)}")
            print(f"      XML file: {foil_hole.xml_path}")
            print(f"      Data files: {len(foil_hole.data_files)}")


def main():
    acquisition_dir_path = "tests/testdata/metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"

    if not os.path.exists(acquisition_dir_path):
        print(f"Error: Could not find EPU session dir at: {acquisition_dir_path}")
        return

    parser = EPUSessionParser(acquisition_dir_path)
    try:
        session = parser.parse()
        print_session_summary(session)
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()