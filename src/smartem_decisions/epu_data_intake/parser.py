#!/usr/bin/env python

import re
from dataclasses import dataclass, field
from pprint import pprint
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import logging
import typer
from lxml import etree

@dataclass
class MicrographManifest:
    unique_id: str
    acquisition_datetime: datetime
    defocus: float
    detector_name: str
    energy_filter: bool
    phase_plate: bool
    image_size_x: int
    image_size_y: int
    binning_x: int
    binning_y: int


@dataclass
class MicrographData:
    id: str
    gridsquare_id: str
    foilhole_id: str
    manifest_file: Path
    manifest: MicrographManifest
    # TODO:
    #  1. add positioning on foilhole. So in a path akin `'FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$'`
    #  match 2 is a location ID (these repeat for every foihole and Dan will provide the info of where these
    #  locations are defined)
    #  2. Path to high-res micrograph image


@dataclass
class FoilHoleData:
   id: str
   gridsquare_id: str
   files: dict = field(default_factory=lambda: {"foilholes_dir": [], "data_dir": []})
   center_x: Optional[float] = None
   center_y: Optional[float] = None
   quality: Optional[float] = None
   rotation: Optional[float] = None
   size_width: Optional[float] = None
   size_height: Optional[float] = None


@dataclass
class GridSquareManifest:
    acquisition_datetime: datetime
    defocus: float  # in meters
    magnification: float
    pixel_size: float  # in meters
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
class AtlasTileData:
    id: str
    position: tuple  # (x, y)
    size: tuple     # (width, height)
    file_format: str
    base_filename: str


@dataclass
class AtlasData:
    id: str
    acquisition_date: datetime
    storage_folder: str
    description: str
    name: str
    tiles: List[AtlasTileData]


@dataclass
class EPUSessionData:
    name: str
    id: str
    start_time: datetime
    atlas_id: Optional[str] = None # TODO could this be the path to Atlas.dm?
    storage_path: Optional[str] = None # Path of parent directory containing the epu session dir
    clustering_mode: Optional[str] = None
    clustering_radius: Optional[float] = None


"""
Methods prefixed with `scan_` glob the filesystem for expected directories and files based on
known naming conventions.
Methods prefixed with `parse_` extract entity information from individual files, or from XML partials.
"""
class EpuSession:
    project_dir: Path
    atlas_dir: Path

    imagedisc_dirs: List[Path] # TODO remove

    epu_session: EPUSessionData
    atlas: AtlasData

    # IDs only for lookup
    gridsquare_ids = []
    foilhole_ids = []
    micrograph_ids = []

    gridsquares = dict()  # indexed by gridsquare_id: str, contains GridSquareData objects
    foilholes = dict()  # indexed by foilhole_id: str, contains FoilHoleData objects
    micrographs = dict() # indexed by micrograph_id: str, if such a thing exists?


    def __init__(self, project_dir, atlas_dir): # TODO - derive atlas dir from project dir deterministically
        self.logger = logging.getLogger(__name__)

        self.project_dir = Path(project_dir)
        self.atlas_dir = Path(atlas_dir)


    def print_summary(self): # TODO __str__
        print(f"\nEPU Session Summary")
        print(f"==================")
        print(f"Session Name: {self.epu_session.name}")
        print(f"Session ID: {self.epu_session.id}")
        print(f"Start Time: {self.epu_session.start_time}")
        print(f"Project directory: {self.project_dir}")
        print(f"Atlas directory: {self.atlas_dir}")
        pprint(self.epu_session)

        print(f"\nSession Statistics:")
        print(f"  Total Grid Squares: {len(self.gridsquares)}")
        print(f"  Active Grid Squares: {sum(1 for gs in self.gridsquares.values() if gs.is_active)}")
        print(f"  Total Foil Holes: {len(self.foilholes)}")
        print(f"  Total Micrographs: {len(self.micrographs)}")


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


    def scan_gridsquares(self):
        pass  # TODO drop method since we are not parsing incrementally rather than a complete directory
        try:
            metadata_path = self.project_dir / "Metadata"
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

        except Exception as e:
            self.logger.error(f"Failed to scan grid squares: {str(e)}")


    def scan_foilholes(self, gridsquare_id: str, gridsquare_dir: Path):
        pass # TODO drop method since we are not parsing incrementally rather than a complete directory
        try:
            # Check for required subdirectories
            gridsquare_data_dir = gridsquare_dir / "Data"
            gridsquare_foilholes_dir = gridsquare_dir / "FoilHoles"
            if not gridsquare_data_dir.is_dir():
                return
            if not gridsquare_foilholes_dir.is_dir():
                return

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

        except Exception as e:
            self.logger.error(f"Failed to scan foil holes: {str(e)}")


    def scan_micrographs(self, gridsquare_id: str, foilhole_id: str):
        pass # TODO drop method since we are not parsing incrementally rather than a complete directory
        try:
            # there is one file in data_dir per micrograph, so the unique combinations of foil hole and position in foil hole
            micrograph_manifest_paths = list(
                self.project_dir.glob(
                    f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_{foilhole_id}_Data_*_*_*_*.xml"
                )
            )
            for micrograph_path in micrograph_manifest_paths:
                micrograph_id, micrograph_manifest = self.parse_micrograph_manifest(micrograph_path)
                self.micrographs[micrograph_id] = MicrographData(
                    id = micrograph_id,
                    gridsquare_id = gridsquare_id,
                    foilhole_id = foilhole_id,
                    manifest_file = micrograph_path,
                    manifest = micrograph_manifest,
                )

        except Exception as e:
            self.logger.error(f"Failed to parse EpuSession manifest: {str(e)}")


class EpuParsers:

    project_dir_globs = [
        "EpuSession.dm",
        "Metadata/GridSquare_*.dm",
        "Images-Disc*/GridSquare_*/GridSquare_*_*.xml"
        "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
        "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    ]

    atlas_dir_globs = [
        "Sample*/Atlas/Atlas.dm",
        "Sample*/Sample.dm", # TODO is needed?
    ]

    @staticmethod
    def parse_epu_session_manifest(manifest_path: str) -> Optional[EPUSessionData]:
        # TODO consider using lxml's built-in namespace stripping during parsing:
        # parser = etree.XMLParser(remove_blank_text=True, remove_comments=True, strip_namespaces=True)
        # tree = etree.parse(manifest_path, parser)

        # atlas_id = 'Z:\\DoseFractions\\cm40598-8\\atlas\\Supervisor_20250114_095529_BSAtest_cm40598-8\\Sample9\\Atlas\\Atlas.dm',
        # storage_path = 'Z:\\DoseFractions\\cm40598-8',
        # TODO ^^ This is where we get the `Atlas.dm` location and need to call `self.parse_atlas_manifest()`
        # > In cygwin it would be /cygdrive/z/DoseFractions/cm40598-8/atlas/Supervisor_20250114_095529_BSAtest_cm40598-8/Sample9/Atlas/Atlas.dm .
        # >   In MSys2 python will read it as the windows path
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
                            EpuParsers._parse_atlas_tile(tile)
                            for tile in
                            element.xpath(".//ns:Atlas/ns:TilesEfficient/ns:_items/ns:TileXml", namespaces=namespaces)
                            if tile.xpath(".//common:Id", namespaces=namespaces)
                        ]
                    )

        except Exception as e:
            print(f"Failed to parse Atlas manifest: {str(e)}")
            return None


    @staticmethod
    def _parse_atlas_tile(tile_xml) -> Optional[AtlasTileData]:
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
    def parse_gridsquare_manifest(manifest_path: str) -> Optional[GridSquareManifest]:
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
    def parse_foilhole_manifest(manifest_path: str) -> Optional[FoilHoleData]:
        try:
            namespaces = {
                'ms': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
                'arr': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                'draw': 'http://schemas.datacontract.org/2004/07/System.Drawing',
                'b': 'http://schemas.datacontract.org/2004/07/Fei.Types'
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

                    center_elem = element.xpath(
                        ".//ms:CustomData//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Shape2D",
                        namespaces=namespaces)[0]

                    return FoilHoleData(
                        id=foilhole_id,
                        gridsquare_id=gridsquare_id,
                        files={"foilholes_dir": [], "data_dir": []},
                        center_x=float(get_element_text(".//draw:x", center_elem) or 0),
                        center_y=float(get_element_text(".//draw:y", center_elem) or 0),
                        quality=float(get_element_text(".//b:Quality", center_elem) or 0),
                        rotation=float(get_element_text(".//b:Rotation", center_elem) or 0),
                        size_width=float(get_element_text(".//draw:width", center_elem) or 0),
                        size_height=float(get_element_text(".//draw:height", center_elem) or 0)
                    )

        except Exception as e:
            print(f"Failed to parse foil hole manifest: {str(e)}")
            return None


    @staticmethod
    def parse_micrograph_manifest(manifest_path: str) -> Optional[MicrographManifest]:
        # TODO we also want to match and extract "9017354" from "FoilHole_9015883_Data_9017354_6_20250108_154918.xml"
        #   see comment on MicrographData definition
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
def parse_epu_session(path: str):
    epu_session_data = EpuParsers.parse_epu_session_manifest(path)
    pprint(epu_session_data)


@epu_parser_cli.command()
def parse_atlas(path: str):
    atlas_data = EpuParsers.parse_atlas_manifest(path)
    pprint(atlas_data)


@epu_parser_cli.command()
def parse_gridsquare(path: str):
    gridsquare_data = EpuParsers.parse_gridsquare_manifest(path)
    pprint(gridsquare_data)


@epu_parser_cli.command()
def parse_foilhole(path: str):
    foilhole_data = EpuParsers.parse_foilhole_manifest(path)
    pprint(foilhole_data)


@epu_parser_cli.command()
def parse_micrograph(path: str):
    micrograph_data = EpuParsers.parse_micrograph_manifest(path)
    pprint(micrograph_data)


if __name__ == "__main__":
    # example datasets
    dir1 = "../metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"
    dir2 = "../metadata_Supervisor_20250114_220855_23_epuBSAd20_GrOxDDM"
    dir3 = "../metadata_Supervisor_20241220_140307_72_et2_gangshun"

    epu_parser_cli()
