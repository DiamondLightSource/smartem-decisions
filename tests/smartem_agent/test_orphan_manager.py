import time
from datetime import datetime
from pathlib import Path

import pytest

from smartem_agent.event_classifier import EntityType
from smartem_agent.orphan_manager import OrphanManager
from smartem_common.schemas import FoilHoleData, GridSquareData, MicrographData, MicrographManifest


class TestOrphanManager:
    @pytest.fixture
    def orphan_manager(self):
        return OrphanManager(timeout_seconds=5.0)

    @pytest.fixture
    def sample_gridsquare_data(self):
        return GridSquareData(gridsquare_id="42", grid_uuid="test-grid-uuid")

    @pytest.fixture
    def sample_foilhole_data(self):
        return FoilHoleData(id="123", gridsquare_id="42")

    @pytest.fixture
    def sample_micrograph_manifest(self):
        return MicrographManifest(
            unique_id="unique-id-456",
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

    @pytest.fixture
    def sample_micrograph_data(self, sample_micrograph_manifest):
        return MicrographData(
            id="unique-id-456",
            gridsquare_id="42",
            foilhole_id="123",
            foilhole_uuid="test-foilhole-uuid",
            location_id="1",
            high_res_path=Path("/test"),
            manifest_file=Path("/test/manifest.xml"),
            manifest=sample_micrograph_manifest,
        )

    def test_register_foilhole_orphan(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["by_type"]["foilhole"] == 1

    def test_register_micrograph_orphan(self, orphan_manager, sample_micrograph_data):
        orphan_manager.register_orphan(
            entity_data=sample_micrograph_data,
            entity_type=EntityType.MICROGRAPH,
            required_parent_natural_id="123",
            file_path=Path("/test/Micrograph_456.xml"),
        )

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["by_type"]["micrograph"] == 1

    def test_register_gridsquare_orphan(self, orphan_manager, sample_gridsquare_data):
        orphan_manager.register_orphan(
            entity_data=sample_gridsquare_data,
            entity_type=EntityType.GRIDSQUARE,
            required_parent_natural_id="grid-1",
            file_path=Path("/test/GridSquare_42.dm"),
        )

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["by_type"]["gridsquare"] == 1

    def test_resolve_orphans_empty(self, orphan_manager):
        orphans = orphan_manager.resolve_orphans_for(EntityType.GRIDSQUARE, "42")
        assert len(orphans) == 0

    def test_resolve_orphans_single(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        orphans = orphan_manager.resolve_orphans_for(EntityType.GRIDSQUARE, "42")

        assert len(orphans) == 1
        assert orphans[0].entity_type == EntityType.FOILHOLE
        assert orphans[0].required_parent_natural_id == "42"

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 0
        assert stats["total_resolved"] == 1

    def test_resolve_orphans_multiple_same_parent(self, orphan_manager):
        for i in range(3):
            foilhole_data = FoilHoleData(id=str(100 + i), gridsquare_id="42")
            orphan_manager.register_orphan(
                entity_data=foilhole_data,
                entity_type=EntityType.FOILHOLE,
                required_parent_natural_id="42",
                file_path=Path(f"/test/FoilHole_{100 + i}.xml"),
            )

        orphans = orphan_manager.resolve_orphans_for(EntityType.GRIDSQUARE, "42")

        assert len(orphans) == 3
        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 0
        assert stats["total_resolved"] == 3

    def test_resolve_orphans_wrong_parent(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        orphans = orphan_manager.resolve_orphans_for(EntityType.GRIDSQUARE, "99")

        assert len(orphans) == 0
        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1

    def test_timeout_detection_no_timeouts(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        timed_out = orphan_manager.check_timeouts(max_age_seconds=10.0)

        assert len(timed_out) == 0
        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["total_timed_out"] == 0

    def test_timeout_detection_with_timeouts(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        time.sleep(0.1)

        timed_out = orphan_manager.check_timeouts(max_age_seconds=0.05)

        assert len(timed_out) == 1
        assert timed_out[0].entity_type == EntityType.FOILHOLE

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 1
        assert stats["total_timed_out"] == 1

    def test_timeout_detection_mixed_ages(self, orphan_manager):
        old_foilhole = FoilHoleData(id="123", gridsquare_id="42")
        orphan_manager.register_orphan(
            entity_data=old_foilhole,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        time.sleep(0.1)

        new_foilhole = FoilHoleData(id="456", gridsquare_id="42")
        orphan_manager.register_orphan(
            entity_data=new_foilhole,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_456.xml"),
        )

        timed_out = orphan_manager.check_timeouts(max_age_seconds=0.05)

        assert len(timed_out) == 1
        assert timed_out[0].entity_data.id == "123"

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 2
        assert stats["total_timed_out"] == 1

    def test_clear_orphans(self, orphan_manager, sample_foilhole_data):
        orphan_manager.register_orphan(
            entity_data=sample_foilhole_data,
            entity_type=EntityType.FOILHOLE,
            required_parent_natural_id="42",
            file_path=Path("/test/FoilHole_123.xml"),
        )

        orphan_manager.clear()

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 0
        assert stats["total_resolved"] == 0
        assert stats["total_timed_out"] == 0

    def test_multiple_orphan_types(self, orphan_manager, sample_micrograph_manifest):
        gridsquare_data = GridSquareData(gridsquare_id="10", grid_uuid="test-grid-uuid")
        foilhole_data = FoilHoleData(id="20", gridsquare_id="10")
        micrograph_data = MicrographData(
            id="unique-30",
            gridsquare_id="10",
            foilhole_id="20",
            foilhole_uuid="test-fh-uuid",
            location_id="1",
            high_res_path=Path("/test"),
            manifest_file=Path("/test/manifest.xml"),
            manifest=sample_micrograph_manifest,
        )

        orphan_manager.register_orphan(gridsquare_data, EntityType.GRIDSQUARE, "grid-1", Path("/test/gs.dm"))
        orphan_manager.register_orphan(foilhole_data, EntityType.FOILHOLE, "10", Path("/test/fh.xml"))
        orphan_manager.register_orphan(micrograph_data, EntityType.MICROGRAPH, "20", Path("/test/micro.xml"))

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 3
        assert stats["by_type"]["gridsquare"] == 1
        assert stats["by_type"]["foilhole"] == 1
        assert stats["by_type"]["micrograph"] == 1

    def test_parent_type_mapping(self, orphan_manager):
        assert orphan_manager.PARENT_TYPE_MAP[EntityType.GRIDSQUARE] == EntityType.GRID
        assert orphan_manager.PARENT_TYPE_MAP[EntityType.FOILHOLE] == EntityType.GRIDSQUARE
        assert orphan_manager.PARENT_TYPE_MAP[EntityType.MICROGRAPH] == EntityType.FOILHOLE

    def test_register_orphan_unknown_type(self, orphan_manager):
        orphan_manager.register_orphan(
            entity_data={},
            entity_type=EntityType.UNKNOWN,
            required_parent_natural_id="test",
            file_path=Path("/test/unknown.txt"),
        )

        stats = orphan_manager.get_orphan_stats()
        assert stats["total_orphans"] == 0
