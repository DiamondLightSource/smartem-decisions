import time
from dataclasses import dataclass
from pathlib import Path

from smartem_agent2.event_classifier import EntityType
from smartem_common.utils import get_logger

logger = get_logger(__name__)


@dataclass
class OrphanedEntity:
    entity_type: EntityType
    entity_data: object
    required_parent_type: EntityType
    required_parent_natural_id: str
    file_path: Path
    first_seen: float


class OrphanManager:
    PARENT_TYPE_MAP = {
        EntityType.ATLAS: EntityType.GRID,
        EntityType.GRIDSQUARE: EntityType.GRID,
        EntityType.FOILHOLE: EntityType.GRIDSQUARE,
        EntityType.MICROGRAPH: EntityType.FOILHOLE,
    }

    def __init__(self, timeout_seconds: float = 300.0):
        self.timeout_seconds = timeout_seconds
        self._orphans_by_parent: dict[tuple[EntityType, str], list[OrphanedEntity]] = {}
        self._resolution_count = 0
        self._timeout_count = 0
        self._timeout_logged: set[Path] = set()

    def register_orphan(
        self,
        entity_data: object,
        entity_type: EntityType,
        required_parent_natural_id: str,
        file_path: Path,
    ) -> None:
        required_parent_type = self.PARENT_TYPE_MAP.get(entity_type)
        if not required_parent_type:
            logger.warning(f"Unknown parent type for entity type {entity_type}, cannot register orphan")
            return

        orphan = OrphanedEntity(
            entity_type=entity_type,
            entity_data=entity_data,
            required_parent_type=required_parent_type,
            required_parent_natural_id=required_parent_natural_id,
            file_path=file_path,
            first_seen=time.time(),
        )

        key = (required_parent_type, required_parent_natural_id)
        if key not in self._orphans_by_parent:
            self._orphans_by_parent[key] = []

        self._orphans_by_parent[key].append(orphan)
        logger.info(
            f"Registered orphan: {entity_type.value} from {file_path.name}, "
            f"waiting for {required_parent_type.value} '{required_parent_natural_id}'"
        )

    def resolve_orphans_for(self, parent_type: EntityType, parent_natural_id: str) -> list[OrphanedEntity]:
        key = (parent_type, parent_natural_id)
        orphans = self._orphans_by_parent.pop(key, [])

        if orphans:
            self._resolution_count += len(orphans)
            for orphan in orphans:
                self._timeout_logged.discard(orphan.file_path)
            logger.info(
                f"Resolved {len(orphans)} orphan(s) for {parent_type.value} '{parent_natural_id}' "
                f"(total resolved: {self._resolution_count})"
            )

        return orphans

    def check_timeouts(self, max_age_seconds: float | None = None) -> list[OrphanedEntity]:
        if max_age_seconds is None:
            max_age_seconds = self.timeout_seconds

        current_time = time.time()
        timed_out_orphans = []

        for orphans in self._orphans_by_parent.values():
            for orphan in orphans:
                age = current_time - orphan.first_seen
                if age >= max_age_seconds:
                    timed_out_orphans.append(orphan)
                    if orphan.file_path not in self._timeout_logged:
                        self._timeout_count += 1
                        self._timeout_logged.add(orphan.file_path)
                        logger.warning(
                            f"Orphan timeout: {orphan.entity_type.value} from {orphan.file_path.name}, "
                            f"waiting for {orphan.required_parent_type.value} '{orphan.required_parent_natural_id}', "
                            f"age: {age:.1f}s (kept in memory for eventual resolution)"
                        )

        return timed_out_orphans

    def get_orphan_stats(self) -> dict[str, int | dict[EntityType, int]]:
        stats_by_type: dict[EntityType, int] = {}
        total_count = 0

        for orphans in self._orphans_by_parent.values():
            for orphan in orphans:
                stats_by_type[orphan.entity_type] = stats_by_type.get(orphan.entity_type, 0) + 1
                total_count += 1

        return {
            "total_orphans": total_count,
            "by_type": {entity_type.value: count for entity_type, count in stats_by_type.items()},
            "total_resolved": self._resolution_count,
            "total_timed_out": self._timeout_count,
        }

    def clear(self) -> None:
        self._orphans_by_parent.clear()
        self._resolution_count = 0
        self._timeout_count = 0
        self._timeout_logged.clear()
