import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import os
import re

from pyright.cli import entrypoint


@dataclass
class SupervisorInfo:
    """Information about the supervisor session"""
    date: datetime
    session_id: str
    project_name: str

    @classmethod
    def from_string(cls, supervisor_str: str) -> Optional['SupervisorInfo']:
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
        except (ValueError, IndexError):
            return None


@dataclass
class MicroscopeSettings:
    """Microscope settings from a grid square"""
    acquisition_datetime: datetime
    dose_on_camera: float
    dose_rate: float
    applied_defocus: float
    detector_name: str
    beam_diameter: float
    magnification: int
    acceleration_voltage: int
    stage_position: Dict[str, float]


@dataclass
class GridSquare:
    id: int
    filename: str
    file_size: int
    is_detailed: bool
    position: Optional[Tuple[float, float]] = None
    microscope_settings: Optional[MicroscopeSettings] = None


@dataclass
class Sample:
    id: int
    atlas_id: str
    alignment_timestamp: datetime
    grid_squares: Dict[int, GridSquare]
    grid_geometry: str
    supervisor_info: Optional[SupervisorInfo] = None


@dataclass
class EPUSession:
    id: int
    name: str
    start_datetime: datetime
    samples: List[Sample]
    storage_path: str
    clustering_mode: str
    clustering_radius: float
    image_file_format: str


class EPUSessionParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.ns = {
            'ns': 'http://schemas.datacontract.org/2004/07/Applications.Epu.Persistence',
            'ct': 'http://schemas.datacontract.org/2004/07/Fei.Applications.Common.Types',
            'i': 'http://www.w3.org/2001/XMLSchema-instance'
        }

    def _parse_supervisor_info(self, path: str) -> Optional[SupervisorInfo]:
        match = re.search(r'Supervisor_([^/\\]+)', path)
        if match:
            return SupervisorInfo.from_string(match.group(1))
        return None

    def _parse_microscope_settings(self, file_path: str) -> Optional[MicroscopeSettings]:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Parse custom data section
            custom_data = {}
            for item in root.findall('.//{*}KeyValueOfstringanyType'):
                key = item.find('.//{*}Key').text
                value_elem = item.find('.//{*}Value')
                if value_elem is not None and 'type' in value_elem.attrib:
                    value_type = value_elem.attrib['type'].split(':')[-1]
                    if value_type == 'double':
                        custom_data[key] = float(value_elem.text)
                    elif value_type == 'boolean':
                        custom_data[key] = value_elem.text.lower() == 'true'
                    else:
                        custom_data[key] = value_elem.text

            # Get stage position
            stage = root.find('.//{*}Position')
            stage_position = {}
            if stage is not None:
                for axis in ['A', 'B', 'X', 'Y', 'Z']:
                    elem = stage.find(f'./{axis}')
                    stage_position[axis] = float(elem.text) if elem is not None else 0.0

            # Get microscope data
            microscope_data = root.find('.//{*}microscopeData')
            if microscope_data is None:
                return None

            acquisition_elem = microscope_data.find('.//acquisitionDateTime')
            acquisition_time = datetime.fromisoformat(
                acquisition_elem.text.replace('Z', '+00:00')
            ) if acquisition_elem is not None else datetime.now()

            beam_elem = microscope_data.find('.//BeamDiameter')
            beam_diameter = float(beam_elem.text) if beam_elem is not None else 0.0

            mag_elem = microscope_data.find('.//NominalMagnification')
            magnification = int(mag_elem.text) if mag_elem is not None else 0

            voltage_elem = microscope_data.find('.//AccelerationVoltage')
            acceleration_voltage = int(voltage_elem.text) if voltage_elem is not None else 0

            return MicroscopeSettings(
                acquisition_datetime=acquisition_time,
                dose_on_camera=custom_data.get('DoseOnCamera', 0.0),
                dose_rate=custom_data.get('DoseRate', 0.0),
                applied_defocus=custom_data.get('AppliedDefocus', 0.0),
                detector_name=custom_data.get('DetectorCommercialName', ''),
                beam_diameter=beam_diameter,
                magnification=magnification,
                acceleration_voltage=acceleration_voltage,
                stage_position=stage_position
            )
        except (ET.ParseError, FileNotFoundError):
            return None

    def parse(self) -> EPUSession:
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        # Extract basic session info
        session_id = int(root.find('./ct:Id', self.ns).text)
        name = root.find('./ns:Name', self.ns).text
        start_time = datetime.fromisoformat(root.find('./ns:StartDateTime', self.ns).text.rstrip('Z'))

        # Get clustering info
        clustering_mode = root.find('./ns:ClusteringMode', self.ns).text
        clustering_radius = float(root.find('./ns:ClusteringRadius', self.ns).text)
        image_file_format = root.find('./ns:ImageFileFormat', self.ns).text

        # Get storage path
        storage_folder = root.find('.//ns:StorageFolderXml/ns:Path', self.ns)
        storage_path = storage_folder.text if storage_folder is not None else ""

        # Parse samples
        samples = []
        samples_element = root.find('.//ns:Samples', self.ns)
        if samples_element is not None:
            for sample_elem in samples_element.findall('.//ns:SampleXml', self.ns):
                id_elem = sample_elem.find('.//ct:Id', self.ns)
                if id_elem is None:
                    continue

                sample_id = int(id_elem.text)
                atlas_id = sample_elem.find('.//ns:AtlasId', self.ns).text
                alignment_timestamp = datetime.fromisoformat(
                    sample_elem.find('.//ns:AlignmentTimeStamp', self.ns).text.rstrip('Z')
                )
                grid_geometry = sample_elem.find('.//ns:GridGeometry', self.ns).text

                # Extract supervisor info from atlas path
                supervisor_info = self._parse_supervisor_info(atlas_id)

                # Parse grid squares
                grid_squares = {}
                grid_squares_elem = sample_elem.find('.//ns:GridSquares', self.ns)
                if grid_squares_elem is not None:
                    pairs = grid_squares_elem.findall(
                        './/b:KeyValuePairOfintSerializedReferenceOfGridSquareXml_PsqDC3X0m6koiAE_P',
                        {'b': 'http://schemas.datacontract.org/2004/07/System.Collections.Generic'})

                    for pair in pairs:
                        square_id = int(pair.find('b:key',
                                                  {
                                                      'b': 'http://schemas.datacontract.org/2004/07/System.Collections.Generic'}).text)
                        filename = pair.find('.//ct:FileName', self.ns).text
                        filename = filename.replace('\\', '/')
                        epu_session_dir = os.path.dirname(os.path.abspath(self.file_path))
                        base_filename = os.path.basename(filename)
                        full_path = os.path.join(epu_session_dir, "Metadata", base_filename)

                        file_size = 0
                        try:
                            if os.path.exists(full_path):
                                file_size = os.path.getsize(full_path)
                            else:
                                # print(f"File does not exist: {full_path}")
                                pass
                        except OSError as e:
                            # Only print errors that aren't about missing files
                            if e.errno != 2:  # errno 2 is "No such file or directory"
                                print(f"Error accessing {full_path}: {e}")

                        # Files around 2.8KB are baseline, >100KB are detailed
                        is_detailed = file_size > 100000

                        # For detailed squares, try to extract microscope settings
                        microscope_settings = None
                        if is_detailed:
                            try:
                                microscope_settings = self._parse_microscope_settings(full_path)
                            except Exception as e:
                                print(f"Could not parse microscope settings from {full_path}: {e}")

                        # Extract position if available
                        position = None
                        position_elem = pair.find('.//ns:Position', self.ns)
                        if position_elem is not None:
                            try:
                                x = float(position_elem.find('.//ns:X', self.ns).text)
                                y = float(position_elem.find('.//ns:Y', self.ns).text)
                                position = (x, y)
                            except (AttributeError, ValueError) as e:
                                print(f"Could not parse position for grid square {square_id}: {e}")

                        grid_squares[square_id] = GridSquare(
                            id=square_id,
                            filename=filename,
                            file_size=file_size,
                            is_detailed=is_detailed,
                            position=position,
                            microscope_settings=microscope_settings
                        )

                sample = Sample(
                    id=sample_id,
                    atlas_id=atlas_id,
                    alignment_timestamp=alignment_timestamp,
                    grid_squares=grid_squares,
                    grid_geometry=grid_geometry,
                    supervisor_info=supervisor_info
                )
                samples.append(sample)

        return EPUSession(
            id=session_id,
            name=name,
            start_datetime=start_time,
            samples=samples,
            storage_path=storage_path,
            clustering_mode=clustering_mode,
            clustering_radius=clustering_radius,
            image_file_format=image_file_format
        )


def print_session_summary(session: EPUSession):
    print(f"Session: {session.name}")
    print(f"Started: {session.start_datetime}")
    print(f"Storage: {session.storage_path}")
    print(f"Image format: {session.image_file_format}")
    print(f"Clustering mode: {session.clustering_mode} (radius: {session.clustering_radius})")
    print("\nSamples:")

    for sample in session.samples:
        print(f"\nSample {sample.id}:")
        if sample.supervisor_info:
            print(f"  Supervisor Session:")
            print(f"    Date: {sample.supervisor_info.date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Project: {sample.supervisor_info.project_name}")
        print(f"  Atlas ID: {sample.atlas_id}")
        print(f"  Grid geometry: {sample.grid_geometry}")
        print(f"  Alignment time: {sample.alignment_timestamp}")

        detailed_squares = [square for square in sample.grid_squares.values() if square.is_detailed]

        print(f"\n  Grid squares summary:")
        print(f"    Total squares: {len(sample.grid_squares)}")
        print(f"    Detailed squares: {len(detailed_squares)}")

        if detailed_squares:
            print(f"\n  Detailed grid squares (>100KB):")
            for square in sorted(detailed_squares, key=lambda x: x.id):
                size_mb = square.file_size / (1024 * 1024)
                pos_str = f" at ({square.position[0]:.6f}, {square.position[1]:.6f})" if square.position else ""
                print(f"\n    {square.id}: {square.filename} ({size_mb:.2f}MB){pos_str}")

                if square.microscope_settings:
                    ms = square.microscope_settings
                    print(f"      Acquisition time: {ms.acquisition_datetime}")
                    print(f"      Detector: {ms.detector_name}")
                    print(f"      Dose rate: {ms.dose_rate:.2f}")
                    print(f"      Dose on camera: {ms.dose_on_camera:.2f}")
                    print(f"      Applied defocus: {ms.applied_defocus:.2e}")
                    print(f"      Magnification: {ms.magnification}x")
                    print(f"      Beam diameter: {ms.beam_diameter:.2e}")
                    print(f"      Acceleration voltage: {ms.acceleration_voltage}kV")
                    if ms.stage_position:
                        stage_pos = [f"{k}: {v:.6f}" for k, v in ms.stage_position.items()]
                        print(f"      Stage position: {', '.join(stage_pos)}")


def main():
    # acquisition_dir_path = "tests/testdata/metadata_Supervisor_20250108_101446_62_cm40593-1_EPU"
    acquisition_dir_path = "tests/testdata/example"


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
