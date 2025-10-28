import time
from pathlib import Path

import pytest

from smartem_agent.event_classifier import ClassifiedEvent, EntityType, EventClassifier


class TestEventClassifier:
    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_classify_session_file(self, classifier):
        path = Path("/path/to/data/EpuSession.dm")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.GRID
        assert event.natural_id is None
        assert event.priority == 0

    def test_classify_atlas_file(self, classifier):
        path = Path("/path/to/data/Sample1/Atlas/Atlas.dm")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.ATLAS
        assert event.natural_id is None
        assert event.priority == 1

    def test_classify_gridsquare_dm_file(self, classifier):
        path = Path("/path/to/data/Metadata/GridSquare_42.dm")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.GRIDSQUARE
        assert event.natural_id == "42"
        assert event.priority == 2

    def test_classify_gridsquare_xml_file(self, classifier):
        path = Path("/path/to/data/Images-Disc1/GridSquare_10/GridSquare_10_1.xml")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.GRIDSQUARE
        assert event.natural_id is None
        assert event.priority == 2

    def test_classify_foilhole_file(self, classifier):
        path = Path("/path/to/data/Images-Disc1/GridSquare_5/FoilHoles/FoilHole_123_1_2.xml")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.FOILHOLE
        assert event.natural_id == "123"
        assert event.priority == 3

    def test_classify_micrograph_file(self, classifier):
        path = Path("/path/to/data/Images-Disc1/GridSquare_7/Data/FoilHole_456_Data_1_2_3_4.xml")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.MICROGRAPH
        assert event.natural_id == "456"
        assert event.priority == 4

    def test_classify_unknown_file(self, classifier):
        path = Path("/path/to/data/unknown_file.txt")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.UNKNOWN
        assert event.natural_id is None
        assert event.priority == 999

    def test_extract_parent_natural_id_foilhole(self, classifier):
        path = Path("/path/to/Images-Disc1/GridSquare_42/FoilHoles/FoilHole_123_1_2.xml")
        parent_id = classifier.extract_parent_natural_id(path, EntityType.FOILHOLE)

        assert parent_id == "42"

    def test_extract_parent_natural_id_micrograph(self, classifier):
        path = Path("/path/to/Images-Disc1/GridSquare_99/Data/FoilHole_456_Data_1_2_3_4.xml")
        parent_id = classifier.extract_parent_natural_id(path, EntityType.MICROGRAPH)

        assert parent_id == "99"

    def test_extract_parent_natural_id_no_parent(self, classifier):
        path = Path("/path/to/data/Metadata/GridSquare_10.dm")
        parent_id = classifier.extract_parent_natural_id(path, EntityType.GRIDSQUARE)

        assert parent_id is None

    def test_classified_event_ordering_by_priority(self):
        timestamp = time.time()
        grid_event = ClassifiedEvent(EntityType.GRID, Path("grid"), None, 0, timestamp, "created")
        micrograph_event = ClassifiedEvent(EntityType.MICROGRAPH, Path("micro"), "1", 4, timestamp, "created")

        assert grid_event < micrograph_event
        assert not (micrograph_event < grid_event)

    def test_classified_event_ordering_by_timestamp(self):
        early = time.time()
        late = early + 1.0

        event1 = ClassifiedEvent(EntityType.GRID, Path("grid1"), None, 0, early, "created")
        event2 = ClassifiedEvent(EntityType.GRID, Path("grid2"), None, 0, late, "created")

        assert event1 < event2
        assert not (event2 < event1)

    def test_classifier_handles_string_paths(self, classifier):
        path = "/path/to/data/EpuSession.dm"
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.GRID
        assert isinstance(event.file_path, Path)

    def test_classifier_handles_path_objects(self, classifier):
        path = Path("/path/to/data/EpuSession.dm")
        event = classifier.classify(path, "created", time.time())

        assert event.entity_type == EntityType.GRID
        assert isinstance(event.file_path, Path)

    def test_event_type_stored_correctly(self, classifier):
        path = Path("/path/to/data/EpuSession.dm")
        event = classifier.classify(path, "modified", time.time())

        assert event.event_type == "modified"
