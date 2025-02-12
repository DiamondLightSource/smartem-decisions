#!/usr/bin/env python

import os
import re
import typer
from pprint import pprint
from pathlib import Path
from datetime import datetime
from lxml import etree
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from data_model import (
    EPUSessionData,
    AtlasData,
    AtlasTileData,
    GridSquareMetadata,
    GridSquareManifest,
    FoilHoleData,
    MicrographManifest,
)

console = Console()


# TODO: use or loose
# def get_tile_coordinates(self, atlas_info: AtlasInfo) -> List[tuple]:
#     """Returns list of (x,y) coordinates for all tiles"""
#     return [tile.position for tile in atlas_info.tiles if tile is not None]
#
# def get_tile_dimensions(self, atlas_info: AtlasInfo) -> List[tuple]:
#     """Returns list of (width,height) dimensions for all tiles"""
#     return [tile.size for tile in atlas_info.tiles if tile is not None]
#
# def analyze_tile_layout(self, atlas_info: AtlasData) -> dict:
#     """Analyzes the tile layout and returns statistics"""
#     coordinates = self.get_tile_coordinates(atlas_info)
#     dimensions = self.get_tile_dimensions(atlas_info)
#
#     x_coords = [coord[0] for coord in coordinates]
#     y_coords = [coord[1] for coord in coordinates]
#     widths = [dim[0] for dim in dimensions]
#     heights = [dim[1] for dim in dimensions]
#
#     return {
#         "total_tiles": len(coordinates),
#         "grid_width": max(x_coords) - min(x_coords) + max(widths),
#         "grid_height": max(y_coords) - min(y_coords) + max(heights),
#         "avg_tile_width": sum(widths) / len(widths),
#         "avg_tile_height": sum(heights) / len(heights)
#     }


class EpuParser:

    @staticmethod
    def to_cygwin_path(windows_path: str): # TODO add tests
        """This method would convert a Windows path such as:
        'Z:\\DoseFractions\\cm40598-8\\atlas\\Supervisor_20250114_095529_BSAtest_cm40598-8\\Sample9\\Atlas\\Atlas.dm'
        to:
        '/cygdrive/z/DoseFractions/cm40598-8/atlas/Supervisor_20250114_095529_BSAtest_cm40598-8/Sample9/Atlas/Atlas.dm'
        > Note: In MSys2 python will read it as the windows path
        """
        if len(windows_path) >= 2 and windows_path[1] == ':':
            drive_letter = windows_path[0].lower()
            cygwin_path = f"/cygdrive/{drive_letter}{windows_path[2:].replace('\\', '/')}"
        else:
            cygwin_path = windows_path.replace('\\', '/')
        return cygwin_path.replace('//', '/')


    @staticmethod
    def validate_project_dir(path: Path) -> tuple[bool, list[str]]:
        """
        Validates the EPU acquisition directory structure.

        Returns:
            tuple: (is_valid: bool, errors: list[str])
            - is_valid: True if all checks pass, False otherwise
            - errors: List of error messages if any checks fail
        """
        errors = []

        # 1. Check for `/EpuSession.dm` file
        epu_session_path = path / "EpuSession.dm"
        if not epu_session_path.is_file():
            errors.append("Missing required file: EpuSession.dm")

        # 2. Check for `/Metadata` directory
        metadata_path = path / "Metadata"
        if not metadata_path.is_dir():
            errors.append("Missing required directory: Metadata")

        # 3. Check for `/Images-Disc*` directories (at least `/Images-Disc1`)
        imagedisc_dirs = sorted([
            path / Path(d.name) for d in path.iterdir()
            if d.is_dir() and d.name.startswith('Images-Disc')
        ])

        if not imagedisc_dirs:
            errors.append("No Images-Disc directories found. At least Images-Disc1 should exist.")
        else:
            # Validate the format of Images-Disk directories
            for dir_path in imagedisc_dirs:
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


    @staticmethod
    def resolve_project_dir(watched_dir: Path):
        """
        Watched dir may contain a number of subdirectories, one per each EPU
        acquisition. Disregarding any project_dir candidate that does not conform to
        a valid EPU Acquisition directory structure (using `EpuParser.validate_project_dir`)
        wouldn't work for an incremental parser, but receipt of fs events from any given subdirectory
        can be an indicator that the dir is actively written to by EPU software. TODO
        """
        return watched_dir


    @staticmethod
    def resolve_atlas_dir(watched_dir: Path):
        """In atlas dir `tree -d` may look like so (files omitted):
        └── Supervisor_20250129_111544_bi37708-28_atlas
            ├── Atlas
            ├── Sample0
            │   └── Atlas
            ├── Sample1
            │   └── Atlas
            ├── Sample3
            │   └── Atlas
            ├── Sample4
            │   └── Atlas
            ├── Sample6
            │   └── Atlas
            └── Sample7
                └── Atlas
        TODO: confirm if `atlas/` can ever have more than a single child dir
        """
        return watched_dir / "atlas"


    @staticmethod
    def parse_epu_session_manifest(manifest_path: str) -> EPUSessionData | None:
        try:
            namespaces = {
                'ns': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
                'common': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
                'i': 'http://www.w3.org/2001/XMLSchema-instance',
                'z': 'http://schemas.microsoft.com/2003/10/Serialization/'
            }

            for event, element in etree.iterparse(manifest_path,
                                                  tag="{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}EpuSessionXml"):
                if event == 'end':
                    def get_element_text(xpath):
                        elements = element.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    start_time_str = get_element_text("./ns:StartDateTime")

                    return EPUSessionData(
                        name=get_element_text("./ns:Name"),
                        id=get_element_text("./common:Id"),
                        start_time=datetime.fromisoformat(start_time_str.rstrip('Z')) if start_time_str else None,
                        atlas_id=get_element_text("./ns:AtlasId"),
                        storage_path=get_element_text("./ns:Path"),
                        clustering_mode=get_element_text("./ns:ClusteringMode"),
                        clustering_radius=get_element_text("./ns:ClusteringRadius"),
                    )

        except Exception as e:
            print(f"Failed to parse EPU session manifest: {str(e)}")
            return None


    @staticmethod
    def parse_atlas_manifest(atlas_path: str):
        try:
            namespaces = {
                'ns': 'http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence',
                'common': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
                'i': 'http://www.w3.org/2001/XMLSchema-instance',
                'z': 'http://schemas.microsoft.com/2003/10/Serialization/'
            }

            for event, element in etree.iterparse(atlas_path,
                                                  tag="{http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence}AtlasSessionXml"):
                if event == 'end':
                    def get_element_text(xpath):
                        elements = element.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    acquisition_date_str = get_element_text(".//ns:Atlas/ns:AcquisitionDateTime")

                    return AtlasData(
                        id=get_element_text(".//common:Id"),
                        acquisition_date=datetime.fromisoformat(
                            acquisition_date_str.replace('Z', '+00:00')
                        ) if acquisition_date_str else None,
                        storage_folder=get_element_text(".//ns:Atlas/ns:StorageFolder"),
                        description=get_element_text(".//ns:Atlas/ns:Description"),
                        name=get_element_text(".//ns:Atlas/ns:Name"),
                        tiles=[
                            EpuParser._parse_atlas_tile(tile)
                            for tile in
                            element.xpath(".//ns:Atlas/ns:TilesEfficient/ns:_items/ns:TileXml", namespaces=namespaces)
                            if tile.xpath(".//common:Id", namespaces=namespaces)
                        ]
                    )

        except Exception as e:
            print(f"Failed to parse Atlas manifest: {str(e)}")
            return None


    @staticmethod
    def _parse_atlas_tile(tile_xml) -> AtlasTileData | None:
        try:
            namespaces = {
                'ns': 'http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence',
                'common': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
                'draw': 'http://schemas.datacontract.org/2004/07/System.Drawing'
            }

            def get_element_text(xpath):
                elements = tile_xml.xpath(xpath, namespaces=namespaces)
                return elements[0].text if elements else None

            tile_id = get_element_text(".//common:Id")
            if not tile_id:
                return None

            x = int(get_element_text("./ns:AtlasPixelPosition/draw:x"))
            y = int(get_element_text("./ns:AtlasPixelPosition/draw:y"))
            width = int(get_element_text("./ns:AtlasPixelPosition/draw:width"))
            height = int(get_element_text("./ns:AtlasPixelPosition/draw:height"))

            file_format = get_element_text("./ns:TileImageReference/common:FileFormat")
            base_filename = get_element_text("./ns:TileImageReference/common:BaseFileName")

            return AtlasTileData(
                id=tile_id,
                position=(x, y),
                size=(width, height),
                file_format=file_format,
                base_filename=base_filename
            )

        except Exception as e:
            print(f"Failed to parse tile: {str(e)}")
            return None

    @staticmethod
    def parse_gridsquares_metadata_dir(path: str) -> list[tuple[str, str]]:
        """Parse a directory containing GridSquare metadata files and return their IDs and filenames.

        Args:
            path (str): Path to the directory containing GridSquare_*.dm files

        Returns:
            list[tuple[int, str]]: List of tuples containing (grid_square_id, full_path) pairs
        """

        pattern = re.compile(r'GridSquare_(\d+)\.dm$') # TODO is already defined elsewhere, re-use

        result = [
            (pattern.match(filename).group(1), os.path.join(path, filename))
            for filename in os.listdir(path)
            if pattern.match(filename)
        ]

        return sorted(result)


    @staticmethod
    def parse_gridsquare_metadata(path: str) -> GridSquareMetadata | None:
        try:
            namespaces = {
                'epu': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
                'shared': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
                'a': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects'
            }

            context = etree.iterparse(
                path,
                tag="{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}GridSquareXml",
                events=('end',)
            )

            for event, element in context:
                def get_element_text(xpath):
                    elements = element.xpath(xpath, namespaces=namespaces)
                    return elements[0].text if elements else None

                position = {
                    # TODO perhaps better to use `np.nan` instead of 0.0?
                    'x': float(get_element_text(".//epu:Position/shared:X") or 0.0),
                    'y': float(get_element_text(".//epu:Position/shared:Y") or 0.0),
                    'z': float(get_element_text(".//epu:Position/shared:Z") or 0.0),
                }

                image_path_str = get_element_text(".//epu:GridSquareImagePath")
                image_path = Path(EpuParser.to_cygwin_path(image_path_str)) if image_path_str else None

                # Parse boolean values
                selected_str = get_element_text(".//epu:Selected")
                unusable_str = get_element_text(".//epu:Unusable")
                selected = selected_str.lower() == 'true' if selected_str else False
                unusable = unusable_str.lower() == 'true' if unusable_str else False

                metadata = GridSquareMetadata(
                    atlas_node_id=int(get_element_text(".//epu:AtlasNodeId") or 0),
                    position=position,
                    state=get_element_text(".//epu:State"),
                    rotation=float(get_element_text(".//epu:Rotation") or 0.0), # TODO use `np.nan`?
                    image_path=image_path,
                    selected=selected,
                    unusable=unusable
                )

                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]

                return metadata

        except Exception as e:
            print(f"Failed to parse gridsquare metadata: {str(e)}")
            return None


    @staticmethod
    def parse_gridsquare_manifest(manifest_path: str) -> GridSquareManifest | None:
        try:
            namespaces = {
                'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
                'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
            }

            for event, element in etree.iterparse(manifest_path,
                                                  tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"):
                if event == 'end':
                    def get_element_text(xpath):
                        elements = element.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    def get_custom_value(key):
                        xpath = f".//ms:CustomData//arr:KeyValueOfstringanyType[arr:Key='{key}']/arr:Value"
                        return get_element_text(xpath)

                    acquisition_date_str = get_element_text(
                        ".//ms:microscopeData/ms:acquisition/ms:acquisitionDateTime")

                    return GridSquareManifest(
                        acquisition_datetime=datetime.fromisoformat(
                            acquisition_date_str.replace('Z', '+00:00')
                        ) if acquisition_date_str else None,
                        defocus=float(get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus") or 0.0),
                        magnification=float(get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:TemMagnification/ms:NominalMagnification") or 0.0),
                        pixel_size=float(
                            get_element_text(".//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue") or 0.0),
                        detector_name=get_custom_value("DetectorCommercialName") or "Unknown",
                        applied_defocus=float(get_custom_value("AppliedDefocus") or 0.0),
                        data_dir=Path(manifest_path).parent
                    )

        except Exception as e:
            print(f"Failed to parse grid square manifest: {str(e)}")
            return None


    @staticmethod
    def parse_foilhole_manifest(manifest_path: str) -> FoilHoleData | None:
        try:
            namespaces = {
                'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
                'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                'draw': 'http://schemas.datacontract.org/2004/07/System.Drawing',
                'b': 'http://schemas.datacontract.org/2004/07/Fei.Types',
                'c': 'http://schemas.datacontract.org/2004/07/System.Drawing'
            }

            for event, element in etree.iterparse(manifest_path,
                                                  tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"):
                if event == 'end':
                    def get_element_text(xpath, elem=element):
                        elements = elem.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    filename = Path(manifest_path).name
                    match = re.match(r'FoilHole_(\d+)_.*\.xml', filename)
                    if not match:
                        return None
                    foilhole_id = match.group(1)

                    match = re.search(r'GridSquare_(\d+)', str(manifest_path))
                    if not match:
                        return None
                    gridsquare_id = match.group(1)

                    return FoilHoleData(
                        id=foilhole_id,
                        gridsquare_id=gridsquare_id,
                        center_x=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:x") or 0),
                        center_y=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:y") or 0),
                        quality=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Quality") or 0),
                        rotation=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Rotation") or 0),
                        size_width=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:width") or 0),
                        size_height=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:height") or 0)
                    )

        except Exception as e:
            print(f"Failed to parse foil hole manifest: {str(e)}")
            return None


    @staticmethod
    def parse_micrograph_manifest(manifest_path: str) -> MicrographManifest | None:
        try:
            namespaces = {
                'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
                'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                'draw': 'http://schemas.datacontract.org/2004/07/System.Drawing'
            }

            for event, element in etree.iterparse(manifest_path,
                                                  tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"):
                if event == 'end':
                    def get_element_text(xpath):
                        elements = element.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    def get_custom_value(key):
                        xpath = f".//ms:CustomData//arr:KeyValueOfstringanyType[arr:Key='{key}']/arr:Value"
                        return get_element_text(xpath)

                    camera = element.xpath(".//ms:microscopeData/ms:acquisition/ms:camera", namespaces=namespaces)[0]
                    readout_area = camera.xpath(".//ms:ReadoutArea", namespaces=namespaces)[0]
                    binning = camera.xpath(".//ms:Binning", namespaces=namespaces)[0]

                    return MicrographManifest(
                        unique_id=get_element_text(".//ms:uniqueID"),
                        acquisition_datetime=datetime.fromisoformat(
                            get_element_text(".//ms:microscopeData/ms:acquisition/ms:acquisitionDateTime").replace('Z',
                                                                                                                   '+00:00')
                        ),
                        defocus=float(get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus") or 0.0),
                        detector_name=get_custom_value("DetectorCommercialName") or "Unknown",
                        energy_filter=get_element_text(".//ms:microscopeData/ms:optics/ms:EFTEMOn") == 'true',
                        phase_plate=get_custom_value("PhasePlateUsed") == 'true',
                        image_size_x=int(readout_area.xpath(".//draw:width", namespaces=namespaces)[0].text or 0),
                        image_size_y=int(readout_area.xpath(".//draw:height", namespaces=namespaces)[0].text or 0),
                        binning_x=int(binning.xpath(".//draw:x", namespaces=namespaces)[0].text or 1),
                        binning_y=int(binning.xpath(".//draw:y", namespaces=namespaces)[0].text or 1)
                    )

        except Exception as e:
            print(f"Failed to parse micrograph manifest: {str(e)}")
            return None


epu_parser_cli = typer.Typer()


@epu_parser_cli.command()
def parse_acquisition_dir(path: str):
    pass


@epu_parser_cli.command()
def parse_epu_session(path: str):
    epu_session_data = EpuParser.parse_epu_session_manifest(path)
    pprint(epu_session_data)


@epu_parser_cli.command()
def parse_atlas(path: str):
    atlas_data = EpuParser.parse_atlas_manifest(path)
    pprint(atlas_data)


@epu_parser_cli.command()
def parse_gridsquare_metadata(path: str):
    metadata = EpuParser.parse_gridsquare_metadata(path)
    pprint(metadata)


@epu_parser_cli.command()
def parse_gridsquare(path: str):
    gridsquare_manifest_data = EpuParser.parse_gridsquare_manifest(path)
    pprint(gridsquare_manifest_data)


@epu_parser_cli.command()
def parse_foilhole(path: str):
    foilhole_data = EpuParser.parse_foilhole_manifest(path)
    pprint(foilhole_data)


@epu_parser_cli.command()
def parse_micrograph(path: str):
    micrograph_data = EpuParser.parse_micrograph_manifest(path)
    pprint(micrograph_data)


@epu_parser_cli.command()
def validate_epu_dir(path: str):
    is_valid, errors = EpuParser.validate_project_dir(Path(path))

    if is_valid:
        title = Text("✅ Valid EPU Directory", style="bold green")
        content = Text("All required files and directories are present.", style="green")
    else:
        title = Text("❌ Invalid EPU Directory", style="bold red")
        content = Text.assemble(
            Text("Found the following issues:\n\n", style="red"),
            *(Text(f"• {error}\n", style="yellow") for error in errors)
        )

    panel = Panel(
        content,
        title=title,
        border_style="green" if is_valid else "red",
        padding=(1, 2)
    )

    console.print(panel)
    return not is_valid  # Return non-zero exit code if validation fails

if __name__ == "__main__":
    # Example Datasets
    # dir1 = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"
    # dir2 = "../metadata_Supervisor_20250114_220855_23_epuBSAd20_GrOxDDM"
    # dir3 = "../metadata_Supervisor_20241220_140307_72_et2_gangshun"

    epu_parser_cli()
