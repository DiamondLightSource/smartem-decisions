import json
from datetime import datetime
from pathlib import Path

from smartem_backend.model.http_request import (
    AcquisitionBaseFields,
    AtlasBaseFields,
    GridBaseFields,
    GridSquareBaseFields,
    MicrographBaseFields,
)
from smartem_backend.model.http_response import (
    AcquisitionResponse,
    AtlasResponse,
    AtlasTileResponse,
    GridResponse,
    GridSquareResponse,
    MicrographResponse,
    QualityPredictionModelParameterResponse,
    QualityPredictionModelWeightResponse,
    QualityPredictionResponse,
)
from smartem_common.entity_status import (
    AcquisitionStatus,
    GridSquareStatus,
    GridStatus,
    MicrographStatus,
)
from smartem_common.schemas import (
    AcquisitionData,
    AtlasData,
    AtlasTileData,
    AtlasTilePosition,
    GridSquareManifest,
    MicrographManifest,
)

TEST_DATETIME = datetime(2024, 6, 15, 14, 30, 45)
TEST_DATETIME_ISO = "2024-06-15T14:30:45"


class TestSchemasDatetimeSerialization:
    def test_micrograph_manifest_serialization(self):
        manifest = MicrographManifest(
            unique_id="test-id",
            acquisition_datetime=TEST_DATETIME,
            defocus=1.5,
            detector_name="Falcon",
            energy_filter=True,
            phase_plate=False,
            image_size_x=4096,
            image_size_y=4096,
            binning_x=1,
            binning_y=1,
        )
        json_str = manifest.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO

    def test_gridsquare_manifest_serialization(self):
        manifest = GridSquareManifest(
            acquisition_datetime=TEST_DATETIME,
            defocus=2.0,
            magnification=100000.0,
            pixel_size=1.0,
            detector_name="Falcon",
            applied_defocus=1.5,
            data_dir=Path("/tmp/test"),
        )
        json_str = manifest.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO
        assert data["data_dir"] == "/tmp/test"

    def test_atlas_data_serialization(self):
        atlas = AtlasData(
            id="atlas-1",
            acquisition_date=TEST_DATETIME,
            storage_folder="/storage/atlas",
            name="Test Atlas",
            tiles=[
                AtlasTileData(
                    id="tile-1",
                    tile_position=AtlasTilePosition(position=(0, 0), size=(100, 100)),
                    file_format="mrc",
                    base_filename="tile",
                    atlas_uuid="atlas-uuid",
                )
            ],
            gridsquare_positions=None,
            grid_uuid="grid-uuid",
        )
        json_str = atlas.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_date"] == TEST_DATETIME_ISO

    def test_acquisition_data_serialization(self):
        acq = AcquisitionData(
            id="acq-1",
            name="Test Acquisition",
            start_time=TEST_DATETIME,
        )
        json_str = acq.model_dump_json()
        data = json.loads(json_str)
        assert data["start_time"] == TEST_DATETIME_ISO

    def test_acquisition_data_none_datetime(self):
        acq = AcquisitionData(
            id="acq-1",
            name="Test Acquisition",
            start_time=None,
        )
        json_str = acq.model_dump_json()
        data = json.loads(json_str)
        assert data["start_time"] is None


class TestHttpRequestDatetimeSerialization:
    def test_acquisition_base_fields_serialization(self):
        fields = AcquisitionBaseFields(
            uuid="uuid-1",
            name="Test",
            status=AcquisitionStatus.STARTED,
            start_time=TEST_DATETIME,
            end_time=None,
            paused_time=None,
        )
        json_str = fields.model_dump_json()
        data = json.loads(json_str)
        assert data["start_time"] == TEST_DATETIME_ISO
        assert data["end_time"] is None

    def test_atlas_base_fields_serialization(self):
        fields = AtlasBaseFields(
            uuid="uuid-1",
            atlas_id="atlas-1",
            acquisition_date=TEST_DATETIME,
        )
        json_str = fields.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_date"] == TEST_DATETIME_ISO

    def test_grid_base_fields_serialization(self):
        fields = GridBaseFields(
            uuid="uuid-1",
            name="Grid 1",
            status=GridStatus.SCAN_STARTED,
            scan_start_time=TEST_DATETIME,
            scan_end_time=None,
        )
        json_str = fields.model_dump_json()
        data = json.loads(json_str)
        assert data["scan_start_time"] == TEST_DATETIME_ISO
        assert data["scan_end_time"] is None

    def test_gridsquare_base_fields_serialization(self):
        fields = GridSquareBaseFields(
            uuid="uuid-1",
            gridsquare_id="gs-1",
            status=GridSquareStatus.REGISTERED,
            acquisition_datetime=TEST_DATETIME,
        )
        json_str = fields.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO

    def test_micrograph_base_fields_serialization(self):
        fields = MicrographBaseFields(
            uuid="uuid-1",
            foilhole_id="fh-1",
            status=MicrographStatus.CTF_COMPLETED,
            acquisition_datetime=TEST_DATETIME,
        )
        json_str = fields.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO


class TestHttpResponseDatetimeSerialization:
    def test_atlas_response_serialization(self):
        response = AtlasResponse(
            uuid="uuid-1",
            grid_uuid="grid-uuid",
            atlas_id="atlas-1",
            acquisition_date=TEST_DATETIME,
            storage_folder="/storage",
            description="Test",
            name="Atlas",
            tiles=[
                AtlasTileResponse(
                    uuid="tile-uuid",
                    atlas_uuid="atlas-uuid",
                    tile_id="tile-1",
                    position_x=0,
                    position_y=0,
                    size_x=100,
                    size_y=100,
                    file_format="mrc",
                    base_filename="tile",
                )
            ],
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_date"] == TEST_DATETIME_ISO

    def test_acquisition_response_serialization(self):
        response = AcquisitionResponse(
            uuid="uuid-1",
            name="Acquisition",
            status=AcquisitionStatus.COMPLETED,
            start_time=TEST_DATETIME,
            end_time=TEST_DATETIME,
            paused_time=None,
            storage_path="/storage",
            atlas_path="/atlas",
            clustering_mode="mode",
            clustering_radius="10",
            instrument_model="Krios",
            instrument_id="inst-1",
            computer_name="pc-1",
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["start_time"] == TEST_DATETIME_ISO
        assert data["end_time"] == TEST_DATETIME_ISO
        assert data["paused_time"] is None

    def test_grid_response_serialization(self):
        response = GridResponse(
            uuid="uuid-1",
            acquisition_uuid="acq-uuid",
            status=GridStatus.SCAN_COMPLETED,
            name="Grid",
            data_dir="/data",
            atlas_dir="/atlas",
            scan_start_time=TEST_DATETIME,
            scan_end_time=TEST_DATETIME,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["scan_start_time"] == TEST_DATETIME_ISO
        assert data["scan_end_time"] == TEST_DATETIME_ISO

    def test_gridsquare_response_serialization(self):
        response = GridSquareResponse(
            uuid="uuid-1",
            gridsquare_id="gs-1",
            grid_uuid="grid-uuid",
            status=GridSquareStatus.REGISTERED,
            data_dir="/data",
            atlas_node_id=1,
            state="completed",
            rotation=0.0,
            image_path="/image.mrc",
            selected=True,
            unusable=False,
            stage_position_x=0.0,
            stage_position_y=0.0,
            stage_position_z=0.0,
            center_x=100,
            center_y=100,
            physical_x=0.0,
            physical_y=0.0,
            size_width=200,
            size_height=200,
            acquisition_datetime=TEST_DATETIME,
            defocus=1.5,
            magnification=100000.0,
            pixel_size=1.0,
            detector_name="Falcon",
            applied_defocus=1.5,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO

    def test_micrograph_response_serialization(self):
        response = MicrographResponse(
            uuid="uuid-1",
            foilhole_uuid="fh-uuid",
            foilhole_id="fh-1",
            status=MicrographStatus.CTF_COMPLETED,
            acquisition_datetime=TEST_DATETIME,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["acquisition_datetime"] == TEST_DATETIME_ISO

    def test_quality_prediction_response_serialization(self):
        response = QualityPredictionResponse(
            id=1,
            prediction_model_name="model-1",
            value=0.95,
            timestamp=TEST_DATETIME,
            gridsquare_uuid="gs-uuid",
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["timestamp"] == TEST_DATETIME_ISO

    def test_quality_prediction_model_parameter_response_serialization(self):
        response = QualityPredictionModelParameterResponse(
            id=1,
            grid_uuid="grid-uuid",
            timestamp=TEST_DATETIME,
            prediction_model_name="model-1",
            key="threshold",
            value=0.5,
            group="default",
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["timestamp"] == TEST_DATETIME_ISO

    def test_quality_prediction_model_weight_response_serialization(self):
        response = QualityPredictionModelWeightResponse(
            id=1,
            grid_uuid="grid-uuid",
            micrograph_uuid="micro-uuid",
            micrograph_quality=True,
            timestamp=TEST_DATETIME,
            origin="manual",
            prediction_model_name="model-1",
            weight=1.0,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["timestamp"] == TEST_DATETIME_ISO


class TestDatetimeRoundTrip:
    def test_acquisition_data_roundtrip(self):
        original = AcquisitionData(
            id="acq-1",
            name="Test",
            start_time=TEST_DATETIME,
        )
        json_str = original.model_dump_json()
        restored = AcquisitionData.model_validate_json(json_str)
        assert restored.start_time == TEST_DATETIME

    def test_acquisition_response_roundtrip(self):
        original = AcquisitionResponse(
            uuid="uuid-1",
            name="Test",
            status=AcquisitionStatus.COMPLETED,
            start_time=TEST_DATETIME,
            end_time=None,
            paused_time=None,
            storage_path=None,
            atlas_path=None,
            clustering_mode=None,
            clustering_radius=None,
            instrument_model=None,
            instrument_id=None,
            computer_name=None,
        )
        json_str = original.model_dump_json()
        restored = AcquisitionResponse.model_validate_json(json_str)
        assert restored.start_time == TEST_DATETIME
