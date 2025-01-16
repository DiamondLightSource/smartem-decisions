import xml.etree.ElementTree as ET
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class MicroscopeImageData:
    acquisition_datetime: datetime
    dose_on_camera: float
    dose_rate: float
    applied_defocus: float
    detector_name: str
    beam_diameter: float
    magnification: int
    acceleration_voltage: int
    stage_position: Dict[str, float]


def parse_custom_data(custom_data) -> Dict[str, Any]:
    result = {}
    for item in custom_data.findall('.//{*}KeyValueOfstringanyType'):
        key = item.find('.//{*}Key').text
        value_elem = item.find('.//{*}Value')
        if value_elem is not None:
            if 'type' in value_elem.attrib:
                value_type = value_elem.attrib['type'].split(':')[-1]
                if value_type == 'double':
                    result[key] = float(value_elem.text)
                elif value_type == 'boolean':
                    result[key] = value_elem.text.lower() == 'true'
                else:
                    result[key] = value_elem.text
    return result


def parse_microscope_xml(xml_path: str) -> MicroscopeImageData:
    try:
        tree = ET.parse(xml_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"XML file not found at: {xml_path}")

    root = tree.getroot()

    # Parse custom data section
    custom_data = parse_custom_data(root.find('.//{*}CustomData'))

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
        raise ValueError("Could not find microscopeData in XML")

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

    return MicroscopeImageData(
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


def main():
    xml_path = 'tests/testdata/epumocks/EPU_session/Metadata/GridSquare_20240406_102420.xml'
    # xml_path = os.path.join('tests', 'testdata', 'epumocks', 'EPU_session', 'Metadata',
    #                         'GridSquare_20240406_102420.xml')
    data = parse_microscope_xml(xml_path)
    print(f"Acquisition time: {data.acquisition_datetime}")
    print(f"Detector: {data.detector_name}")
    print(f"Dose rate: {data.dose_rate:.2f}")
    print(f"Magnification: {data.magnification}x")
    print(f"Stage position: {data.stage_position}")


if __name__ == '__main__':
    main()