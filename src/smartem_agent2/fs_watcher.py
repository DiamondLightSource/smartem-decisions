import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from smartem_agent.fs_parser import EpuParser
from smartem_agent.model.store import InMemoryDataStore, PersistentDataStore
from smartem_agent2.event_classifier import EventClassifier
from smartem_agent2.event_processor import EventProcessor
from smartem_agent2.event_queue import EventQueue
from smartem_agent2.orphan_manager import OrphanManager
from smartem_backend.api_client import SSEAgentClient
from smartem_common.utils import get_logger

logger = get_logger(__name__)

DEFAULT_PATTERNS = [
    "EpuSession.dm",
    "**/EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "**/Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "**/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "**/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "**/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
    "**/Atlas/Atlas.dm",
]


class SmartEMWatcherV2(FileSystemEventHandler):
    watched_event_types = ["created", "modified"]

    def __init__(
        self,
        watch_dir: Path,
        dry_run: bool = False,
        api_url: str | None = None,
        log_interval: float = 10.0,
        patterns: list[str] | None = None,
        path_mapper: Callable[[Path], Path] = lambda p: p,
        agent_id: str | None = None,
        session_id: str | None = None,
        sse_timeout: int = 30,
        heartbeat_interval: int = 60,
        max_queue_size: int = 50000,
        batch_size: int = 100,
        processing_interval: float = 0.05,
        orphan_timeout: float = 300.0,
        orphan_check_interval: float = 60.0,
        error_max_retries: int = 5,
        error_base_delay: float = 1.0,
        error_max_delay: float = 60.0,
        metrics_window_size: int = 1000,
    ):
        self.watch_dir = watch_dir.absolute()
        self.log_interval = log_interval
        self.patterns = patterns if patterns is not None else DEFAULT_PATTERNS.copy()
        self.path_mapper = path_mapper
        self.last_log_time = time.time()
        self.verbose = logging.getLogger().level <= logging.INFO

        self.event_classifier = EventClassifier()
        self.event_queue = EventQueue(max_size=max_queue_size)
        self.orphan_manager = OrphanManager(timeout_seconds=orphan_timeout)

        if dry_run:
            self.datastore = InMemoryDataStore(str(self.watch_dir))
        else:
            self.datastore = PersistentDataStore(str(self.watch_dir), api_url)

        self.parser = EpuParser()

        from smartem_agent2.error_handler import ErrorHandler
        from smartem_agent2.metrics import ProcessingMetrics

        self.error_handler = ErrorHandler(
            max_retries=error_max_retries, base_delay=error_base_delay, max_delay=error_max_delay
        )
        self.metrics = ProcessingMetrics(window_size=metrics_window_size)
        self.event_processor = EventProcessor(
            self.parser, self.datastore, self.orphan_manager, self.error_handler, self.metrics, path_mapper
        )

        self.batch_size = batch_size
        self.processing_interval = processing_interval
        self.orphan_check_interval = orphan_check_interval

        self._processing_thread = None
        self._orphan_check_thread = None
        self._shutdown_event = threading.Event()

        self.sse_client = None
        self.sse_thread = None
        self.heartbeat_thread = None
        self.heartbeat_interval = heartbeat_interval
        self._sse_shutdown_event = threading.Event()
        self._heartbeat_shutdown_event = threading.Event()

        if agent_id and session_id and api_url and not dry_run:
            self.sse_client = SSEAgentClient(
                base_url=api_url, agent_id=agent_id, session_id=session_id, timeout=sse_timeout
            )
            self._start_sse_stream()
            self._start_heartbeat_timer()

        self._start_processing_loop()
        self._start_orphan_check_loop()

        logger.info(
            f"SmartEM Watcher V2 initialized: watch_dir={self.watch_dir}, "
            f"queue_size={max_queue_size}, batch_size={batch_size}, "
            f"processing_interval={processing_interval}s, orphan_timeout={orphan_timeout}s"
        )

    def _start_processing_loop(self):
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=False)
        self._processing_thread.start()
        logger.info("Started event processing loop")

    def _processing_loop(self):
        while not self._shutdown_event.is_set():
            try:
                if self.event_queue.size() > 0:
                    batch = self.event_queue.dequeue_batch(max_size=self.batch_size)
                    if batch:
                        stats = self.event_processor.process_batch(batch)
                        if stats.total_processed > 0:
                            logger.info(
                                f"Processed batch: {stats.total_processed} events "
                                f"({stats.successful} successful, {stats.orphaned} orphaned, "
                                f"{stats.failed} failed, {stats.orphans_resolved} resolved)"
                            )
                else:
                    recovered = self.event_queue.recover_evicted_events()
                    if recovered == 0:
                        time.sleep(self.processing_interval)

            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                time.sleep(self.processing_interval)

        logger.info("Processing loop stopped")

    def _start_orphan_check_loop(self):
        self._orphan_check_thread = threading.Thread(target=self._orphan_check_loop, daemon=False)
        self._orphan_check_thread.start()
        logger.info("Started orphan timeout check loop")

    def _orphan_check_loop(self):
        while not self._shutdown_event.is_set():
            try:
                if self._shutdown_event.wait(self.orphan_check_interval):
                    break

                timed_out_orphans = self.orphan_manager.check_timeouts()
                if timed_out_orphans:
                    logger.warning(f"Found {len(timed_out_orphans)} timed out orphans")

            except Exception as e:
                logger.error(f"Error in orphan check loop: {e}", exc_info=True)

        logger.info("Orphan check loop stopped")

    def _start_sse_stream(self):
        if self.sse_client:
            logger.info(
                f"Starting SSE stream for agent {self.sse_client.agent_id}, session {self.sse_client.session_id}"
            )
            self.sse_thread = threading.Thread(target=self._run_sse_stream, daemon=False)
            self.sse_thread.start()

    def _run_sse_stream(self):
        retry_count = 0
        max_retries = 5
        retry_delay = 10

        while not self._sse_shutdown_event.is_set() and retry_count < max_retries:
            try:
                logger.info(f"SSE stream attempt {retry_count + 1}/{max_retries}")
                self.sse_client.stream_instructions(
                    instruction_callback=self._handle_sse_instruction,
                    connection_callback=self._handle_sse_connection,
                    error_callback=self._handle_sse_error,
                )
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"SSE stream error (attempt {retry_count}/{max_retries}): {e}")

                if retry_count < max_retries and not self._sse_shutdown_event.is_set():
                    logger.info(f"Retrying SSE connection in {retry_delay} seconds...")
                    if self._sse_shutdown_event.wait(retry_delay):
                        break

        if retry_count >= max_retries:
            logger.error("SSE stream failed after maximum retry attempts")
        else:
            logger.info("SSE stream stopped")

    def _start_heartbeat_timer(self):
        if self.sse_client and self.heartbeat_interval > 0:
            logger.info(f"Starting heartbeat timer with interval {self.heartbeat_interval} seconds")
            self.heartbeat_thread = threading.Thread(target=self._run_heartbeat_loop, daemon=False)
            self.heartbeat_thread.start()

    def _run_heartbeat_loop(self):
        while not self._heartbeat_shutdown_event.is_set():
            try:
                if self._heartbeat_shutdown_event.wait(self.heartbeat_interval):
                    break

                if self.sse_client and self.sse_client.is_connected():
                    success = self.sse_client.send_heartbeat()
                    if success:
                        logger.debug("Heartbeat sent successfully")
                    else:
                        logger.warning("Failed to send heartbeat")
                else:
                    logger.debug("Skipping heartbeat - SSE client not connected")

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

        logger.info("Heartbeat loop stopped")

    def _handle_sse_instruction(self, instruction_data: dict):
        instruction_id = instruction_data.get("instruction_id")
        instruction_type = instruction_data.get("instruction_type")
        payload = instruction_data.get("payload", {})

        logger.info(f"SSE Instruction - ID: {instruction_id}, Type: {instruction_type}, Payload: {payload}")

        start_time = time.time()
        try:
            result = self._process_instruction(instruction_type, payload)
            processing_time_ms = int((time.time() - start_time) * 1000)

            self.sse_client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=result or "Instruction processed successfully",
                processing_time_ms=processing_time_ms,
            )
            logger.info(f"Processed and acknowledged instruction {instruction_id} in {processing_time_ms}ms")

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to process instruction {instruction_id}: {e}")
            try:
                self.sse_client.acknowledge_instruction(
                    instruction_id=instruction_id,
                    status="failed",
                    error_message=str(e),
                    processing_time_ms=processing_time_ms,
                )
            except Exception as ack_error:
                logger.error(f"Failed to acknowledge instruction failure {instruction_id}: {ack_error}")

    def _process_instruction(self, instruction_type: str, payload: dict) -> str:
        match instruction_type:
            case "agent.status.request":
                stats = self.event_processor.get_stats()
                orphan_stats = self.orphan_manager.get_orphan_stats()
                metrics_summary = self.metrics.get_summary()
                error_stats = self.error_handler.get_error_stats()
                latency = metrics_summary["latency_percentiles"]

                return (
                    f"Agent watching {self.watch_dir}\n"
                    f"Queue: {self.event_queue.size()} events\n"
                    f"Processed: {stats.total_processed} total "
                    f"({stats.successful} success, {stats.orphaned} orphaned, {stats.failed} failed)\n"
                    f"Orphans: {orphan_stats['total_orphans']} pending, "
                    f"{orphan_stats['total_resolved']} resolved, "
                    f"{orphan_stats['total_timed_out']} timed out\n"
                    f"Performance: {metrics_summary['throughput_per_second']:.2f} events/sec, "
                    f"success rate {metrics_summary['success_rate'] * 100:.1f}%\n"
                    f"Latency (ms): p50={latency['p50']:.1f}, p95={latency['p95']:.1f}, "
                    f"p99={latency['p99']:.1f}, max={latency['max']:.1f}\n"
                    f"Errors: {error_stats['active_errors']} active, "
                    f"by category: {error_stats['error_counts']}\n"
                    f"Uptime: {metrics_summary['uptime_seconds']:.0f}s"
                )

            case "agent.config.update":
                if "log_interval" in payload:
                    old_interval = self.log_interval
                    self.log_interval = float(payload["log_interval"])
                    return f"Log interval updated from {old_interval} to {self.log_interval}"
                return "No supported config updates in payload"

            case "agent.info.datastore":
                grid_count = len(self.datastore.grids) if self.datastore else 0
                return f"Datastore contains {grid_count} grids"

            case "agent.info.metrics":
                metrics_summary = self.metrics.get_summary()
                retry_dist = metrics_summary["retry_distribution"]
                latency = metrics_summary["latency_percentiles"]

                return (
                    f"Metrics Summary:\n"
                    f"Successes: {metrics_summary['success_count']}, "
                    f"Failures: {metrics_summary['failure_count']}\n"
                    f"Success rate: {metrics_summary['success_rate'] * 100:.1f}%\n"
                    f"Throughput: {metrics_summary['throughput_per_second']:.2f} events/sec\n"
                    f"Latency percentiles (ms): p50={latency['p50']:.1f}, "
                    f"p95={latency['p95']:.1f}, p99={latency['p99']:.1f}\n"
                    f"Mean latency: {latency['mean']:.1f}ms, Max: {latency['max']:.1f}ms\n"
                    f"Retry distribution: {retry_dist if retry_dist else 'none'}\n"
                    f"Uptime: {metrics_summary['uptime_seconds']:.0f}s"
                )

            case "agent.info.errors":
                error_stats = self.error_handler.get_error_stats()
                return (
                    f"Error Statistics:\n"
                    f"Active errors: {error_stats['active_errors']}\n"
                    f"Errors by category:\n"
                    f"  Permanent corrupt: {error_stats['error_counts'].get('permanent_corrupt', 0)}\n"
                    f"  Permanent missing: {error_stats['error_counts'].get('permanent_missing', 0)}\n"
                    f"  Transient parser: {error_stats['error_counts'].get('transient_parser', 0)}\n"
                    f"  Transient API: {error_stats['error_counts'].get('transient_api', 0)}\n"
                    f"  Unknown: {error_stats['error_counts'].get('unknown', 0)}\n"
                    f"Currently retrying:\n"
                    f"  Transient parser: {error_stats['errors_by_category'].get('transient_parser', 0)}\n"
                    f"  Transient API: {error_stats['errors_by_category'].get('transient_api', 0)}"
                )

            case "agent.info.orphans":
                orphan_stats = self.orphan_manager.get_orphan_stats()
                return (
                    f"Orphan Statistics:\n"
                    f"Total orphans: {orphan_stats['total_orphans']}\n"
                    f"By type:\n"
                    f"  GridSquares: {orphan_stats['by_type'].get('gridsquare', 0)}\n"
                    f"  FoilHoles: {orphan_stats['by_type'].get('foilhole', 0)}\n"
                    f"  Micrographs: {orphan_stats['by_type'].get('micrograph', 0)}\n"
                    f"  Atlases: {orphan_stats['by_type'].get('atlas', 0)}\n"
                    f"Total resolved: {orphan_stats['total_resolved']}\n"
                    f"Total timed out: {orphan_stats['total_timed_out']}"
                )

            case "microscope.control.move_stage":
                stage_position = payload.get("stage_position", {})
                speed = payload.get("speed", "normal")
                x, y, z = stage_position.get("x"), stage_position.get("y"), stage_position.get("z")
                logger.info(f"Moving stage to position: x={x}, y={y}, z={z}, speed={speed}")
                time.sleep(0.5)
                return f"Stage moved to {stage_position}"

            case "microscope.control.take_image":
                image_params = payload.get("image_params", {})
                logger.info(f"Taking image with parameters: {image_params}")
                time.sleep(1.0)
                return f"Image acquired with params {image_params}"

            case "microscope.control.reorder_gridsquares":
                gridsquare_ids = payload.get("gridsquare_ids", [])
                priority = payload.get("priority", "normal")
                reason = payload.get("reason", "")
                logger.info(f"Reordering grid squares: {gridsquare_ids}, priority: {priority}, reason: {reason}")
                time.sleep(0.3)
                return f"Reordered {len(gridsquare_ids)} grid squares with {priority} priority"

            case "microscope.control.skip_gridsquares":
                gridsquare_ids = payload.get("gridsquare_ids", [])
                reason = payload.get("reason", "")
                logger.info(f"Skipping grid squares: {gridsquare_ids}, reason: {reason}")
                time.sleep(0.2)
                return f"Skipped {len(gridsquare_ids)} grid squares"

            case "microscope.control.reorder_foilholes":
                gridsquare_id = payload.get("gridsquare_id")
                foilhole_ids = payload.get("foilhole_ids", [])
                priority = payload.get("priority", "normal")
                reason = payload.get("reason", "")
                logger.info(
                    f"Reordering foilholes in {gridsquare_id}: {foilhole_ids}, priority: {priority}, reason: {reason}"
                )
                time.sleep(0.4)
                return f"Reordered {len(foilhole_ids)} foilholes in {gridsquare_id}"

            case _:
                logger.warning(f"Unknown instruction type: {instruction_type}")
                return f"Logged unknown instruction type: {instruction_type}"

    def _handle_sse_connection(self, connection_data: dict):
        agent_id = connection_data.get("agent_id")
        session_id = connection_data.get("session_id")
        connection_id = connection_data.get("connection_id")
        logger.info(f"SSE Connected - Agent: {agent_id}, Session: {session_id}, Connection: {connection_id}")

    def _handle_sse_error(self, error: Exception):
        logger.error(f"SSE Error: {error}")

    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = Path(path).relative_to(self.watch_dir)
            return any(rel_path.match(pattern) for pattern in self.patterns)
        except ValueError:
            return False

    def on_any_event(self, event):
        if event.is_directory or not self.matches_pattern(event.src_path):
            return

        if event.event_type not in self.watched_event_types:
            return

        try:
            if not os.path.exists(event.src_path):
                return
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"Error accessing file {event.src_path}: {str(e)}")
            return

        current_time = time.time()

        classified_event = self.event_classifier.classify(event.src_path, event.event_type, current_time)

        self.event_queue.enqueue(classified_event)

        if current_time - self.last_log_time >= self.log_interval:
            self._log_status()

    def _log_status(self):
        stats = self.event_processor.get_stats()
        orphan_stats = self.orphan_manager.get_orphan_stats()
        queue_size = self.event_queue.size()

        status_log = {
            "timestamp": datetime.now().isoformat(),
            "queue_size": queue_size,
            "events_processed": stats.total_processed,
            "successful": stats.successful,
            "orphaned": stats.orphaned,
            "failed": stats.failed,
            "orphans_resolved": stats.orphans_resolved,
            "orphans_pending": orphan_stats["total_orphans"],
            "orphans_by_type": orphan_stats["by_type"],
            "orphans_timed_out": orphan_stats["total_timed_out"],
        }

        logger.info(status_log)
        self.last_log_time = time.time()

    def stop(self):
        logger.info("Stopping SmartEM Watcher V2...")

        self._shutdown_event.set()

        if self._processing_thread and self._processing_thread.is_alive():
            logger.info("Waiting for processing thread to stop...")
            self._processing_thread.join(timeout=10)

        if self._orphan_check_thread and self._orphan_check_thread.is_alive():
            logger.info("Waiting for orphan check thread to stop...")
            self._orphan_check_thread.join(timeout=10)

        self._sse_shutdown_event.set()
        self._heartbeat_shutdown_event.set()

        if self.sse_client:
            self.sse_client.stop()

        if self.sse_thread and self.sse_thread.is_alive():
            logger.info("Waiting for SSE thread to stop...")
            self.sse_thread.join(timeout=10)

        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            logger.info("Waiting for heartbeat thread to stop...")
            self.heartbeat_thread.join(timeout=5)

        logger.info("SmartEM Watcher V2 stopped")
