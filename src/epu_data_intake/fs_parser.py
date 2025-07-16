import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from lxml import etree

from epu_data_intake.model.schemas import (
    AcquisitionData,
    AtlasData,
    AtlasTileData,
    AtlasTileGridSquarePosition,
    AtlasTileGridSquarePositionData,
    AtlasTilePosition,
    FoilHoleData,
    FoilHolePosition,
    GridData,
    GridSquareData,
    GridSquareManifest,
    GridSquareMetadata,
    GridSquarePosition,
    GridSquareStagePosition,
    MicrographData,
    MicrographManifest,
    MicroscopeData,
)
from epu_data_intake.model.store import InMemoryDataStore


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
    def to_cygwin_path(windows_path: str):  # TODO add tests
        """This method would convert a Windows path such as:
        'Z:\\DoseFractions\\cm40598-8\\atlas\\Supervisor_20250114_095529_BSAtest_cm40598-8\\Sample9\\Atlas\\Atlas.dm'
        to:
        '/cygdrive/z/DoseFractions/cm40598-8/atlas/Supervisor_20250114_095529_BSAtest_cm40598-8/Sample9/Atlas/Atlas.dm'
        > Note: In MSys2 python will read it as the windows path
        """
        if len(windows_path) >= 2 and windows_path[1] == ":":
            drive_letter = windows_path[0].lower()
            cygwin_path = f"/cygdrive/{drive_letter}{windows_path[2:].replace('\\', '/')}"
        else:
            cygwin_path = windows_path.replace("\\", "/")
        return cygwin_path.replace("//", "/")

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
        imagedisc_dirs = sorted(
            [
                path / Path(d.name)
                for d in path.iterdir()
                if d.is_dir() and EpuParser.images_disc_dir_pattern.search(str(path / d.name))
            ]
        )

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
    def _parse_microscope_data(root, namespaces) -> MicroscopeData | None:
        """
        Parse instrument information from EPU session XML.

        Note: Instrument information is typically not available in the main EpuSession.dm file
        but rather in the individual image metadata files (GridSquare XMLs, FoilHole XMLs, etc.).
        This method will attempt to find it but will likely return None for most EPU sessions.

        Args:
            root: XML root element
            namespaces: XML namespaces dictionary

        Returns:
            MicroscopeData object with instrument information or None if not found
        """
        try:

            def get_element_text(xpath):
                elements = root.xpath(xpath, namespaces=namespaces)
                return elements[0].text if elements else None

            # Try multiple XPath patterns to find instrument data in different EPU versions
            # Pattern 1: Direct elements (less common in EpuSession.dm)
            instrument_model = get_element_text(".//ns:InstrumentModel") or get_element_text(".//InstrumentModel")
            instrument_id = get_element_text(".//ns:InstrumentID") or get_element_text(".//InstrumentID")
            computer_name = get_element_text(".//ns:ComputerName") or get_element_text(".//ComputerName")

            # Pattern 2: Within microscopeData/instrument structure (more common in image files)
            if not any([instrument_model, instrument_id, computer_name]):
                instrument_model = get_element_text(".//microscopeData/instrument/InstrumentModel")
                instrument_id = get_element_text(".//microscopeData/instrument/InstrumentID")
                computer_name = get_element_text(".//microscopeData/instrument/ComputerName")

            # Pattern 3: Any instrument element anywhere in the document
            if not any([instrument_model, instrument_id, computer_name]):
                instrument_model = get_element_text(".//instrument/InstrumentModel")
                instrument_id = get_element_text(".//instrument/InstrumentID")
                computer_name = get_element_text(".//instrument/ComputerName")

            # If no data found, return None (this is expected for most EpuSession.dm files)
            if not any([instrument_model, instrument_id, computer_name]):
                logging.debug("No instrument information found in EPU session manifest (this is normal)")
                return None

            logging.info(
                f"Found instrument info in EPU session: Model={instrument_model}, ID={instrument_id}, "
                f"Computer={computer_name}"
            )

            return MicroscopeData(
                instrument_model=instrument_model,
                instrument_id=instrument_id,
                computer_name=computer_name,
            )

        except Exception as e:
            logging.debug(f"Could not parse instrument data from EPU session: {str(e)}")
            return None

    @staticmethod
    def parse_epu_session_manifest(manifest_path: str) -> AcquisitionData | None:
        try:
            namespaces = {
                "ns": "http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence",
                "common": "http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types",
                "i": "http://www.w3.org/2001/XMLSchema-instance",
                "z": "http://schemas.microsoft.com/2003/10/Serialization/",
            }

            tree = etree.parse(manifest_path)
            root = tree.getroot()

            def get_element_text(xpath):
                elements = root.xpath(xpath, namespaces=namespaces)
                return elements[0].text if elements else None

            atlas_id = get_element_text(".//ns:Samples/ns:_items/ns:SampleXml[1]/ns:AtlasId")
            storage_path = get_element_text(".//ns:StorageFolders/ns:_items/ns:StorageFolderXml[1]/ns:Path")

            if atlas_id and storage_path and atlas_id.startswith(storage_path):
                atlas_id = atlas_id[len(storage_path) :].replace("\\", "/")
            if atlas_id.startswith("/"):  # remove leading forward slash
                atlas_id = atlas_id.lstrip("/")

            start_time_str = get_element_text("./ns:StartDateTime")

            # Parse instrument information
            instrument_data = EpuParser._parse_microscope_data(root, namespaces)

            return AcquisitionData(
                name=get_element_text("./ns:Name"),
                id=get_element_text("./common:Id"),
                start_time=datetime.fromisoformat(start_time_str.rstrip("Z")) if start_time_str else None,
                atlas_path=atlas_id,
                storage_path=EpuParser.to_cygwin_path(storage_path) if storage_path else None,
                clustering_mode=get_element_text("./ns:ClusteringMode"),
                clustering_radius=get_element_text("./ns:ClusteringRadius"),
                instrument=instrument_data,
            )

        except Exception as e:
            logging.error(f"Failed to parse EPU session manifest: {str(e)}")
            return None

    @staticmethod
    def _find_atlas_file(expected_atlas_path: Path) -> Path | None:
        """
        Find Atlas.dm file at expected path or in nested subdirectories.

        This handles cases where atlas files are nested one level deeper than expected,
        such as atlas/atlas/... instead of atlas/...

        Args:
            expected_atlas_path: The expected path to Atlas.dm file

        Returns:
            Path to the actual Atlas.dm file if found, None otherwise
        """
        # First try the exact expected path
        if expected_atlas_path.exists():
            return expected_atlas_path

        # If not found, search in parent directory for atlas files with similar structure
        if expected_atlas_path.parent.exists():
            # Look for Atlas.dm files in subdirectories that match the expected structure
            atlas_pattern = expected_atlas_path.name  # e.g., "Atlas.dm"

            # Search up to 2 levels deep for Atlas.dm files
            for atlas_file in expected_atlas_path.parent.rglob(atlas_pattern):
                if atlas_file.is_file():
                    # Check if this could be the right atlas file by comparing directory structure
                    relative_path = atlas_file.relative_to(expected_atlas_path.parent)
                    expected_relative = expected_atlas_path.relative_to(expected_atlas_path.parent)

                    # If the relative paths match (allowing for extra intermediate directories)
                    if str(expected_relative) in str(relative_path):
                        logging.info(f"Found atlas file at alternative path: {atlas_file}")
                        return atlas_file

        # If still not found, try searching for any Atlas.dm in the general atlas directory area
        # Go up to find the base dataset directory
        base_dir = expected_atlas_path
        while base_dir.parent != base_dir and base_dir.name not in ["atlas", "metadata"]:
            base_dir = base_dir.parent

        # Search for any Atlas.dm files in atlas directories
        for atlas_file in base_dir.rglob("atlas/**/Atlas.dm"):
            if atlas_file.is_file():
                logging.info(f"Found atlas file in alternative atlas directory: {atlas_file}")
                return atlas_file

        return None

    @staticmethod
    def parse_atlas_manifest(atlas_path: str, grid_uuid: str):
        try:
            namespaces = {
                "ns": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence",
                "common": "http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types",
                "i": "http://www.w3.org/2001/XMLSchema-instance",
                "z": "http://schemas.microsoft.com/2003/10/Serialization/",
            }

            for event, element in etree.iterparse(
                atlas_path,
                tag="{http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence}AtlasSessionXml",
            ):
                if event == "end":

                    def get_element_text(xpath, el=element):
                        elements = el.xpath(xpath, namespaces=namespaces)
                        return elements[-1].text if elements else None

                    acquisition_date_str = get_element_text(".//ns:Atlas/ns:AcquisitionDateTime")

                    atlas_data = AtlasData(
                        id=get_element_text(".//common:Id"),
                        acquisition_date=datetime.fromisoformat(acquisition_date_str.replace("Z", "+00:00"))
                        if acquisition_date_str
                        else None,
                        storage_folder=get_element_text(".//ns:StorageFolder"),
                        description=get_element_text(".//ns:Description"),
                        name=get_element_text(".//ns:Name"),
                        grid_uuid=grid_uuid,
                        tiles=[],
                        gridsquare_positions=EpuParser._parse_gridsquare_positions(element),
                    )
                    atlas_data.tiles = [
                        EpuParser._parse_atlas_tile(tile, atlas_data.uuid)
                        for tile in element.xpath(
                            ".//ns:Atlas/ns:TilesEfficient/ns:_items/ns:TileXml", namespaces=namespaces
                        )
                        if tile.xpath(".//common:Id", namespaces=namespaces)
                    ]
                return atlas_data

        except Exception as e:
            logging.error(f"Failed to parse Atlas manifest: {str(e)}")
            return None

    @staticmethod
    def _parse_gridsquare_positions(atlas_xml):
        """Parse grid square positions from Atlas XML."""
        gridsquare_positions = {}

        namespaces = {
            "ns": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence",
            "gen": "http://schemas.datacontract.org/2004/07/System.Collections.Generic",
            "b": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence",
            "c": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Datamodel",
            "d": "http://schemas.datacontract.org/2004/07/System.Drawing",
        }

        tiles = atlas_xml.xpath(".//ns:Atlas/ns:TilesEfficient/ns:_items/ns:TileXml", namespaces=namespaces)

        for tile in tiles:
            if (nodes := tile.find(".//ns:Nodes", namespaces=namespaces)) is None:
                continue

            # Get key-value pairs using local-name() to match the node-naming pattern
            pairs = nodes.xpath(
                ".//gen:*[starts-with(local-name(), 'KeyValuePairOfintNodeXml')]", namespaces=namespaces
            )
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
                        center=center_tuple, physical=physical_tuple, size=size_tuple, rotation=rotation
                    )

                except (AttributeError, IndexError, ValueError, TypeError) as e:
                    logging.error(f"Failed to parse grid square position: {str(e)}")
                    continue

        return gridsquare_positions

    @staticmethod
    def _parse_atlas_tile(tile_xml, atlas_uuid: str) -> AtlasTileData | None:
        try:
            namespaces = {
                "ns": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Persistence",
                "common": "http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types",
                "draw": "http://schemas.datacontract.org/2004/07/System.Drawing",
                "generic": "http://schemas.datacontract.org/2004/07/System.Collections.Generic",
                "model": "http://schemas.datacontract.org/2004/07/Applications.SciencesAppsShared.GridAtlas.Datamodel",
            }

            def get_element_text(xpath, xml=tile_xml):
                elements = xml.xpath(xpath, namespaces=namespaces)
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

            atlastile_data = AtlasTileData(
                id=tile_id,
                atlas_uuid=atlas_uuid,
                tile_position=AtlasTilePosition(
                    position=position_tuple,
                    size=size_tuple,
                ),
                file_format=get_element_text("./ns:TileImageReference/common:FileFormat"),
                base_filename=get_element_text("./ns:TileImageReference/common:BaseFileName"),
            )

            def _get_gridsquare_position_data(tile_positions) -> list[AtlasTileGridSquarePosition]:
                result = []
                for t in tile_positions:
                    if get_element_text("./ns:TileId", xml=t) == tile_id and t.xpath(
                        "./ns:NodePosition", namespaces=namespaces
                    ):
                        n = t.xpath("./ns:NodePosition", namespaces=namespaces)[0]
                        result.append(
                            AtlasTileGridSquarePosition(
                                position=(
                                    int(float(get_element_text("./model:Center/draw:x", xml=n))),
                                    int(float(get_element_text("./model:Center/draw:y", xml=n))),
                                ),
                                size=(
                                    int(float(get_element_text("./model:Size/draw:width", xml=n))),
                                    int(float(get_element_text("./model:Size/draw:height", xml=n))),
                                ),
                            )
                        )
                return result

            gridsquare_positions = {}
            for gs in tile_xml.xpath(
                "./ns:Nodes/KeyValuePairs/*[starts-with(local-name(), 'KeyValuePairOfintNodeXml')]",
                namespaces=namespaces,
            ):
                gs_id = get_element_text("./generic:key", xml=gs)
                gridsquare_positions[gs_id] = _get_gridsquare_position_data(
                    gs.xpath("./generic:value/ns:TilePositions/ns:_items/ns:TilePositionXml", namespaces=namespaces)
                )

            atlastile_data.gridsquare_positions = gridsquare_positions
            return atlastile_data

        except Exception as e:
            logging.error(f"Failed to parse tile: {str(e)}")
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
                "def": "http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence",
                "i": "http://www.w3.org/2001/XMLSchema-instance",
                "z": "http://schemas.microsoft.com/2003/10/Serialization/",
                "common": "http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types",
                "a": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
                "b": "http://schemas.datacontract.org/2004/07/System.Collections.Generic",
                "c": "http://schemas.datacontract.org/2004/07/System.Drawing",
                "shared": "http://schemas.datacontract.org/2004/07/Fei.SharedObjects",
            }

            tree = etree.parse(path)
            root = tree.getroot()

            def get_element_text(xpath, elem=root):
                try:
                    elements = elem.xpath(xpath, namespaces=namespaces)
                    return elements[0].text if elements else None
                except etree.XPathEvalError as e:
                    logging.error(f"XPath error for expression '{xpath}': {str(e)}")
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
                z=safe_float(get_element_text("//def:Position/shared:Z")),
            )

            image_path_str = get_element_text("//def:GridSquareImagePath")
            image_path = Path(EpuParser.to_cygwin_path(image_path_str)) if image_path_str else None

            selected_str = get_element_text("//def:Selected")
            unusable_str = get_element_text("//def:Unusable")
            selected = selected_str.lower() == "true" if selected_str else False
            unusable = unusable_str.lower() == "true" if unusable_str else False

            # Parse foil hole positions
            # -------------------------
            foilhole_positions: dict[int, FoilHolePosition] = {}

            # Find all KeyValuePair elements
            kvp_xpath = (
                ".//def:TargetLocationsEfficient/a:m_serializationArray/"
                "*[starts-with(local-name(), 'KeyValuePairOfintTargetLocation')]"
            )
            kvp_elements = root.xpath(kvp_xpath, namespaces=namespaces)

            for element in kvp_elements:
                try:
                    if (
                        key_elem := element.find(
                            "{http://schemas.datacontract.org/2004/07/System.Collections.Generic}key"
                        )
                    ) is None:
                        continue
                    fh_id = int(key_elem.text)

                    if (
                        value_elem := element.find(
                            "{http://schemas.datacontract.org/2004/07/System.Collections.Generic}value"
                        )
                    ) is None:
                        continue

                    # Check IsNearGridBar
                    is_near_grid_bar = (
                        value_elem.find(
                            "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}IsNearGridBar"
                        )
                        is not None
                        and value_elem.find(
                            "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}IsNearGridBar"
                        ).text.lower()
                        == "true"
                    )

                    # Find stage position
                    if (
                        stage_pos := value_elem.find(
                            "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}StagePosition"
                        )
                    ) is not None:
                        stage_x = safe_float(
                            stage_pos.find("{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}X").text
                        )
                        stage_y = safe_float(
                            stage_pos.find("{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}Y").text
                        )
                    else:
                        stage_x = stage_y = None

                    # Find pixel position
                    if (
                        pixel_center := value_elem.find(
                            "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}PixelCenter"
                        )
                    ) is not None:
                        pixel_x = safe_float(
                            pixel_center.find("{http://schemas.datacontract.org/2004/07/System.Drawing}x").text
                        )
                        pixel_y = safe_float(
                            pixel_center.find("{http://schemas.datacontract.org/2004/07/System.Drawing}y").text
                        )
                    else:
                        continue

                    if (
                        pixel_size := value_elem.find(
                            "{http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence}PixelWidthHeight"
                        )
                    ) is not None:
                        diameter = safe_float(
                            pixel_size.find("{http://schemas.datacontract.org/2004/07/System.Drawing}width").text
                        )
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
                    logging.error(f"Error processing foil hole {fh_id}: {str(e)}")
                    continue

            metadata = GridSquareMetadata(
                atlas_node_id=int(get_element_text("//def:AtlasNodeId") or 0),
                stage_position=stage_position,
                state=get_element_text("//def:State"),
                rotation=safe_float(get_element_text("//def:Rotation")),
                image_path=image_path,
                selected=selected,
                unusable=unusable,
                foilhole_positions=foilhole_positions,
            )

            return metadata

        except Exception as e:
            logging.error(f"Failed to parse gridsquare metadata: {str(e)}")
            return None

    @staticmethod
    def parse_gridsquare_manifest(manifest_path: str) -> GridSquareManifest | None:
        try:
            namespaces = {
                "ms": "http://schemas.datacontract.org/2004/07/Fei.SharedObjects",
                "arr": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
            }

            for event, element in etree.iterparse(
                manifest_path, tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"
            ):
                if event == "end":

                    def get_element_text(xpath, el=element):
                        elements = el.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    def get_custom_value(key):
                        xpath = f".//ms:CustomData//arr:KeyValueOfstringanyType[arr:Key='{key}']/arr:Value"
                        return get_element_text(xpath)

                    acquisition_date_str = get_element_text(
                        ".//ms:microscopeData/ms:acquisition/ms:acquisitionDateTime"
                    )

                    return GridSquareManifest(
                        acquisition_datetime=datetime.fromisoformat(acquisition_date_str.replace("Z", "+00:00"))
                        if acquisition_date_str
                        else None,
                        defocus=float(get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus"))
                        if get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus")
                        else None,
                        magnification=float(
                            get_element_text(
                                ".//ms:microscopeData/ms:optics/ms:TemMagnification/ms:NominalMagnification"
                            )
                        )
                        if get_element_text(
                            ".//ms:microscopeData/ms:optics/ms:TemMagnification/ms:NominalMagnification"
                        )
                        else None,
                        pixel_size=float(get_element_text(".//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue"))
                        if get_element_text(".//ms:SpatialScale/ms:pixelSize/ms:x/ms:numericValue")
                        else None,
                        detector_name=get_custom_value("DetectorCommercialName")
                        if get_custom_value("DetectorCommercialName")
                        else None,
                        applied_defocus=float(get_custom_value("AppliedDefocus"))
                        if get_custom_value("AppliedDefocus")
                        else None,
                        data_dir=Path(manifest_path).parent,
                    )

        except Exception as e:
            logging.error(f"Failed to parse grid square manifest: {str(e)}")
            return None

    @staticmethod
    def parse_foilhole_manifest(manifest_path: str) -> FoilHoleData | None:
        try:
            namespaces = {
                "ms": "http://schemas.datacontract.org/2004/07/Fei.SharedObjects",
                "arr": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
                "draw": "http://schemas.datacontract.org/2004/07/System.Drawing",
                "b": "http://schemas.datacontract.org/2004/07/Fei.Types",
                "c": "http://schemas.datacontract.org/2004/07/System.Drawing",
            }

            for event, element in etree.iterparse(
                manifest_path, tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"
            ):
                if event == "end":

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
                        center_x=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:x"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:x"
                        )
                        else None,
                        center_y=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:y"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Center/c:y"
                        )
                        else None,
                        quality=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Quality"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Quality"
                        )
                        else None,
                        rotation=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Rotation"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Rotation"
                        )
                        else None,
                        size_width=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:width"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:width"
                        )
                        else None,
                        size_height=float(
                            get_element_text(
                                ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:height"
                            )
                        )
                        if get_element_text(
                            ".//arr:KeyValueOfstringanyType[arr:Key='FindFoilHoleCenterResults']/arr:Value/b:Size/c:height"
                        )
                        else None,
                    )

        except Exception as e:
            logging.error(f"Failed to parse foil hole manifest: {str(e)}")
            return None

    @staticmethod
    def parse_microscope_from_image_metadata(manifest_path: str) -> MicroscopeData | None:
        """
        Extract instrument information from image metadata files (GridSquare, FoilHole, Micrograph XMLs).

        Args:
            manifest_path: Path to the XML image metadata file

        Returns:
            MicroscopeData object with instrument information or None if not found
        """
        try:
            namespaces = {
                "ms": "http://schemas.datacontract.org/2004/07/Fei.SharedObjects",
            }

            for event, element in etree.iterparse(
                manifest_path, tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"
            ):
                if event == "end":

                    def get_element_text(xpath, el=element):
                        elements = el.xpath(xpath, namespaces=namespaces)
                        return elements[0].text if elements else None

                    # Extract instrument information from the instrument section
                    instrument_model = get_element_text(".//ms:microscopeData/ms:instrument/ms:InstrumentModel")
                    instrument_id = get_element_text(".//ms:microscopeData/ms:instrument/ms:InstrumentID")
                    computer_name = get_element_text(".//ms:microscopeData/ms:instrument/ms:ComputerName")

                    # Alternative patterns without namespace
                    if not any([instrument_model, instrument_id, computer_name]):
                        instrument_model = get_element_text(".//instrument/InstrumentModel")
                        instrument_id = get_element_text(".//instrument/InstrumentID")
                        computer_name = get_element_text(".//instrument/ComputerName")

                    if any([instrument_model, instrument_id, computer_name]):
                        logging.debug(
                            f"Found instrument info in {manifest_path}: Model={instrument_model}, "
                            f"ID={instrument_id}, Computer={computer_name}"
                        )
                        return MicroscopeData(
                            instrument_model=instrument_model,
                            instrument_id=instrument_id,
                            computer_name=computer_name,
                        )

        except Exception as e:
            logging.debug(f"Could not parse instrument data from {manifest_path}: {str(e)}")

        return None

    @staticmethod
    def parse_micrograph_manifest(manifest_path: str) -> MicrographManifest | None:
        try:
            namespaces = {
                "ms": "http://schemas.datacontract.org/2004/07/Fei.SharedObjects",
                "arr": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
                "draw": "http://schemas.datacontract.org/2004/07/System.Drawing",
            }

            for event, element in etree.iterparse(
                manifest_path, tag="{http://schemas.datacontract.org/2004/07/Fei.SharedObjects}MicroscopeImage"
            ):
                if event == "end":

                    def get_element_text(xpath, el=element):
                        elements = el.xpath(xpath, namespaces=namespaces)
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
                            get_element_text(".//ms:microscopeData/ms:acquisition/ms:acquisitionDateTime").replace(
                                "Z", "+00:00"
                            )
                        ),
                        defocus=float(get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus"))
                        if get_element_text(".//ms:microscopeData/ms:optics/ms:Defocus")
                        else None,
                        detector_name=get_custom_value("DetectorCommercialName") or "Unknown",
                        energy_filter=get_element_text(".//ms:microscopeData/ms:optics/ms:EFTEMOn") == "true",
                        phase_plate=get_custom_value("PhasePlateUsed") == "true",
                        image_size_x=int(readout_area.xpath(".//draw:width", namespaces=namespaces)[0].text)
                        if readout_area.xpath(".//draw:width", namespaces=namespaces)
                        else None,
                        image_size_y=int(readout_area.xpath(".//draw:height", namespaces=namespaces)[0].text)
                        if readout_area.xpath(".//draw:height", namespaces=namespaces)
                        else None,
                        binning_x=int(binning.xpath(".//draw:x", namespaces=namespaces)[0].text or 1),
                        binning_y=int(binning.xpath(".//draw:y", namespaces=namespaces)[0].text or 1),
                    )

        except Exception as e:
            logging.error(f"Failed to parse micrograph manifest: {str(e)}")
            return None

    @staticmethod
    def parse_epu_output_dir(datastore: InMemoryDataStore):
        """Parse the entire EPU output directory, containing one or more grids/samples
        collected over the duration of a given microscopy session.

        When you have a parent-child relationship between classes where one class inherits from another,
        you can use the parent class type for the parameter annotation.
        This is more concise and leverages the Liskov Substitution Principle, making:
        `datastore: InMemoryDataStore` equivalent to but preferred over:
        `datastore: InMemoryDataStore | PersistentDataStore`
        """

        # Start with locating all EpuSession.dm files - init a grid for each found
        for epu_session_manifest in list(datastore.root_dir.glob("**/*EpuSession.dm")):
            EpuParser.parse_grid_dir(str(Path(epu_session_manifest).parent), datastore)

        return datastore

    @staticmethod
    def parse_grid_dir(grid_data_dir: str, datastore: InMemoryDataStore) -> str:
        """
        Parse an EPU grid directory and populate the provided datastore.

        Args:
            grid_data_dir: Path to the grid data directory
            datastore: The datastore to populate

        Returns:
            str: The UUID of the created grid
        """
        # 1. Create the grid
        grid = GridData(data_dir=Path(grid_data_dir).resolve())

        # 1.1 Parse EpuSession.dm
        epu_manifest_path = str(grid.data_dir / "EpuSession.dm")
        grid.acquisition_data = EpuParser.parse_epu_session_manifest(epu_manifest_path)

        # TODO This is hacky and non-obvious - address as techdebt sometime
        #  Overwrite `uuid` generated within `parse_epu_session_manifest` method when `new AcquisitionData()` is
        #  instantiated with the actual acquisition uuid.
        grid.acquisition_data.uuid = datastore.acquisition.uuid

        # Build out the absolute atlas_dir path
        if grid.acquisition_data.atlas_path:
            grid.atlas_dir = Path(Path(grid_data_dir) / Path("..") / Path(grid.acquisition_data.atlas_path)).resolve()
            if not grid.atlas_dir.exists():
                grid.atlas_dir = Path(
                    Path(grid_data_dir) / Path("../..") / Path(grid.acquisition_data.atlas_path)
                ).resolve()

        # 1.2 Parse Atlas.dm
        if grid.atlas_dir and grid.acquisition_data.atlas_path:
            atlas_file_path = EpuParser._find_atlas_file(grid.atlas_dir)
            if atlas_file_path:
                grid.atlas_data = EpuParser.parse_atlas_manifest(str(atlas_file_path), grid.uuid)
            else:
                logging.warning(
                    f"Atlas file not found at {grid.atlas_dir} or nested subdirectories. Skipping atlas parsing."
                )
                grid.atlas_data = None

        # Add grid to datastore
        datastore.create_grid(grid)

        if grid.atlas_data is not None:
            datastore.create_atlas(grid.atlas_data)
            for atlastile in grid.atlas_data.tiles:
                datastore.create_atlastile(atlastile)
            gs_uuid_map = {}
            for gsid, gsp in grid.atlas_data.gridsquare_positions.items():
                gridsquare = GridSquareData(
                    gridsquare_id=str(gsid),
                    metadata=None,
                    grid_uuid=grid.uuid,
                    center_x=gsp.center[0],
                    center_y=gsp.center[1],
                    size_width=gsp.size[0],
                    size_height=gsp.size[1],
                )
                gs_uuid_map[str(gsid)] = gridsquare.uuid
                datastore.create_gridsquare(gridsquare)
            for atlastile in grid.atlas_data.tiles:
                for gsid, gs_tile_pos in atlastile.gridsquare_positions.items():
                    for pos in gs_tile_pos:
                        datastore.link_atlastile_to_gridsquare(
                            AtlasTileGridSquarePositionData(
                                gridsquare_uuid=gs_uuid_map[gsid],
                                tile_uuid=atlastile.uuid,
                                position=pos.position,
                                size=pos.size,
                            )
                        )

        # 2. Parse all gridsquare metadata from /Metadata directory
        metadata_dir_path = str(grid.data_dir / "Metadata")
        for gridsquare_id, filename in EpuParser.parse_gridsquares_metadata_dir(metadata_dir_path):
            logging.debug(f"Discovered gridsquare ID: {gridsquare_id} from file {filename}")
            gridsquare_metadata = EpuParser.parse_gridsquare_metadata(filename)

            # Create GridSquareData with ID and metadata
            if grid.atlas_data is not None:
                gridsquare = GridSquareData(
                    gridsquare_id=gridsquare_id,
                    metadata=gridsquare_metadata,
                    grid_uuid=grid.uuid,  # Set reference to parent grid
                    center_x=grid.atlas_data.gridsquare_positions[int(gridsquare_id)].center[0]
                    if grid.atlas_data.gridsquare_positions.get(int(gridsquare_id)) is not None
                    else None,
                    center_y=grid.atlas_data.gridsquare_positions[int(gridsquare_id)].center[1]
                    if grid.atlas_data.gridsquare_positions.get(int(gridsquare_id)) is not None
                    else None,
                    size_width=grid.atlas_data.gridsquare_positions[int(gridsquare_id)].size[0]
                    if grid.atlas_data.gridsquare_positions.get(int(gridsquare_id)) is not None
                    else None,
                    size_height=grid.atlas_data.gridsquare_positions[int(gridsquare_id)].size[1]
                    if grid.atlas_data.gridsquare_positions.get(int(gridsquare_id)) is not None
                    else None,
                )
            else:
                gridsquare = GridSquareData(
                    gridsquare_id=gridsquare_id,
                    metadata=gridsquare_metadata,
                    grid_uuid=grid.uuid,  # Set reference to parent grid
                )

            if grid.atlas_data.gridsquare_positions.get(int(gridsquare_id)) is not None:
                found_grid_square = datastore.find_gridsquare_by_natural_id(gridsquare_id)
                gridsquare.uuid = found_grid_square.uuid
                datastore.update_gridsquare(gridsquare)
            else:
                datastore.create_gridsquare(gridsquare)
            logging.debug(f"Added gridsquare: {gridsquare_id} (uuid: {gridsquare.uuid})")
            for fh_id, fh_position in gridsquare_metadata.foilhole_positions.items():
                fh = FoilHoleData(
                    id=str(fh_id),
                    gridsquare_id=gridsquare_id,
                    gridsquare_uuid=gridsquare.uuid,
                    x_location=fh_position.x_location,
                    y_location=fh_position.y_location,
                    x_stage_position=fh_position.x_stage_position,
                    y_stage_position=fh_position.y_stage_position,
                    diameter=fh_position.diameter,
                    is_near_grid_bar=fh_position.is_near_grid_bar,
                )
                datastore.create_foilhole(fh)

        # 3. Parse gridsquare manifests and associated data
        instrument_extracted = False  # Track if we've already extracted instrument info for this grid
        for gridsquare_manifest_path in list(grid.data_dir.glob("Images-Disc*/GridSquare_*/GridSquare_*_*.xml")):
            gridsquare_manifest = EpuParser.parse_gridsquare_manifest(str(gridsquare_manifest_path))
            gridsquare_id = re.search(EpuParser.gridsquare_dir_pattern, str(gridsquare_manifest_path)).group(1)
            gridsquare = datastore.find_gridsquare_by_natural_id(gridsquare_id)

            if gridsquare:
                gridsquare.manifest = gridsquare_manifest
                datastore.update_gridsquare(gridsquare)
                logging.debug(f"Updated gridsquare manifest: ID: {gridsquare_id} (UUID: {gridsquare.uuid})")

                # Extract instrument information if not already found
                if not instrument_extracted:
                    instrument = EpuParser.parse_microscope_from_image_metadata(str(gridsquare_manifest_path))
                    if instrument:
                        grid.acquisition_data.instrument = instrument
                        logging.info(
                            f"Extracted instrument info: Model={instrument.instrument_model}, "
                            f"ID={instrument.instrument_id}"
                        )
                        if hasattr(datastore, "api_client"):
                            try:
                                datastore.api_client.update_acquisition(grid.acquisition_data)
                                logging.info(
                                    f"Updated acquisition {grid.acquisition_data.id} with instrument information"
                                )
                            except Exception as e:
                                logging.error(f"Failed to update acquisition via API: {e}")
                        instrument_extracted = True

                # 3.1 Parse foilholes for this gridsquare
                foilhole_manifest_paths = sorted(
                    grid.data_dir.glob(f"Images-Disc*/GridSquare_{gridsquare_id}/FoilHoles/FoilHole_*_*_*.xml"),
                    key=lambda p: p.name,  # Sort by filename to get the latest version
                )

                for foilhole_manifest_path in foilhole_manifest_paths:
                    foilhole_id_match = re.search(EpuParser.foilhole_xml_file_pattern, str(foilhole_manifest_path))
                    foilhole_id = foilhole_id_match.group(1)

                    foilhole = EpuParser.parse_foilhole_manifest(str(foilhole_manifest_path))
                    foilhole.gridsquare_id = gridsquare_id
                    foilhole.gridsquare_uuid = gridsquare.uuid

                    # Extract instrument information if not already found
                    if not instrument_extracted:
                        instrument = EpuParser.parse_microscope_from_image_metadata(str(foilhole_manifest_path))
                        if instrument:
                            grid.acquisition_data.instrument = instrument
                            logging.info(
                                f"Extracted instrument info: Model={instrument.instrument_model}, "
                                f"ID={instrument.instrument_id}"
                            )
                            if hasattr(datastore, "api_client"):
                                try:
                                    datastore.api_client.update_acquisition(grid.acquisition_data)
                                    logging.info(
                                        f"Updated acquisition {grid.acquisition_data.id} with instrument information"
                                    )
                                except Exception as e:
                                    logging.error(f"Failed to update acquisition via API: {e}")
                            instrument_extracted = True

                    # Add to datastore using upsert method
                    success = datastore.upsert_foilhole(foilhole)
                    if success:
                        logging.debug(f"Upserted foilhole: {foilhole_id} (uuid: {foilhole.uuid})")
                    else:
                        logging.warning(
                            f"Failed to upsert foilhole {foilhole_id} - "
                            f"parent gridsquare {foilhole.gridsquare_uuid} not found"
                        )

                # 3.2 Parse micrographs for this gridsquare
                for micrograph_manifest_path in list(
                    grid.data_dir.glob(f"Images-Disc*/GridSquare_{gridsquare_id}/Data/FoilHole_*_Data_*_*_*_*.xml")
                ):
                    micrograph_manifest = EpuParser.parse_micrograph_manifest(str(micrograph_manifest_path))
                    match = re.search(EpuParser.micrograph_xml_file_pattern, str(micrograph_manifest_path))
                    foilhole_id = match.group(1)
                    location_id = match.group(2)
                    foilhole = datastore.find_foilhole_by_natural_id(foilhole_id)
                    if not foilhole:
                        logging.warning(
                            f"Could not find foilhole by natural ID {foilhole_id}, "
                            f"skipping micrograph creation for micrograph {micrograph_manifest.unique_id}"
                        )
                        continue

                    # Extract instrument information if not already found
                    if not instrument_extracted:
                        instrument = EpuParser.parse_microscope_from_image_metadata(str(micrograph_manifest_path))
                        if instrument:
                            grid.acquisition_data.instrument = instrument
                            logging.info(
                                f"Extracted instrument info: Model={instrument.instrument_model}, "
                                f"ID={instrument.instrument_id}"
                            )
                            if hasattr(datastore, "api_client"):
                                try:
                                    datastore.api_client.update_acquisition(grid.acquisition_data)
                                    logging.info(
                                        f"Updated acquisition {grid.acquisition_data.id} with instrument information"
                                    )
                                except Exception as e:
                                    logging.error(f"Failed to update acquisition via API: {e}")
                            instrument_extracted = True

                    micrograph = MicrographData(
                        id=micrograph_manifest.unique_id,
                        gridsquare_id=gridsquare_id,
                        foilhole_id=foilhole_id,
                        foilhole_uuid=foilhole.uuid,
                        location_id=location_id,
                        high_res_path=Path(""),
                        manifest_file=micrograph_manifest_path,
                        manifest=micrograph_manifest,
                    )

                    success = datastore.upsert_micrograph(micrograph)
                    if not success:
                        logging.warning(f"Failed to upsert micrograph {micrograph.id}")
                    logging.debug(f"Added micrograph: {micrograph_manifest.unique_id} (uuid: {micrograph.uuid})")
            else:
                logging.warning(f"Found gridsquare manifest for {gridsquare_id} but no matching gridsquare metadata")

        return grid.uuid


if __name__ == "__main__":
    logging.warning("This module is not meant to be run directly. Import and use its components instead.")
    sys.exit(1)
