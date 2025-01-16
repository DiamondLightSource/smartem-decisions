import xml.etree.ElementTree as ET
import pathlib
import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SupervisorInfo:
    """Information about the supervisor session"""
    date: datetime
    session_id: str  # The 6-digit ID (e.g., 093820)
    project_name: str

    @classmethod
    def from_string(cls, supervisor_str: str) -> Optional['SupervisorInfo']:
        """Parse supervisor string like '20240404_093820_Pete_Miriam_HexAuFoil'"""
        try:
            parts = supervisor_str.split('_')
            if len(parts) < 3:
                return None

            date_str = parts[0]
            time_str = parts[1]
            datetime_str = f"{date_str}_{time_str}"
            date = datetime.strptime(datetime_str, "%Y%m%d_%H%M%S")
            project_name = '_'.join(parts[2:])

            return cls(date=date, session_id=time_str, project_name=project_name)
        except (ValueError, IndexError) as e:
            print(f"DEBUG: Error parsing supervisor string '{supervisor_str}': {e}")
            return None

    def __str__(self) -> str:
        return f"{self.date.strftime('%Y%m%d')}_{self.session_id}_{self.project_name}"


@dataclass
class GridSquare:
    id: int
    file_path: pathlib.Path
    position: Optional[tuple[float, float]] = None


@dataclass
class AtlasInfo:
    atlas_id: str
    sample_id: int
    supervisor: SupervisorInfo
    grid_squares: Dict[int, GridSquare]
    file_path: pathlib.Path


@dataclass
class EpuSessionInfo:
    atlas_id: str
    grid_squares: List[int]  # List of referenced grid square IDs
    file_path: pathlib.Path


class PathMapper:
    """Handles path normalization and mapping between network and local paths"""

    def __init__(self):
        self.known_atlas_ids = {}  # Maps normalized paths to atlas IDs
        self.base_local_path = pathlib.Path('tests/testdata/epu_acquisition_dir')
        print("DEBUG: PathMapper initialized")

    def _extract_atlas_path_parts(self, path: str) -> tuple[Optional[str], Optional[str]]:
        """Extract supervisor and sample parts from an atlas path"""
        path = str(path).replace('\\', '/')
        print(f"DEBUG: Extracting parts from path: {path}")

        supervisor_match = re.search(r'Supervisor_([^/]+)', path)
        sample_match = re.search(r'Sample(\d+)', path)

        supervisor_part = supervisor_match.group(0) if supervisor_match else None
        sample_part = sample_match.group(0) if sample_match else None

        print(f"DEBUG: Extracted supervisor_part: {supervisor_part}, sample_part: {sample_part}")
        return supervisor_part, sample_part

    def normalize_path(self, path: str) -> str:
        """Convert any path format to a normalized format"""
        clean_path = str(path).replace('\\', '/').lower()
        print(f"DEBUG: Normalizing path: {clean_path}")

        supervisor_part, sample_part = self._extract_atlas_path_parts(clean_path)
        if supervisor_part and sample_part:
            normalized = f"{supervisor_part}/{sample_part}/Atlas/Atlas.dm"
            print(f"DEBUG: Normalized path to: {normalized}")
            return normalized

        print(f"DEBUG: Keeping original path: {clean_path}")
        return clean_path

    def get_path_variants(self, path: str) -> List[str]:
        """Generate all possible variants of a path"""
        print(f"DEBUG: Generating variants for path: {path}")
        supervisor_part, sample_part = self._extract_atlas_path_parts(path)

        if not (supervisor_part and sample_part):
            return [self.normalize_path(path)]

        # Generate all possible variants
        variants = [
            f"{supervisor_part}/{sample_part}/Atlas/Atlas.dm",  # Normalized form
            f"{self.base_local_path}/Atlas/{supervisor_part}/{sample_part}/Atlas/Atlas.dm",  # Local path
            f"z:/nt32457-6/atlas/{supervisor_part}/{sample_part}/Atlas/Atlas.dm",  # Network path
        ]

        # Normalize all variants
        normalized_variants = [v.lower().replace('\\', '/') for v in variants]
        print(f"DEBUG: Generated variants: {normalized_variants}")
        return normalized_variants

    def resolve_atlas_id(self, path: str) -> Optional[str]:
        """Get Atlas ID from path, checking all possible variants"""
        print(f"\nDEBUG: Resolving Atlas ID for path: {path}")
        print(f"DEBUG: Current known mappings: {self.known_atlas_ids}")

        variants = self.get_path_variants(path)
        for variant in variants:
            if variant in self.known_atlas_ids:
                atlas_id = self.known_atlas_ids[variant]
                print(f"DEBUG: Found Atlas ID {atlas_id} for variant {variant}")
                return atlas_id

        print(f"DEBUG: No Atlas ID found for any variant of {path}")
        return None

    def register_atlas_id(self, path: str, atlas_id: str):
        """Register all variants of a path with an Atlas ID"""
        print(f"\nDEBUG: Registering Atlas ID {atlas_id} for path: {path}")
        variants = self.get_path_variants(path)

        for variant in variants:
            self.known_atlas_ids[variant] = atlas_id
            print(f"DEBUG: Registered variant: {variant} -> {atlas_id}")


def parse_dm_file(file_path: pathlib.Path) -> tuple[ET.Element, dict]:
    """Parse a .dm file as XML and return the root element and namespaces"""
    try:
        print(f"\nParsing file: {file_path}")
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract and register namespaces
        namespaces = {}
        for child in root.iter():
            if '}' in child.tag:
                uri = child.tag[1:].split('}')[0]
                prefix = f"ns{len(namespaces)}"
                namespaces[prefix] = uri

        print(f"Detected root element: {root.tag.split('}')[-1]}")
        return root, namespaces
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse {file_path} as XML: {e}")
    except Exception as e:
        raise ValueError(f"Error processing {file_path}: {e}")


def extract_id_from_filename(file_path: pathlib.Path) -> Optional[dict]:
    """Extract various IDs from filename and path"""
    print(f"\nDEBUG: Extracting IDs from filename: {file_path}")
    ids = {}

    # Extract grid square ID
    if file_path.name.startswith('GridSquare_'):
        match = re.search(r'GridSquare_(\d+)', file_path.name)
        if match:
            ids['grid_square_id'] = int(match.group(1))
            print(f"DEBUG: Found grid_square_id: {ids['grid_square_id']}")

    # Extract sample ID
    sample_match = re.search(r'Sample(\d+)', str(file_path))
    if sample_match:
        ids['sample_id'] = int(sample_match.group(1))
        print(f"DEBUG: Found sample_id: {ids['sample_id']}")

    # Extract supervisor info
    supervisor_match = re.search(r'Supervisor_([^/\\]+)', str(file_path))
    if supervisor_match:
        supervisor_str = supervisor_match.group(1)
        supervisor = SupervisorInfo.from_string(supervisor_str)
        if supervisor:
            ids['supervisor'] = supervisor
            print(f"DEBUG: Found supervisor: {supervisor}")

    return ids if ids else None


def extract_atlas_info(atlas_file: pathlib.Path, path_mapper: PathMapper) -> Optional[AtlasInfo]:
    """Extract information from Atlas.dm file and related structure"""
    print(f"\nDEBUG: Extracting Atlas info from: {atlas_file}")
    ids = extract_id_from_filename(atlas_file)

    if not ids or 'sample_id' not in ids or 'supervisor' not in ids:
        print("DEBUG: Could not extract required IDs from path")
        return None

    root, namespaces = parse_dm_file(atlas_file)
    print("\nSearching for atlas information...")

    # Find Atlas ID
    atlas_id = None
    for elem in root.iter():
        if elem.tag.split('}')[-1] == 'Atlas':
            for sub_elem in elem.iter():
                if sub_elem.tag.split('}')[-1] == 'Id':
                    atlas_id = sub_elem.text
                    break
            if atlas_id:
                break

    if not atlas_id:
        print("DEBUG: Could not find Atlas ID in XML")
        return None

    print(f"Found Atlas ID: {atlas_id}")
    path_mapper.register_atlas_id(str(atlas_file), atlas_id)

    # Process grid squares
    grid_squares = {}
    for dm_file in atlas_file.parent.parent.rglob('GridSquare_*.dm'):
        grid_square = extract_grid_square_info(dm_file)
        if grid_square:
            grid_squares[grid_square.id] = grid_square
            print(f"DEBUG: Found grid square {grid_square.id}")

    return AtlasInfo(
        atlas_id=atlas_id,
        sample_id=ids['sample_id'],
        supervisor=ids['supervisor'],
        grid_squares=grid_squares,
        file_path=atlas_file
    )


def extract_grid_square_info(file_path: pathlib.Path) -> Optional[GridSquare]:
    """Extract information from a grid square file"""
    ids = extract_id_from_filename(file_path)
    if not ids or 'grid_square_id' not in ids:
        return None

    return GridSquare(
        id=ids['grid_square_id'],
        file_path=file_path
    )


def extract_epu_session_info(epu_file: pathlib.Path, path_mapper: PathMapper) -> Optional[EpuSessionInfo]:
    """Extract information from EpuSession.dm file"""
    print(f"\nDEBUG: Extracting EPU session info from: {epu_file}")
    root, namespaces = parse_dm_file(epu_file)

    # Find Atlas ID reference
    atlas_path = None

    # First try to find it in SampleXml
    for elem in root.iter():
        if elem.tag.split('}')[-1] == 'SampleXml':
            for child in elem.iter():
                if child.tag.split('}')[-1] == 'AtlasId' and child.text:
                    atlas_path = child.text
                    print(f"DEBUG: Found AtlasId in SampleXml: {atlas_path}")
                    break
        if atlas_path:
            break

    # If not found, look anywhere in the file
    if not atlas_path:
        for elem in root.iter():
            if elem.tag.split('}')[-1] == 'AtlasId' and elem.text:
                atlas_path = elem.text
                print(f"DEBUG: Found AtlasId in general search: {atlas_path}")
                break

    if not atlas_path:
        print("DEBUG: Could not find AtlasId in EPU session")
        return None

    # Resolve Atlas ID
    atlas_id = path_mapper.resolve_atlas_id(atlas_path)
    if not atlas_id:
        print(f"DEBUG: Could not resolve Atlas ID from path: {atlas_path}")
        atlas_id = atlas_path

    print(f"Found Atlas ID: {atlas_id}")

    # Collect grid square references
    grid_square_ids = set()

    # Check Images-Disc1 directory
    images_dir = epu_file.parent / 'Images-Disc1'
    if images_dir.exists():
        for item in images_dir.iterdir():
            if item.is_dir() and item.name.startswith('GridSquare_'):
                match = re.search(r'GridSquare_(\d+)', item.name)
                if match:
                    grid_square_ids.add(int(match.group(1)))
                    print(f"DEBUG: Found grid square {match.group(1)} in Images-Disc1")

    # Check for GridSquare_*.dm files
    for dm_file in epu_file.parent.rglob('GridSquare_*.dm'):
        ids = extract_id_from_filename(dm_file)
        if ids and 'grid_square_id' in ids:
            grid_square_ids.add(ids['grid_square_id'])
            print(f"DEBUG: Found grid square {ids['grid_square_id']} in .dm files")

    return EpuSessionInfo(
        atlas_id=atlas_id,
        grid_squares=sorted(grid_square_ids),
        file_path=epu_file
    )


def process_directory(base_dir: pathlib.Path) -> tuple[List[AtlasInfo], List[EpuSessionInfo]]:
    """Process a directory containing .dm files and extract all relevant information"""
    atlas_infos = []
    epu_session_infos = []
    path_mapper = PathMapper()

    print(f"\nProcessing directory: {base_dir}")

    # First process Atlas files to build ID mapping
    for dm_file in base_dir.rglob('*.dm'):
        if dm_file.name == 'Atlas.dm':
            try:
                atlas_info = extract_atlas_info(dm_file, path_mapper)
                if atlas_info:
                    atlas_infos.append(atlas_info)
            except Exception as e:
                print(f"DEBUG: Error processing Atlas.dm: {e}")

    # Then process EPU files using the atlas ID mapping
    for dm_file in base_dir.rglob('*.dm'):
        if dm_file.name == 'EpuSession.dm':
            try:
                epu_info = extract_epu_session_info(dm_file, path_mapper)
                if epu_info:
                    epu_session_infos.append(epu_info)
            except Exception as e:
                print(f"DEBUG: Error processing EpuSession.dm: {e}")

    return atlas_infos, epu_session_infos


def main():
    base_dir = pathlib.Path('tests/testdata/epumocks')
    atlas_infos, epu_session_infos = process_directory(base_dir)

    print("\nSummary:")
    print(f"Found {len(atlas_infos)} atlas files and {len(epu_session_infos)} EPU session files")

    print("\nAtlas Information:")
    for atlas in atlas_infos:
        print(f"\nAtlas ID: {atlas.atlas_id}")
        print(f"Sample ID: {atlas.sample_id}")
        print("Supervisor Info:")
        print(f"  Date: {atlas.supervisor.date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Session ID: {atlas.supervisor.session_id}")
        print(f"  Project: {atlas.supervisor.project_name}")
        print(f"File: {atlas.file_path}")
        print("Grid Squares:")
        for grid_id, grid in atlas.grid_squares.items():
            print(f"  Grid {grid_id}")
            if grid.position:
                print(f"    Position: ({grid.position[0]}, {grid.position[1]})")

    print("\nEPU Session Information:")
    for epu in epu_session_infos:
        print(f"\nEPU Session referencing Atlas ID: {epu.atlas_id}")
        print(f"File: {epu.file_path}")
        print("Referenced Grid Squares:", epu.grid_squares)


if __name__ == '__main__':
    main()
