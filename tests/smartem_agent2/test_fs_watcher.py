import time
from pathlib import Path
from unittest.mock import patch

import pytest
from watchdog.events import FileCreatedEvent

from smartem_agent2.fs_watcher import SmartEMWatcherV2


class TestSmartEMWatcherV2:
    @pytest.fixture
    def temp_dir(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def watcher(self, temp_dir):
        watcher = SmartEMWatcherV2(
            watch_dir=temp_dir,
            dry_run=True,
            log_interval=10.0,
            processing_interval=100.0,
            orphan_check_interval=100.0,
            orphan_timeout=0.5,
            max_queue_size=100,
            batch_size=10,
        )
        yield watcher
        watcher.stop()

    def test_initialization(self, temp_dir):
        watcher = SmartEMWatcherV2(
            watch_dir=temp_dir,
            dry_run=True,
            max_queue_size=500,
            batch_size=25,
            processing_interval=0.2,
        )

        assert watcher.watch_dir == temp_dir.absolute()
        assert watcher.event_queue.max_size == 500
        assert watcher.batch_size == 25
        assert watcher.processing_interval == 0.2

        watcher.stop()

    def test_matches_pattern_session_file(self, watcher, temp_dir):
        session_path = temp_dir / "EpuSession.dm"
        assert watcher.matches_pattern(str(session_path))

    def test_matches_pattern_gridsquare_metadata(self, watcher, temp_dir):
        gs_path = temp_dir / "Metadata" / "GridSquare_42.dm"
        assert watcher.matches_pattern(str(gs_path))

    def test_matches_pattern_foilhole(self, watcher, temp_dir):
        fh_path = temp_dir / "Images-Disc1" / "GridSquare_10" / "FoilHoles" / "FoilHole_123_1_2.xml"
        assert watcher.matches_pattern(str(fh_path))

    def test_matches_pattern_non_matching(self, watcher, temp_dir):
        random_path = temp_dir / "random_file.txt"
        assert not watcher.matches_pattern(str(random_path))

    def test_on_any_event_enqueues_matching_file(self, watcher, temp_dir):
        session_path = temp_dir / "EpuSession.dm"
        session_path.touch()

        event = FileCreatedEvent(str(session_path))

        initial_size = watcher.event_queue.size()
        watcher.on_any_event(event)

        assert watcher.event_queue.size() == initial_size + 1

    def test_on_any_event_skips_non_matching_file(self, watcher, temp_dir):
        random_path = temp_dir / "random.txt"
        random_path.touch()

        event = FileCreatedEvent(str(random_path))

        initial_size = watcher.event_queue.size()
        watcher.on_any_event(event)

        assert watcher.event_queue.size() == initial_size

    def test_on_any_event_skips_directory(self, watcher, temp_dir):
        dir_path = temp_dir / "some_directory"
        dir_path.mkdir()

        event = FileCreatedEvent(str(dir_path))
        event.is_directory = True

        initial_size = watcher.event_queue.size()
        watcher.on_any_event(event)

        assert watcher.event_queue.size() == initial_size

    def test_processing_loop_processes_events(self, temp_dir):
        watcher = SmartEMWatcherV2(
            watch_dir=temp_dir,
            dry_run=True,
            processing_interval=0.05,
        )

        try:
            session_path = temp_dir / "EpuSession.dm"
            session_path.touch()

            with patch.object(watcher.parser, "parse_epu_session_manifest") as mock_parse:
                from smartem_common.schemas import AcquisitionData

                mock_parse.return_value = AcquisitionData(name="Test", id="test-id")

                event = FileCreatedEvent(str(session_path))
                watcher.on_any_event(event)

                time.sleep(0.3)

                assert watcher.event_processor.stats.total_processed >= 1
                assert len(watcher.datastore.grids) == 1
        finally:
            watcher.stop()

    def test_orphan_detection_and_resolution(self, temp_dir):
        watcher = SmartEMWatcherV2(
            watch_dir=temp_dir, dry_run=True, processing_interval=0.05, orphan_check_interval=100.0
        )

        try:
            grid_path = temp_dir / "EpuSession.dm"
            grid_path.touch()

            fh_path = temp_dir / "Images-Disc1" / "GridSquare_42" / "FoilHoles" / "FoilHole_123_1_2.xml"
            fh_path.parent.mkdir(parents=True, exist_ok=True)
            fh_path.touch()

            with (
                patch.object(watcher.parser, "parse_epu_session_manifest") as mock_parse_session,
                patch.object(watcher.parser, "parse_foilhole_manifest") as mock_parse_fh,
            ):
                from smartem_common.schemas import AcquisitionData, FoilHoleData

                mock_parse_session.return_value = AcquisitionData(name="Test", id="test-id")
                mock_parse_fh.return_value = FoilHoleData(id="123", gridsquare_id="42")

                fh_event = FileCreatedEvent(str(fh_path))
                watcher.on_any_event(fh_event)

                time.sleep(0.2)

                assert watcher.orphan_manager.get_orphan_stats()["total_orphans"] == 1

                gs_path = temp_dir / "Metadata" / "GridSquare_42.dm"
                gs_path.parent.mkdir(parents=True, exist_ok=True)
                gs_path.touch()

                with patch.object(watcher.parser, "parse_gridsquare_metadata") as mock_parse_gs:
                    from smartem_common.schemas import GridSquareMetadata

                    mock_parse_gs.return_value = GridSquareMetadata(
                        atlas_node_id=42,
                        stage_position=None,
                        state="Ready",
                        rotation=0.0,
                        image_path=None,
                        selected=True,
                        unusable=False,
                        foilhole_positions={},
                    )

                    grid_event = FileCreatedEvent(str(grid_path))
                    watcher.on_any_event(grid_event)

                    gs_event = FileCreatedEvent(str(gs_path))
                    watcher.on_any_event(gs_event)

                    time.sleep(0.3)

                    assert len(watcher.datastore.gridsquares) == 1
                    assert len(watcher.datastore.foilholes) == 1
                    assert watcher.event_processor.stats.orphans_resolved >= 1
        finally:
            watcher.stop()

    def test_orphan_timeout_detection(self, temp_dir):
        watcher = SmartEMWatcherV2(watch_dir=temp_dir, dry_run=True, orphan_timeout=0.2, orphan_check_interval=0.1)

        try:
            from smartem_agent2.event_classifier import EntityType
            from smartem_common.schemas import FoilHoleData

            orphan_data = FoilHoleData(id="999", gridsquare_id="99")
            watcher.orphan_manager.register_orphan(
                entity_data=orphan_data,
                entity_type=EntityType.FOILHOLE,
                required_parent_natural_id="99",
                file_path=Path("/test/FoilHole_999.xml"),
            )

            time.sleep(0.5)

            stats = watcher.orphan_manager.get_orphan_stats()
            assert stats["total_timed_out"] >= 1
        finally:
            watcher.stop()

    def test_stop_graceful_shutdown(self, temp_dir):
        watcher = SmartEMWatcherV2(watch_dir=temp_dir, dry_run=True, processing_interval=0.1, orphan_check_interval=0.2)

        assert watcher._processing_thread.is_alive()
        assert watcher._orphan_check_thread.is_alive()

        watcher.stop()

        time.sleep(0.5)

        assert not watcher._processing_thread.is_alive()
        assert not watcher._orphan_check_thread.is_alive()

    def test_log_status(self, watcher, temp_dir):
        session_path = temp_dir / "EpuSession.dm"
        session_path.touch()

        with patch.object(watcher.parser, "parse_epu_session_manifest") as mock_parse:
            from smartem_common.schemas import AcquisitionData

            mock_parse.return_value = AcquisitionData(name="Test", id="test-id")

            event = FileCreatedEvent(str(session_path))
            watcher.on_any_event(event)

            time.sleep(0.2)

            watcher._log_status()

    def test_process_instruction_status_request(self, watcher):
        result = watcher._process_instruction("agent.status.request", {})

        assert "Agent watching" in result
        assert "queue:" in result
        assert "processed:" in result

    def test_process_instruction_config_update(self, watcher):
        old_interval = watcher.log_interval

        result = watcher._process_instruction("agent.config.update", {"log_interval": 20.0})

        assert watcher.log_interval == 20.0
        assert str(old_interval) in result
        assert "20.0" in result

    def test_process_instruction_datastore_info(self, watcher):
        result = watcher._process_instruction("agent.info.datastore", {})

        assert "Datastore contains" in result
        assert "grids" in result

    def test_process_instruction_unknown_type(self, watcher):
        result = watcher._process_instruction("unknown.instruction.type", {})

        assert "unknown instruction type" in result.lower()

    def test_event_queue_max_size_enforcement(self, temp_dir):
        watcher = SmartEMWatcherV2(
            watch_dir=temp_dir,
            dry_run=True,
            max_queue_size=5,
            processing_interval=100.0,
        )

        try:
            for _ in range(10):
                session_path = temp_dir / "EpuSession.dm"
                session_path.touch()
                event = FileCreatedEvent(str(session_path))
                watcher.on_any_event(event)

            assert watcher.event_queue.size() <= 5
            assert watcher.event_queue.get_evicted_count() > 0
        finally:
            watcher.stop()

    def test_custom_patterns(self, temp_dir):
        custom_patterns = ["*.txt", "data/*.csv"]

        watcher = SmartEMWatcherV2(watch_dir=temp_dir, dry_run=True, patterns=custom_patterns)

        txt_path = temp_dir / "test.txt"
        assert watcher.matches_pattern(str(txt_path))

        csv_path = temp_dir / "data" / "test.csv"
        assert watcher.matches_pattern(str(csv_path))

        dm_path = temp_dir / "EpuSession.dm"
        assert not watcher.matches_pattern(str(dm_path))

        watcher.stop()
