import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from smartem_agent.fs_parser import EpuParser
from smartem_agent.model.store import InMemoryDataStore
from smartem_agent2.event_classifier import ClassifiedEvent, EntityType
from smartem_agent2.event_processor import EventProcessor, ProcessingResult
from smartem_agent2.orphan_manager import OrphanManager
from smartem_common.schemas import (
    AcquisitionData,
    AtlasData,
    FoilHoleData,
    GridData,
    GridSquareData,
    GridSquareMetadata,
    GridSquarePosition,
    MicrographManifest,
)


class TestEventProcessor:
    @pytest.fixture
    def temp_dir(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def datastore(self, temp_dir):
        return InMemoryDataStore(str(temp_dir))

    @pytest.fixture
    def orphan_manager(self):
        return OrphanManager(timeout_seconds=300.0)

    @pytest.fixture
    def parser(self):
        return EpuParser()

    @pytest.fixture
    def processor(self, parser, datastore, orphan_manager):
        return EventProcessor(parser, datastore, orphan_manager)

    @pytest.fixture
    def sample_micrograph_manifest(self):
        return MicrographManifest(
            unique_id="test-unique-id",
            acquisition_datetime=datetime.now(),
            defocus=1.0,
            detector_name="Test Detector",
            energy_filter=False,
            phase_plate=False,
            image_size_x=4096,
            image_size_y=4096,
            binning_x=1,
            binning_y=1,
        )

    def test_process_batch_empty(self, processor):
        stats = processor.process_batch([])
        assert stats.total_processed == 0
        assert stats.successful == 0
        assert stats.orphaned == 0
        assert stats.failed == 0

    def test_process_grid_event_mocked(self, processor, temp_dir):
        grid_path = temp_dir / "EpuSession.dm"
        grid_path.touch()

        processor.parser.parse_epu_session_manifest = Mock(
            return_value=AcquisitionData(name="Test Acquisition", id="test-id")
        )

        event = ClassifiedEvent(
            entity_type=EntityType.GRID,
            file_path=grid_path,
            natural_id=None,
            priority=0,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.SUCCESS
        assert len(processor.datastore.grids) == 1

    def test_process_atlas_event_with_parent_grid(self, processor, temp_dir):
        grid_path = temp_dir / "EpuSession.dm"
        grid_path.touch()

        grid = GridData(data_dir=grid_path.parent)
        grid.acquisition_data = AcquisitionData(name="Test", id="test-id")
        processor.datastore.create_grid(grid)

        atlas_path = temp_dir / "Sample1" / "Atlas" / "Atlas.dm"
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        atlas_path.touch()

        processor.parser.parse_atlas_manifest = Mock(
            return_value=AtlasData(
                id="atlas-1",
                acquisition_date=datetime.now(),
                storage_folder="test",
                name="Test Atlas",
                tiles=[],
                gridsquare_positions={
                    1: GridSquarePosition(center=(100, 200), physical=None, size=(50, 50), rotation=0.0)
                },
                grid_uuid=grid.uuid,
            )
        )

        event = ClassifiedEvent(
            entity_type=EntityType.ATLAS,
            file_path=atlas_path,
            natural_id=None,
            priority=1,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.SUCCESS
        assert len(processor.datastore.atlases) == 1

    def test_process_atlas_without_parent_grid(self, processor, temp_dir):
        atlas_path = temp_dir / "orphan_atlas" / "Atlas" / "Atlas.dm"
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        atlas_path.touch()

        event = ClassifiedEvent(
            entity_type=EntityType.ATLAS,
            file_path=atlas_path,
            natural_id=None,
            priority=1,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.ORPHANED

    def test_process_gridsquare_metadata_new(self, processor, temp_dir):
        grid = GridData(data_dir=temp_dir)
        grid.acquisition_data = AcquisitionData(name="Test", id="test-id")
        processor.datastore.create_grid(grid)

        gs_path = temp_dir / "Metadata" / "GridSquare_42.dm"
        gs_path.parent.mkdir(parents=True, exist_ok=True)
        gs_path.touch()

        processor.parser.parse_gridsquare_metadata = Mock(
            return_value=GridSquareMetadata(
                atlas_node_id=42,
                stage_position=None,
                state="Ready",
                rotation=0.0,
                image_path=None,
                selected=True,
                unusable=False,
                foilhole_positions={},
            )
        )

        event = ClassifiedEvent(
            entity_type=EntityType.GRIDSQUARE,
            file_path=gs_path,
            natural_id="42",
            priority=2,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.SUCCESS
        assert len(processor.datastore.gridsquares) == 1

        gs = processor.datastore.find_gridsquare_by_natural_id("42")
        assert gs is not None
        assert gs.gridsquare_id == "42"

    def test_process_foilhole_with_parent(self, processor, temp_dir):
        grid = GridData(data_dir=temp_dir)
        grid.acquisition_data = AcquisitionData(name="Test", id="test-id")
        processor.datastore.create_grid(grid)

        gridsquare = GridSquareData(gridsquare_id="42", grid_uuid=grid.uuid)
        processor.datastore.create_gridsquare(gridsquare)

        fh_path = temp_dir / "Images-Disc1" / "GridSquare_42" / "FoilHoles" / "FoilHole_123_1_2.xml"
        fh_path.parent.mkdir(parents=True, exist_ok=True)
        fh_path.touch()

        processor.parser.parse_foilhole_manifest = Mock(
            return_value=FoilHoleData(id="123", gridsquare_id="42", gridsquare_uuid=None)
        )

        event = ClassifiedEvent(
            entity_type=EntityType.FOILHOLE,
            file_path=fh_path,
            natural_id="123",
            priority=3,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.SUCCESS
        assert len(processor.datastore.foilholes) == 1

        fh = processor.datastore.find_foilhole_by_natural_id("123")
        assert fh is not None
        assert fh.gridsquare_uuid == gridsquare.uuid

    def test_process_foilhole_without_parent_orphaned(self, processor, temp_dir):
        fh_path = temp_dir / "Images-Disc1" / "GridSquare_99" / "FoilHoles" / "FoilHole_456_1_2.xml"
        fh_path.parent.mkdir(parents=True, exist_ok=True)
        fh_path.touch()

        processor.parser.parse_foilhole_manifest = Mock(
            return_value=FoilHoleData(id="456", gridsquare_id="99", gridsquare_uuid=None)
        )

        event = ClassifiedEvent(
            entity_type=EntityType.FOILHOLE,
            file_path=fh_path,
            natural_id="456",
            priority=3,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.ORPHANED

        stats = processor.orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["by_type"]["foilhole"] == 1

    def test_process_micrograph_with_parent(self, processor, temp_dir, sample_micrograph_manifest):
        grid = GridData(data_dir=temp_dir)
        grid.acquisition_data = AcquisitionData(name="Test", id="test-id")
        processor.datastore.create_grid(grid)

        gridsquare = GridSquareData(gridsquare_id="10", grid_uuid=grid.uuid)
        processor.datastore.create_gridsquare(gridsquare)

        foilhole = FoilHoleData(id="20", gridsquare_id="10", gridsquare_uuid=gridsquare.uuid)
        processor.datastore.create_foilhole(foilhole)

        micro_path = temp_dir / "Images-Disc1" / "GridSquare_10" / "Data" / "FoilHole_20_Data_1_2_3_4.xml"
        micro_path.parent.mkdir(parents=True, exist_ok=True)
        micro_path.touch()

        processor.parser.parse_micrograph_manifest = Mock(return_value=sample_micrograph_manifest)

        event = ClassifiedEvent(
            entity_type=EntityType.MICROGRAPH,
            file_path=micro_path,
            natural_id="20",
            priority=4,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.SUCCESS
        assert len(processor.datastore.micrographs) == 1

    def test_process_micrograph_without_parent_orphaned(self, processor, temp_dir, sample_micrograph_manifest):
        micro_path = temp_dir / "Images-Disc1" / "GridSquare_99" / "Data" / "FoilHole_888_Data_1_2_3_4.xml"
        micro_path.parent.mkdir(parents=True, exist_ok=True)
        micro_path.touch()

        processor.parser.parse_micrograph_manifest = Mock(return_value=sample_micrograph_manifest)

        event = ClassifiedEvent(
            entity_type=EntityType.MICROGRAPH,
            file_path=micro_path,
            natural_id="888",
            priority=4,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.ORPHANED

    def test_orphan_resolution_cascade(self, processor, temp_dir):
        grid = GridData(data_dir=temp_dir)
        grid.acquisition_data = AcquisitionData(name="Test", id="test-id")
        processor.datastore.create_grid(grid)

        fh_path = temp_dir / "Images-Disc1" / "GridSquare_50" / "FoilHoles" / "FoilHole_100_1_2.xml"
        fh_path.parent.mkdir(parents=True, exist_ok=True)
        fh_path.touch()

        processor.parser.parse_foilhole_manifest = Mock(
            return_value=FoilHoleData(id="100", gridsquare_id="50", gridsquare_uuid=None)
        )

        fh_event = ClassifiedEvent(
            entity_type=EntityType.FOILHOLE,
            file_path=fh_path,
            natural_id="100",
            priority=3,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(fh_event)
        assert result == ProcessingResult.ORPHANED
        assert len(processor.datastore.foilholes) == 0

        gs_path = temp_dir / "Metadata" / "GridSquare_50.dm"
        gs_path.parent.mkdir(parents=True, exist_ok=True)
        gs_path.touch()

        processor.parser.parse_gridsquare_metadata = Mock(
            return_value=GridSquareMetadata(
                atlas_node_id=50,
                stage_position=None,
                state="Ready",
                rotation=0.0,
                image_path=None,
                selected=True,
                unusable=False,
                foilhole_positions={},
            )
        )

        gs_event = ClassifiedEvent(
            entity_type=EntityType.GRIDSQUARE,
            file_path=gs_path,
            natural_id="50",
            priority=2,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(gs_event)
        assert result == ProcessingResult.SUCCESS

        assert len(processor.datastore.gridsquares) == 1
        assert len(processor.datastore.foilholes) == 1
        assert processor.stats.orphans_resolved == 1

    def test_process_batch_statistics(self, processor, temp_dir):
        grid_path = temp_dir / "EpuSession.dm"
        grid_path.touch()

        processor.parser.parse_epu_session_manifest = Mock(return_value=AcquisitionData(name="Test", id="test-id"))

        events = [
            ClassifiedEvent(EntityType.GRID, grid_path, None, 0, time.time(), "created"),
            ClassifiedEvent(EntityType.UNKNOWN, Path("/test/unknown.txt"), None, 999, time.time(), "created"),
        ]

        stats = processor.process_batch(events)

        assert stats.total_processed == 2
        assert stats.successful == 1
        assert stats.failed == 1

    def test_get_stats(self, processor):
        stats = processor.get_stats()
        assert stats.total_processed == 0
        assert stats.successful == 0

    def test_reset_stats(self, processor):
        processor.stats.total_processed = 10
        processor.stats.successful = 5

        processor.reset_stats()

        stats = processor.get_stats()
        assert stats.total_processed == 0
        assert stats.successful == 0

    def test_process_unknown_entity_type(self, processor):
        event = ClassifiedEvent(
            entity_type=EntityType.UNKNOWN,
            file_path=Path("/test/unknown.txt"),
            natural_id=None,
            priority=999,
            timestamp=time.time(),
            event_type="created",
        )

        result = processor._process_event(event)
        assert result == ProcessingResult.FAILED

    def test_exception_handling_in_batch(self, processor, temp_dir):
        grid_path = temp_dir / "EpuSession.dm"
        grid_path.touch()

        processor.parser.parse_epu_session_manifest = Mock(side_effect=Exception("Test exception"))

        event = ClassifiedEvent(EntityType.GRID, grid_path, None, 0, time.time(), "created")

        stats = processor.process_batch([event])

        assert stats.total_processed == 1
        assert stats.failed == 1
        assert stats.successful == 0
