from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from smartem_agent.fs_parser import EpuParser


class EntityType(Enum):
    GRID = "grid"
    ATLAS = "atlas"
    GRIDSQUARE = "gridsquare"
    FOILHOLE = "foilhole"
    MICROGRAPH = "micrograph"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedEvent:
    entity_type: EntityType
    file_path: Path
    natural_id: str | None
    priority: int
    timestamp: float
    event_type: str

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class EventClassifier:
    PRIORITY_MAP = {
        EntityType.GRID: 0,
        EntityType.ATLAS: 1,
        EntityType.GRIDSQUARE: 2,
        EntityType.FOILHOLE: 3,
        EntityType.MICROGRAPH: 4,
        EntityType.UNKNOWN: 999,
    }

    def __init__(self):
        self.session_dm_pattern = EpuParser.session_dm_pattern
        self.atlas_dm_pattern = EpuParser.atlas_dm_pattern
        self.gridsquare_dm_file_pattern = EpuParser.gridsquare_dm_file_pattern
        self.gridsquare_xml_file_pattern = EpuParser.gridsquare_xml_file_pattern
        self.foilhole_xml_file_pattern = EpuParser.foilhole_xml_file_pattern
        self.micrograph_xml_file_pattern = EpuParser.micrograph_xml_file_pattern
        self.gridsquare_dir_pattern = EpuParser.gridsquare_dir_pattern

    def classify(self, file_path: str | Path, event_type: str, timestamp: float) -> ClassifiedEvent:
        file_path = Path(file_path) if isinstance(file_path, str) else file_path
        path_str = str(file_path)

        entity_type, natural_id = self._determine_entity_type_and_id(path_str)
        priority = self.PRIORITY_MAP[entity_type]

        return ClassifiedEvent(
            entity_type=entity_type,
            file_path=file_path,
            natural_id=natural_id,
            priority=priority,
            timestamp=timestamp,
            event_type=event_type,
        )

    def _determine_entity_type_and_id(self, path: str) -> tuple[EntityType, str | None]:
        if self.session_dm_pattern.search(path):
            return EntityType.GRID, None

        if self.atlas_dm_pattern.search(path):
            return EntityType.ATLAS, None

        if match := self.gridsquare_dm_file_pattern.search(path):
            gridsquare_id = match.group(1)
            return EntityType.GRIDSQUARE, gridsquare_id

        if match := self.gridsquare_xml_file_pattern.search(path):
            return EntityType.GRIDSQUARE, None

        if match := self.foilhole_xml_file_pattern.search(path):
            foilhole_id = match.group(1)
            return EntityType.FOILHOLE, foilhole_id

        if match := self.micrograph_xml_file_pattern.search(path):
            foilhole_id = match.group(1)
            return EntityType.MICROGRAPH, foilhole_id

        return EntityType.UNKNOWN, None

    def extract_parent_natural_id(self, file_path: str | Path, entity_type: EntityType) -> str | None:
        path_str = str(file_path)

        match entity_type:
            case EntityType.GRIDSQUARE:
                return None
            case EntityType.FOILHOLE:
                if match := self.gridsquare_dir_pattern.search(path_str):
                    return match.group(1)
                return None
            case EntityType.MICROGRAPH:
                if match := self.gridsquare_dir_pattern.search(path_str):
                    return match.group(1)
                return None
            case _:
                return None
