import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from smartem_agent.fs_parser import EpuParser
from smartem_agent.model.store import InMemoryDataStore
from smartem_agent2.error_handler import ErrorHandler
from smartem_agent2.event_classifier import ClassifiedEvent, EntityType
from smartem_agent2.metrics import ProcessingMetrics
from smartem_agent2.orphan_manager import OrphanManager
from smartem_common.schemas import FoilHoleData, GridData, GridSquareData, MicrographData
from smartem_common.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingStats:
    total_processed: int = 0
    successful: int = 0
    orphaned: int = 0
    failed: int = 0
    orphans_resolved: int = 0


class EventProcessor:
    def __init__(
        self,
        parser: EpuParser,
        datastore: InMemoryDataStore,
        orphan_manager: OrphanManager,
        error_handler: ErrorHandler | None = None,
        metrics: ProcessingMetrics | None = None,
        path_mapper: Callable[[Path], Path] = lambda p: p,
    ):
        self.parser = parser
        self.datastore = datastore
        self.orphan_manager = orphan_manager
        self.error_handler = error_handler or ErrorHandler()
        self.metrics = metrics or ProcessingMetrics()
        self.path_mapper = path_mapper
        self.stats = ProcessingStats()

    def process_batch(self, events: list[ClassifiedEvent]) -> ProcessingStats:
        batch_stats = ProcessingStats()

        for event in events:
            start_time = time.time()
            try:
                result = self._process_event(event)
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(latency_ms)

                batch_stats.total_processed += 1

                if result == ProcessingResult.SUCCESS:
                    batch_stats.successful += 1
                    self.metrics.record_success()
                elif result == ProcessingResult.ORPHANED:
                    batch_stats.orphaned += 1
                elif result == ProcessingResult.FAILED:
                    batch_stats.failed += 1
                    self.metrics.record_failure()

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_latency(latency_ms)
                self.metrics.record_failure()

                logger.error(f"Unexpected error processing {event.file_path}: {e}", exc_info=True)
                batch_stats.total_processed += 1
                batch_stats.failed += 1

        self.stats.total_processed += batch_stats.total_processed
        self.stats.successful += batch_stats.successful
        self.stats.orphaned += batch_stats.orphaned
        self.stats.failed += batch_stats.failed

        return batch_stats

    def _process_event(self, event: ClassifiedEvent) -> "ProcessingResult":
        match event.entity_type:
            case EntityType.GRID:
                return self._process_grid(event)
            case EntityType.ATLAS:
                return self._process_atlas(event)
            case EntityType.GRIDSQUARE:
                return self._process_gridsquare(event)
            case EntityType.FOILHOLE:
                return self._process_foilhole(event)
            case EntityType.MICROGRAPH:
                return self._process_micrograph(event)
            case EntityType.UNKNOWN:
                logger.debug(f"Skipping unknown file type: {event.file_path}")
                return ProcessingResult.FAILED
            case _:
                logger.warning(f"Unhandled entity type: {event.entity_type}")
                return ProcessingResult.FAILED

    def _process_grid(self, event: ClassifiedEvent) -> "ProcessingResult":
        try:
            grid = GridData(data_dir=event.file_path.parent.resolve())
            grid.acquisition_data = self.parser.parse_epu_session_manifest(str(event.file_path))

            grid.acquisition_data.uuid = self.datastore.acquisition.uuid

            self.datastore.create_grid(grid, path_mapper=self.path_mapper)
            logger.info(f"Created grid: {grid.uuid} from {event.file_path.name}")

            self.error_handler.record_success(event.file_path)

            resolved_orphans = self.orphan_manager.resolve_orphans_for(EntityType.GRID, str(grid.data_dir))
            self._resolve_orphan_entities(resolved_orphans)

            return ProcessingResult.SUCCESS

        except Exception as e:
            if self.error_handler.should_retry(e, event.file_path):
                category = self.error_handler.categorize_error(e, event.file_path)
                self.error_handler.record_retry(event.file_path)
                self.metrics.record_retry(category.value)
                logger.warning(f"Transient error processing grid {event.file_path.name}, will retry: {e}")
                return ProcessingResult.FAILED
            else:
                self.error_handler.record_permanent_failure(e, event.file_path)
                logger.error(f"Permanent failure processing grid {event.file_path}: {e}")
                return ProcessingResult.FAILED

    def _process_atlas(self, event: ClassifiedEvent) -> "ProcessingResult":
        try:
            grid_uuid = self.datastore.get_grid_by_path(str(event.file_path))
            if not grid_uuid:
                grid_dir = self._find_grid_dir(event.file_path)
                self.orphan_manager.register_orphan(
                    entity_data=event,
                    entity_type=EntityType.ATLAS,
                    required_parent_natural_id=str(grid_dir),
                    file_path=event.file_path,
                )
                logger.warning(f"Atlas file {event.file_path} has no parent grid, registering as orphan")
                return ProcessingResult.ORPHANED

            atlas_data = self.parser.parse_atlas_manifest(str(event.file_path), grid_uuid)
            if not atlas_data:
                logger.error(f"Failed to parse atlas manifest: {event.file_path}")
                return ProcessingResult.FAILED

            grid = self.datastore.get_grid(grid_uuid)
            grid.atlas_data = atlas_data
            self.datastore.update_grid(grid)
            self.datastore.create_atlas(atlas_data)

            if atlas_data.gridsquare_positions:
                gs_uuid_map = {}
                for gsid, gsp in atlas_data.gridsquare_positions.items():
                    gridsquare = GridSquareData(
                        gridsquare_id=str(gsid),
                        metadata=None,
                        grid_uuid=grid.uuid,
                        center_x=gsp.center[0] if gsp.center else None,
                        center_y=gsp.center[1] if gsp.center else None,
                        size_width=gsp.size[0] if gsp.size else None,
                        size_height=gsp.size[1] if gsp.size else None,
                    )

                    if found_grid_square := self.datastore.find_gridsquare_by_natural_id(str(gsid)):
                        gridsquare.uuid = found_grid_square.uuid
                        self.datastore.update_gridsquare(gridsquare, lowmag=True)
                        gs_uuid_map[str(gsid)] = gridsquare.uuid
                    else:
                        self.datastore.create_gridsquare(gridsquare, lowmag=True)
                        gs_uuid_map[str(gsid)] = gridsquare.uuid

                self.datastore.grid_registered(grid_uuid)

            logger.info(f"Processed atlas for grid {grid_uuid} from {event.file_path.name}")
            self.error_handler.record_success(event.file_path)
            return ProcessingResult.SUCCESS

        except Exception as e:
            if self.error_handler.should_retry(e, event.file_path):
                category = self.error_handler.categorize_error(e, event.file_path)
                self.error_handler.record_retry(event.file_path)
                self.metrics.record_retry(category.value)
                logger.warning(f"Transient error processing atlas {event.file_path.name}, will retry: {e}")
                return ProcessingResult.FAILED
            else:
                self.error_handler.record_permanent_failure(e, event.file_path)
                logger.error(f"Permanent failure processing atlas {event.file_path}: {e}")
                return ProcessingResult.FAILED

    def _process_gridsquare(self, event: ClassifiedEvent) -> "ProcessingResult":
        try:
            grid_uuid = self.datastore.get_grid_by_path(str(event.file_path))
            if not grid_uuid:
                grid_dir = self._find_grid_dir(event.file_path)
                self.orphan_manager.register_orphan(
                    entity_data=event,
                    entity_type=EntityType.GRIDSQUARE,
                    required_parent_natural_id=str(grid_dir),
                    file_path=event.file_path,
                )
                logger.warning(f"GridSquare file {event.file_path} has no parent grid, registering as orphan")
                return ProcessingResult.ORPHANED

            if event.natural_id:
                gridsquare_metadata = self.parser.parse_gridsquare_metadata(str(event.file_path), self.path_mapper)
                if not gridsquare_metadata:
                    logger.error(f"Failed to parse gridsquare metadata: {event.file_path}")
                    return ProcessingResult.FAILED

                gridsquare_id = event.natural_id
            else:
                gridsquare_manifest = self.parser.parse_gridsquare_manifest(str(event.file_path))
                if not gridsquare_manifest:
                    logger.error(f"Failed to parse gridsquare manifest: {event.file_path}")
                    return ProcessingResult.FAILED

                gridsquare_id_match = self.parser.gridsquare_dir_pattern.search(str(event.file_path))
                if not gridsquare_id_match:
                    logger.error(f"Could not extract gridsquare ID from path: {event.file_path}")
                    return ProcessingResult.FAILED
                gridsquare_id = gridsquare_id_match.group(1)
                gridsquare_metadata = None

            gridsquare = self.datastore.find_gridsquare_by_natural_id(gridsquare_id)
            if not gridsquare:
                gridsquare = GridSquareData(
                    gridsquare_id=gridsquare_id,
                    metadata=gridsquare_metadata,
                    grid_uuid=grid_uuid,
                )
                self.datastore.create_gridsquare(gridsquare)
                logger.info(f"Created gridsquare {gridsquare_id} (UUID: {gridsquare.uuid})")
            else:
                if gridsquare_metadata:
                    gridsquare.metadata = gridsquare_metadata
                self.datastore.update_gridsquare(gridsquare)
                logger.info(f"Updated gridsquare {gridsquare_id} (UUID: {gridsquare.uuid})")

            if gridsquare_metadata and gridsquare_metadata.foilhole_positions:
                all_foilhole_data = [
                    FoilHoleData(
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
                    for fh_id, fh_position in gridsquare_metadata.foilhole_positions.items()
                ]
                self.datastore.create_foilholes(gridsquare.uuid, all_foilhole_data)
                self.datastore.gridsquare_registered(gridsquare.uuid)

            resolved_orphans = self.orphan_manager.resolve_orphans_for(EntityType.GRIDSQUARE, gridsquare_id)
            self._resolve_orphan_entities(resolved_orphans)

            self.error_handler.record_success(event.file_path)
            return ProcessingResult.SUCCESS

        except Exception as e:
            if self.error_handler.should_retry(e, event.file_path):
                category = self.error_handler.categorize_error(e, event.file_path)
                self.error_handler.record_retry(event.file_path)
                self.metrics.record_retry(category.value)
                logger.warning(f"Transient error processing gridsquare {event.file_path.name}, will retry: {e}")
                return ProcessingResult.FAILED
            else:
                self.error_handler.record_permanent_failure(e, event.file_path)
                logger.error(f"Permanent failure processing gridsquare {event.file_path}: {e}")
                return ProcessingResult.FAILED

    def _process_foilhole(self, event: ClassifiedEvent) -> "ProcessingResult":
        try:
            foilhole = self.parser.parse_foilhole_manifest(str(event.file_path))
            if not foilhole:
                logger.error(f"Failed to parse foilhole manifest: {event.file_path}")
                return ProcessingResult.FAILED

            gridsquare = self.datastore.find_gridsquare_by_natural_id(foilhole.gridsquare_id)
            if not gridsquare:
                logger.info(
                    f"FoilHole {foilhole.id} waiting for gridsquare {foilhole.gridsquare_id}, registering as orphan"
                )
                self.orphan_manager.register_orphan(
                    entity_data=foilhole,
                    entity_type=EntityType.FOILHOLE,
                    required_parent_natural_id=foilhole.gridsquare_id,
                    file_path=event.file_path,
                )
                return ProcessingResult.ORPHANED

            foilhole.gridsquare_uuid = gridsquare.uuid
            success = self.datastore.upsert_foilhole(foilhole)
            if not success:
                logger.error(f"Failed to upsert foilhole {foilhole.id}")
                return ProcessingResult.FAILED

            logger.info(f"Processed foilhole {foilhole.id} (UUID: {foilhole.uuid})")

            resolved_orphans = self.orphan_manager.resolve_orphans_for(EntityType.FOILHOLE, foilhole.id)
            self._resolve_orphan_entities(resolved_orphans)

            self.error_handler.record_success(event.file_path)
            return ProcessingResult.SUCCESS

        except Exception as e:
            if self.error_handler.should_retry(e, event.file_path):
                category = self.error_handler.categorize_error(e, event.file_path)
                self.error_handler.record_retry(event.file_path)
                self.metrics.record_retry(category.value)
                logger.warning(f"Transient error processing foilhole {event.file_path.name}, will retry: {e}")
                return ProcessingResult.FAILED
            else:
                self.error_handler.record_permanent_failure(e, event.file_path)
                logger.error(f"Permanent failure processing foilhole {event.file_path}: {e}")
                return ProcessingResult.FAILED

    def _process_micrograph(self, event: ClassifiedEvent) -> "ProcessingResult":
        try:
            micrograph_manifest = self.parser.parse_micrograph_manifest(str(event.file_path))
            if not micrograph_manifest:
                logger.error(f"Failed to parse micrograph manifest: {event.file_path}")
                return ProcessingResult.FAILED

            match = self.parser.micrograph_xml_file_pattern.search(str(event.file_path))
            if not match:
                logger.error(f"Could not extract foilhole ID from micrograph path: {event.file_path}")
                return ProcessingResult.FAILED

            foilhole_id = match.group(1)
            location_id = match.group(2)

            foilhole = self.datastore.find_foilhole_by_natural_id(foilhole_id)
            if not foilhole:
                logger.info(f"Micrograph {micrograph_manifest.unique_id} waiting for foilhole {foilhole_id}")
                return ProcessingResult.ORPHANED

            gridsquare_id = foilhole.gridsquare_id

            micrograph = MicrographData(
                id=micrograph_manifest.unique_id,
                gridsquare_id=gridsquare_id,
                foilhole_uuid=foilhole.uuid,
                foilhole_id=foilhole_id,
                location_id=location_id,
                high_res_path=Path(""),
                manifest_file=event.file_path,
                manifest=micrograph_manifest,
            )

            success = self.datastore.upsert_micrograph(micrograph)
            if not success:
                logger.error(f"Failed to upsert micrograph {micrograph.id}")
                return ProcessingResult.FAILED

            logger.info(f"Processed micrograph {micrograph.id} (UUID: {micrograph.uuid})")
            self.error_handler.record_success(event.file_path)
            return ProcessingResult.SUCCESS

        except Exception as e:
            if self.error_handler.should_retry(e, event.file_path):
                category = self.error_handler.categorize_error(e, event.file_path)
                self.error_handler.record_retry(event.file_path)
                self.metrics.record_retry(category.value)
                logger.warning(f"Transient error processing micrograph {event.file_path.name}, will retry: {e}")
                return ProcessingResult.FAILED
            else:
                self.error_handler.record_permanent_failure(e, event.file_path)
                logger.error(f"Permanent failure processing micrograph {event.file_path}: {e}")
                return ProcessingResult.FAILED

    def _resolve_orphan_entities(self, orphans: list) -> None:
        for orphan in orphans:
            try:
                match orphan.entity_type:
                    case EntityType.ATLAS:
                        self._resolve_orphan_atlas(orphan)
                    case EntityType.GRIDSQUARE:
                        self._resolve_orphan_gridsquare(orphan)
                    case EntityType.FOILHOLE:
                        self._resolve_orphan_foilhole(orphan)
                    case EntityType.MICROGRAPH:
                        self._resolve_orphan_micrograph(orphan)
                    case _:
                        logger.warning(f"Unknown orphan type: {orphan.entity_type}")

                self.stats.orphans_resolved += 1

            except Exception as e:
                logger.error(f"Failed to resolve orphan {orphan.file_path}: {e}")

    def _resolve_orphan_foilhole(self, orphan) -> None:
        foilhole: FoilHoleData = orphan.entity_data
        gridsquare = self.datastore.find_gridsquare_by_natural_id(foilhole.gridsquare_id)
        if not gridsquare:
            logger.error(f"Cannot resolve foilhole orphan {foilhole.id}: gridsquare {foilhole.gridsquare_id} not found")
            return

        foilhole.gridsquare_uuid = gridsquare.uuid
        success = self.datastore.upsert_foilhole(foilhole)
        if success:
            logger.info(f"Resolved orphan foilhole {foilhole.id} (UUID: {foilhole.uuid})")

            resolved_children = self.orphan_manager.resolve_orphans_for(EntityType.FOILHOLE, foilhole.id)
            self._resolve_orphan_entities(resolved_children)
        else:
            logger.error(f"Failed to resolve orphan foilhole {foilhole.id}")

    def _resolve_orphan_atlas(self, orphan) -> None:
        event: ClassifiedEvent = orphan.entity_data
        result = self._process_atlas(event)
        if result != ProcessingResult.SUCCESS:
            logger.error(f"Failed to resolve atlas orphan {event.file_path}")

    def _resolve_orphan_micrograph(self, orphan) -> None:
        logger.warning("Micrograph orphan resolution not yet implemented")

    def _resolve_orphan_gridsquare(self, orphan) -> None:
        event: ClassifiedEvent = orphan.entity_data
        result = self._process_gridsquare(event)
        if result != ProcessingResult.SUCCESS:
            logger.error(f"Failed to resolve gridsquare orphan {event.file_path}")

    def _find_grid_dir(self, file_path: Path) -> Path:
        path = file_path
        while path.parent != path:
            if (path / "EpuSession.dm").exists() or any(
                (path / d).exists() for d in ["Images-Disc1", "Sample0", "Sample1", "Sample2", "Sample3"]
            ):
                return path
            path = path.parent
        return file_path.parent

    def get_stats(self) -> ProcessingStats:
        return self.stats

    def reset_stats(self) -> None:
        self.stats = ProcessingStats()


class ProcessingResult:
    SUCCESS = "success"
    ORPHANED = "orphaned"
    FAILED = "failed"
