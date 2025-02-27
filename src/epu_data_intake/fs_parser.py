import os
import re
import sys

from pathlib import Path
from datetime import datetime
from lxml import etree

from src.epu_data_intake.data_model import (
    EpuSession,
    EpuSessionData,
    Grid,
    AtlasData,
    AtlasTilePosition,
    AtlasTileData,
    GridSquarePosition,
    GridSquareStagePosition,
    FoilHolePosition,
    GridSquareMetadata,
    GridSquareManifest,
    GridSquareData,
    FoilHoleData,
    MicrographManifest,
    MicrographData,
)


class EpuParser:

    METADATA_DIR = "Metadata"
    EPU_SESSION_FILENAME = "EpuSession.dm"
    session_dm_pattern = re.compile(rf"{EPU_SESSION_FILENAME}$")
    atlas_dm_pattern = re.compile(r"Atlas/Atlas\.dm$")
    gridsquare_dm_file_pattern = re.compile(r"GridSquare_(\d+)\.dm$")  # under "Metadata/"
    gridsquare_xml_file_pattern = re.compile(r"GridSquare_(\d+)_(\d+).xml$")
    images_disc_dir_pattern = re.compile(r"/Images-Disc(\d+)$")
    gridsquare_dir_pattern = re.compile(r"[/\\]GridSquare_(\d+)[/\\]")  # under Images-Disc*/
    foilhole_xml_file_pattern = re.compile(r"FoilHole_(\d+)_(\d+)_(\d+)\.xml$")
    micrograph_xml_file_pattern = re.compile(r"FoilHole_(\d+)_Data_(\d+)_(\d+)_(\d+)_(\d+)\.xml$")


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
        epu_session_path = path / EpuParser.EPU_SESSION_FILENAME
        if not epu_session_path.is_file():
            errors.append("Missing required file: EpuSession.dm")

        # 2. Check for `/Metadata` directory
        metadata_path = path / EpuParser.METADATA_DIR
        if not metadata_path.is_dir():
            errors.append("Missing required directory: Metadata")

        # 3. Check for `/Images-Disc*` directories (at least `/Images-Disc1`)
        imagedisc_dirs = sorted([
            path / Path(d.name) for d in path.iterdir()
            if d.is_dir() and EpuParser.images_disc_dir_pattern.search(str(path / d.name))
        ])

        if not imagedisc_dirs:
            errors.append("No Images-Disc directories found. At least Images-Disc1 should exist.")
        else:
            # Validate the format of Images-Disk directories
            for dir_path in imagedisc_dirs:
                if not dir_path.is_dir():
                    continue

                # Check if the directory name matches the expected pattern
                match = EpuParser.images_disc_dir_pattern.search(str(dir_path))
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
    def parse_epu_session_manifest(manifest_path: str) -> EpuSessionData | None:
        try:
            namespaces = {
                'ns': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
                'common': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
                'i': 'http://www.w3.org/2001/XMLSchema-instance',
                'z': 'http://schemas.microsoft.com/2003/10/Serialization/'
            }

            tree = etree.parse(manifest_path)
            root = tree.getroot()

            def get_element_text(xpath):
                elements = root.xpath(xpath, namespaces=namespaces)
                return elements[0].text if elements else None

            atlas_id = get_element_text(".//ns:Samples/ns:_items/ns:SampleXml[1]/ns:AtlasId")
            storage_path = get_element_text(".//ns:StorageFolders/ns:_items/ns:StorageFolderXml[1]/ns:Path")

            if atlas_id and storage_path and atlas_id.startswith(storage_path):
                atlas_id = atlas_id[len(storage_path):].replace('\\', '/')
            if atlas_id.startswith('/'): # remove leading forward slash
                atlas_id = atlas_id.lstrip('/')

            start_time_str = get_element_text("./ns:StartDateTime")

            return EpuSessionData(
                name=get_element_text("./ns:Name"),
                id=get_element_text("./common:Id"),
                start_time=datetime.fromisoformat(start_time_str.rstrip('Z')) if start_time_str else None,
                atlas_path=atlas_id,
                storage_path=EpuParser.to_cygwin_path(storage_path) if storage_path else None,
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
                        ],
                        gridsquare_positions=EpuParser._parse_gridsquare_positions(element)
                    )

        except Exception as e:
            print(f"Failed to parse Atlas manifest: {str(e)}")
            return None


    @staticmethod
    def _parse_gridsquare_positions(atlas_xml):
        """Parse grid square positions from Atlas XML."""
        gridsquare_positions = {}

        namespaces = {
            'ns': 'http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence',
            'gen': 'http://schemas.datacontract.org/2004/07/System.Collections.Generic',
            'b': 'http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence',
            'c': 'http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Datamodel',
            'd': 'http://schemas.datacontract.org/2004/07/System.Drawing'
        }

        tiles = atlas_xml.xpath(".//ns:Atlas/ns:TilesEfficient/ns:_items/ns:TileXml", namespaces=namespaces)

        for tile in tiles:
            if (nodes := tile.find(".//ns:Nodes", namespaces=namespaces)) is None:
                continue

            # Get key-value pairs using local-name() to match the node-naming pattern
            pairs = nodes.xpath(".//gen:*[starts-with(local-name(), 'KeyValuePairOfintNodeXml')]",
                                namespaces=namespaces)
            for pair in pairs:
                try:
                    if (key := pair.findtext("gen:key", namespaces=namespaces)) is None:
                        continue

                    gs_id = int(key)

                    if (value := pair.find("gen:value", namespaces=namespaces)) is None:
                        continue

                    if (position := value.xpath(".//b:PositionOnTheAtlas", namespaces=namespaces)[0]) is None:
                        continue

                    center = position.find("c:Center", namespaces=namespaces)
                    center_tuple = None
                    if center is not None:
                        x_elem = center.find("d:x", namespaces=namespaces)
                        y_elem = center.find("d:y", namespaces=namespaces)
                        if x_elem is not None and y_elem is not None:
                            center_tuple = (int(float(x_elem.text)), int(float(y_elem.text)))

                    physical = position.find("c:Physical", namespaces=namespaces)
                    physical_tuple = None
                    if physical is not None:
                        x_elem = physical.find("d:x", namespaces=namespaces)
                        y_elem = physical.find("d:y", namespaces=namespaces)
                        if x_elem is not None and y_elem is not None:
                            physical_tuple = (float(x_elem.text) * 1e9, float(y_elem.text) * 1e9)

                    size = position.find("c:Size", namespaces=namespaces)
                    size_tuple = None
                    if size is not None:
                        width_elem = size.find("d:width", namespaces=namespaces)
                        height_elem = size.find("d:height", namespaces=namespaces)
                        if width_elem is not None and height_elem is not None:
                            size_tuple = (int(float(width_elem.text)), int(float(height_elem.text)))

                    rotation_elem = position.find("c:Rotation", namespaces=namespaces)
                    rotation = float(rotation_elem.text) if rotation_elem is not None else None

                    gridsquare_positions[gs_id] = GridSquarePosition(
                        center=center_tuple,
                        physical=physical_tuple,
                        size=size_tuple,
                        rotation=rotation
                    )

                except (AttributeError, IndexError, ValueError, TypeError) as e:
                    print(f"Failed to parse grid square position: {str(e)}")
                    continue

        return gridsquare_positions


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

            x_text = get_element_text("./ns:AtlasPixelPosition/draw:x")
            y_text = get_element_text("./ns:AtlasPixelPosition/draw:y")
            position_tuple = (int(x_text), int(y_text)) if x_text and y_text else None

            width_text = get_element_text("./ns:AtlasPixelPosition/draw:width")
            height_text = get_element_text("./ns:AtlasPixelPosition/draw:height")
            size_tuple = (int(width_text), int(height_text)) if width_text and height_text else None

            return AtlasTileData(
                id=tile_id,
                tile_position=AtlasTilePosition(
                    position=position_tuple,
                    size=size_tuple,
                ),
                file_format=get_element_text("./ns:TileImageReference/common:FileFormat"),
                base_filename=get_element_text("./ns:TileImageReference/common:BaseFileName"),
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

        result = [
            (EpuParser.gridsquare_dm_file_pattern.match(filename).group(1), os.path.join(path, filename))
            for filename in os.listdir(path)
            if EpuParser.gridsquare_dm_file_pattern.match(filename)
        ]

        return sorted(result)


    @staticmethod
    def parse_gridsquare_metadata(path: str) -> GridSquareMetadata | None:
        """Parse a GridSquare metadata file and extract both basic metadata and foil hole positions."""
        try:
            namespaces = {
                'def': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
                'i': 'http://www.w3.org/2001/XMLSchema-instance',
                'z': 'http://schemas.microsoft.com/2003/10/Serialization/',
                'common': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
                'a': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                'b': 'http://schemas.datacontract.org/2004/07/System.Collections.Generic',
                'c': 'http://schemas.datacontract.org/2004/07/System.Drawing',
                'shared': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects'
            }

            tree = etree.parse(path)
            root = tree.getroot()

            def get_element_text(xpath, elem=root):
                try:
                    elements = elem.xpath(xpath, namespaces=namespaces)
                    return elements[0].text if elements else None
                except etree.XPathEvalError as e:
                    print(f"XPath error for expression '{xpath}': {str(e)}")
                    return None

            # Helper function for safe float conversion
            def safe_float(value: str | None, default: float = None) -> float | None:
                if not value:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default

            # Basic metadata parsing
            # ----------------------
            stage_position = GridSquareStagePosition(
                x=safe_float(get_element_text("//def:Position/shared:X")),
                y=safe_float(get_element_text("//def:Position/shared:Y")),
                z=safe_float(get_element_text("//def:Position/shared:Z"))
            )

            image_path_str = get_element_text("//def:GridSquareImagePath")
            image_path = Path(EpuParser.to_cygwin_path(image_path_str)) if image_path_str else None

            selected_str = get_element_text("//def:Selected")
            unusable_str = get_element_text("//def:Unusable")
            selected = selected_str.lower() == 'true' if selected_str else False
            unusable = unusable_str.lower() == 'true' if unusable_str else False

            # Parse foil hole positions
            # -------------------------
            foilhole_positions: dict[int, FoilHolePosition] = {}

            # Find all KeyValuePair elements
            kvp_xpath = ".//def:TargetLocationsEfficient/a:m_serializationArray/*[starts-with(local-name(), 'KeyValuePairOfintTargetLocation')]"
            kvp_elements = root.xpath(kvp_xpath, namespaces=namespaces)

            for element in kvp_elements:
                try:
                    if (key_elem := element.find("{http://schemas.datacontract.org/2004/07/System.Collections.Generic}key")) is None:
                        continue
                    fh_id = int(key_elem.text)

                    if (value_elem := element.find(
                        "{http://schemas.datacontract.org/2004/07/System.Collections.Generic}value")) is None:
                        continue

                    # Check IsNearGridBar
                    is_near_grid_bar = (value_elem.find(
                        "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}IsNearGridBar") is not None
                                        and value_elem.find(
                                "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}IsNearGridBar").text.lower() == 'true')

                    # Find stage position
                    if (stage_pos := value_elem.find(
                        "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}StagePosition")) is not None:
                        stage_x = safe_float(
                            stage_pos.find("{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}X").text)
                        stage_y = safe_float(
                            stage_pos.find("{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}Y").text)
                    else:
                        stage_x = stage_y = None

                    # Find pixel position
                    if (pixel_center := value_elem.find(
                        "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}PixelCenter")) is not None:
                        pixel_x = safe_float(
                            pixel_center.find("{http://schemas.datacontract.org/2004/07/System.Drawing}x").text)
                        pixel_y = safe_float(
                            pixel_center.find("{http://schemas.datacontract.org/2004/07/System.Drawing}y").text)
                    else:
                        continue

                    if (pixel_size := value_elem.find(
                        "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}PixelWidthHeight")) is not None:
                        diameter = safe_float(
                            pixel_size.find("{http://schemas.datacontract.org/2004/07/System.Drawing}width").text)
                    else:
                        continue

                    foilhole_positions[fh_id] = FoilHolePosition(
                        x_location=int(pixel_x),
                        y_location=int(pixel_y),
                        x_stage_position=stage_x,
                        y_stage_position=stage_y,
                        diameter=int(diameter),
                        is_near_grid_bar=is_near_grid_bar,
                    )

                except Exception as e:
                    print(f"Error processing foil hole {fh_id}: {str(e)}")
                    continue

            metadata = GridSquareMetadata(
                atlas_node_id=int(get_element_text("//def:AtlasNodeId") or 0),
                stage_position=stage_position,
                state=get_element_text("//def:State"),
                rotation=safe_float(get_element_text("//def:Rotation")),
                image_path=image_path,
                selected=selected,
                unusable=unusable,
                foilhole_positions=foilhole_positions
            )

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
                        defocus=float(
                            get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus")) if get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:Defocus") else None,
                        magnification=float(get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:TemMagnification/ms:NominalMagnification")) if get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:TemMagnification/ms:NominalMagnification") else None,
                        pixel_size=float(get_element_text(
                            ".//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue")) if get_element_text(
                            ".//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue") else None,
                        detector_name=get_custom_value("DetectorCommercialName") if get_custom_value(
                            "DetectorCommercialName") else None,
                        applied_defocus=float(get_custom_value("AppliedDefocus")) if get_custom_value(
                            "AppliedDefocus") else None,
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

                    if not (match := re.search(EpuParser.foilhole_xml_file_pattern, filename)):
                        return None
                    foilhole_id = match.group(1)

                    if not (match := re.search(EpuParser.gridsquare_dir_pattern, str(manifest_path))):
                        return None
                    gridsquare_id = match.group(1)

                    return FoilHoleData(
                        id=foilhole_id,
                        gridsquare_id=gridsquare_id,
                        center_x=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:x")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:x") else None,
                        center_y=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:y")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:y") else None,
                        quality=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Quality")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Quality") else None,
                        rotation=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Rotation")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Rotation") else None,
                        size_width=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:width")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:width") else None,
                        size_height=float(get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:height")) if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:height") else None
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
                        defocus=float(get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus")) if get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:Defocus") else None,
                        detector_name=get_custom_value("DetectorCommercialName") or "Unknown",
                        energy_filter=get_element_text(".//ms:microscopeData/ms:optics/ms:EFTEMOn") == 'true',
                        phase_plate=get_custom_value("PhasePlateUsed") == 'true',
                        image_size_x=int(
                            readout_area.xpath(".//draw:width", namespaces=namespaces)[0].text) if readout_area.xpath(
                            ".//draw:width", namespaces=namespaces) else None,
                        image_size_y=int(
                            readout_area.xpath(".//draw:height", namespaces=namespaces)[0].text) if readout_area.xpath(
                            ".//draw:height", namespaces=namespaces) else None,
                        binning_x=int(binning.xpath(".//draw:x", namespaces=namespaces)[0].text or 1),
                        binning_y=int(binning.xpath(".//draw:y", namespaces=namespaces)[0].text or 1),
                    )

        except Exception as e:
            print(f"Failed to parse micrograph manifest: {str(e)}")
            return None


    @staticmethod
    def parse_epu_output_dir(datastore: EpuSession, verbose: bool = False):
        """Parse the entire EPU output directory, containing one or more grids/samples
        during a given microscopy session.
        """

        # Start with locating all EpuSession.dm files - init a grid for each found
        for epu_session_manifest in list(datastore.root_dir.glob("**/*EpuSession.dm")):
            grid = EpuParser.parse_grid_dir(str(Path(epu_session_manifest).parent), verbose)
            datastore.grids.add(grid.session_data.name, grid)

        return datastore


    @staticmethod
    def parse_grid_dir(grid_data_dir: str, verbose: bool = False) -> Grid:
        gridstore = Grid(str(Path(grid_data_dir).resolve()))

        # 1. parse EpuSession.dm
        epu_manifest_path = str(gridstore.data_dir / "EpuSession.dm")
        gridstore.session_data = EpuParser.parse_epu_session_manifest(epu_manifest_path)
        # Build out the absolute atlas_dir path
        gridstore.atlas_dir = Path(Path(grid_data_dir) / Path("..") / Path(gridstore.session_data.atlas_path)).resolve()
        gridstore.name = "" # TODO

        # 1.1 parse Atlas.dm. Path to `Atlas.dm` specified in `EpuSession.dm`
        if gridstore.session_data.atlas_path:
            gridstore.atlas_data = EpuParser.parse_atlas_manifest(str(gridstore.atlas_dir))

        # 2. scan all gridsquare IDs from /Metadata directory files - this includes "inactive" and "active" gridsquares
        metadata_dir_path = str(gridstore.data_dir / "Metadata")
        for gridsquare_id, filename in EpuParser.parse_gridsquares_metadata_dir(metadata_dir_path):
            verbose and print(f"Discovered gridsquare {gridsquare_id} from file {filename}")
            gridsquare_metadata = EpuParser.parse_gridsquare_metadata(filename)

            # Here we are not worried about overwriting an existing gridsquare
            #   because this is where they are first discovered and added to collection
            assert not gridstore.gridsquares.exists(gridsquare_id)

            gridstore.gridsquares.add(gridsquare_id, GridSquareData(
                id=gridsquare_id,
                metadata=gridsquare_metadata
            ))
            verbose and print(gridstore.gridsquares.get(gridsquare_id))

        # 3. scan all image-disc dir sub-dirs to get a list of active gridsquares. for each gridsquare subdir:
        for gridsquare_manifest_path in list(
            gridstore.data_dir.glob("Images-Disc*/GridSquare_*/GridSquare_*_*.xml")
        ):
            # 3.1 scan gridsquare manifest (take care to check for existing gridsquare record and not overwrite it)
            gridsquare_manifest = EpuParser.parse_gridsquare_manifest(gridsquare_manifest_path)
            gridsquare_id = re.search(EpuParser.gridsquare_dir_pattern, str(gridsquare_manifest_path)).group(1)

            assert gridstore.gridsquares.exists(gridsquare_id)
            gridsquare_data = gridstore.gridsquares.get(gridsquare_id)
            gridsquare_data.manifest = gridsquare_manifest
            gridstore.gridsquares.add(gridsquare_id, gridsquare_data)
            verbose and print(gridstore.gridsquares.get(gridsquare_id))

            # 3.2 scan that gridsquare's Foilholes/ dir to get foilholes
            foilhole_manifest_paths = sorted(
                gridstore.data_dir.glob(f"Images-Disc*/GridSquare_{gridsquare_id}/FoilHoles/FoilHole_*_*_*.xml"),
                key=lambda p: p.name  # sorts based on just the filename part. This is important because it's possible
                # to sometimes have multiple foilhole manifests side-by-side and only the latest one is relevant.
            )
            for foilhole_manifest_path in foilhole_manifest_paths:
                foilhole_id = re.search(EpuParser.foilhole_xml_file_pattern, str(foilhole_manifest_path)).group(1)
                gridstore.foilholes.add(foilhole_id, EpuParser.parse_foilhole_manifest(foilhole_manifest_path))
                verbose and print(gridstore.foilholes.get(foilhole_id))

            # 3.3 scan that gridsquare's Foilholes/ dir to get micrographs
            for micrograph_manifest_path in list(
                gridstore.data_dir.glob(
                    f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_*_Data_*_*_*_*.xml"
                )
            ):
                micrograph_manifest = EpuParser.parse_micrograph_manifest(micrograph_manifest_path)
                match = re.search(EpuParser.micrograph_xml_file_pattern, str(micrograph_manifest_path))
                foilhole_id = match.group(1)
                location_id = match.group(2)
                gridstore.micrographs.add(micrograph_manifest.unique_id, MicrographData(
                    id = micrograph_manifest.unique_id,
                    gridsquare_id = gridsquare_id,
                    foilhole_id = foilhole_id,
                    location_id=location_id,
                    high_res_path=Path(""),
                    manifest_file = micrograph_manifest_path,
                    manifest = micrograph_manifest,
                ))
                verbose and print(gridstore.micrographs.get(micrograph_manifest.unique_id))

        return gridstore


if __name__ == "__main__":
    print("This module is not meant to be run directly. Import and use its components instead.")
    sys.exit(1)
