import logging
import os
import re
import sys
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from watchdog.events import FileSystemEventHandler

from src.epu_data_intake.data_model import (
    EpuAcquisitionSessionStore,
    Grid,
    GridSquareData,
    MicrographData,
)
from src.epu_data_intake.fs_parser import EpuParser

"""Default glob patterns for EPU data files.

A list of patterns that match the standard EPU file structure for cryo-EM data
collection, including session files, grid squares, foil holes, and atlas images.

Patterns match the following files:
* Main EPU session file
* Grid square metadata files
* Grid square image XML files
* Foil hole data XML files
* Foil hole location XML files
* Atlas overview files

:type: list[str]
"""
DEFAULT_PATTERNS = [  # TODO consider merging with props in EpuParser
    "EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
]


class RateLimitedFilesystemEventHandler(FileSystemEventHandler):
    """File system event handler with rate limiting capabilities.

    This handler processes file system events from watchdog, specifically watching
    for file creation and modification events. The implementation ensures reliable
    file write detection across both Windows and Linux platforms.

    :cvar watched_event_types: List of event types to monitor
    :type watched_event_types: list[str]
    :ivar acquisition: EPU session data store handler
    :type acquisition: EpuAcquisitionSessionStore | None
    :ivar watch_dir: Directory path being monitored for changes
    :type watch_dir: Path | None
    :ivar last_log_time: Timestamp of the last logging event
    :type last_log_time: float
    :ivar log_interval: Minimum time between logging events in seconds
    :type log_interval: float
    :ivar patterns: List of file patterns to watch for
    :type patterns: list[str]
    :ivar verbose: Enable detailed logging output
    :type verbose: bool
    :ivar changed_files: Dictionary tracking file modification states
    :type changed_files: dict
    """

    watched_event_types = ["created", "modified"]
    datastore: EpuAcquisitionSessionStore | None = None
    watch_dir: Path | None = None

    # TODO test with a lower log_interval value, set lowest possible default, better naming
    def __init__(
        self,
        watch_dir,
        dry_run: bool = False,
        api_url: str | None = None,
        log_interval: float = 10.0,
        patterns: list[str] = DEFAULT_PATTERNS,
    ):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.patterns = patterns
        self.verbose = logging.getLogger().level <= logging.INFO
        # Distinguish between new and previously seen files.
        self.changed_files = {}

        # Maintain a buffer of "orphaned" files - files that appear to belong to a grid that doesn't exist yet
        self.orphaned_files = {}  # path -> (event, timestamp, file_stat)

        self._set_watch_dir(watch_dir)
        self._init_datastore(dry_run, api_url)

    # TODO unit test this method
    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = str(Path(path).relative_to(self.watch_dir))
            rel_path = rel_path.replace("\\", "/")  # Normalize path separators
            return any(fnmatch(rel_path, pattern) for pattern in self.patterns)
        except ValueError:
            return False

    # TODO on Win there's primary and secondary output dirs - work directly with primary if possible otherwise
    #  operate across both. Note: data is first written to primary output dir then later maybe partially copied
    #  to secondary dir.
    def _set_watch_dir(self, path: Path):
        self.watch_dir = path.absolute()  # TODO this could cause problems in Win - test!

    def _init_datastore(self, dry_run: bool = False, api_url: str = None):
        self.datastore = EpuAcquisitionSessionStore(str(self.watch_dir), dry_run, api_url)
        logging.debug(
            f"Instantiated new datastore, "
            + ("in-memory only" if self.datastore.in_memory_only else "data will be permanently saved on the backend")
        )
        if self.datastore.in_memory_only:
            logging.info(f"Acquisition session uuid assigned: {self.datastore.uuid}")

    # TODO Enhancement: log all events to graylog (if reachable) for session debugging and playback
    def on_any_event(self, event):
        if event.is_directory or not self.matches_pattern(event.src_path):
            if event.is_directory:
                logging.debug(f"Skipping non-matching path: {event.src_path}")
            return

        if event.event_type not in self.watched_event_types:
            if event.is_directory:
                logging.debug(f"Skipping non-matching event type: {event.event_type}")
            return

        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval:
            self._flush_events()

        file_stat = None
        try:
            if os.path.exists(event.src_path):
                file_stat = os.stat(event.src_path)
        except (FileNotFoundError, PermissionError) as e:
            if self.verbose:
                logging.warning(f"{str(e)}")

        new_file_detected = event.src_path not in self.changed_files
        self.changed_files[event.src_path] = (event, current_time, file_stat)

        # New grid discovered? If so - instantiate in store
        if new_file_detected and re.search(EpuParser.session_dm_pattern, event.src_path):
            assert self.datastore.get_grid_by_path(event.src_path) is None  # guaranteed because is a new file
            grid = Grid(str(Path(event.src_path).parent.resolve()))
            self.datastore.add_grid(grid)

        # try to work out which grid the touched file relates to
        grid_id = self.datastore.get_grid_by_path(event.src_path)
        if grid_id is None:
            # This must be an orphaned file since it matched one of patterns for files we are interested in,
            #   but a containing grid doesn't exist yet - store it for when we have the grid.
            if self.verbose:
                logging.debug(
                    f"Could not determine which grid this data belongs to: {event.src_path}, adding to orphans"
                )
            self.orphaned_files[event.src_path] = (event, current_time, file_stat)
            return

        match event.src_path:
            case path if re.search(EpuParser.session_dm_pattern, path):
                self._on_session_detected(path, grid_id, new_file_detected)
                # After processing the session file, check for any orphaned files belonging to this grid
                self._process_orphaned_files(grid_id)
            case path if re.search(EpuParser.atlas_dm_pattern, path):
                self._on_atlas_detected(path, grid_id, new_file_detected)
            case path if re.search(EpuParser.gridsquare_dm_file_pattern, path):
                self._on_gridsquare_metadata_detected(path, grid_id, new_file_detected)
            case path if re.search(EpuParser.gridsquare_xml_file_pattern, path):
                self._on_gridsquare_manifest_detected(path, grid_id, new_file_detected)
            case path if re.search(EpuParser.foilhole_xml_file_pattern, path):
                self._on_foilhole_detected(path, grid_id, new_file_detected)
            case path if re.search(EpuParser.micrograph_xml_file_pattern, path):
                self._on_micrograph_detected(path, grid_id, new_file_detected)

    def _on_session_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.debug(f"Session manifest {'detected' if is_new_file else 'updated'}: {path}")
        session_data = EpuParser.parse_epu_session_manifest(path)
        gridstore = self.datastore.grids.get(grid_id)

        if gridstore and session_data != gridstore.session_data:
            # Create the acquisition first if we're not in dry run mode
            if not self.datastore.in_memory_only and self.datastore.api_client:
                success = self.datastore.api_client.create("acquisition", self.datastore.uuid, session_data)
                if success:
                    logging.info(f"Created acquisition for session #{self.datastore.uuid} {session_data.name}")

            gridstore.session_data = session_data
            logging.debug(f"Updated session data for grid {grid_id}")
            logging.info(gridstore.session_data)

    def _process_orphaned_files(self, grid_id):
        """Process any orphaned files that belong to this grid"""
        for path, (event, timestamp, file_stat) in self.orphaned_files.items():
            # Check if this orphaned file belongs to the new grid
            if self.datastore.get_grid_by_path(path) == grid_id:
                logging.debug(f"Processing previously orphaned file: {path}")
                self.on_any_event(event)  # Process the file as if we just received the event

        # Create a new dictionary excluding the processed files
        self.orphaned_files = {
            path: data for path, data in self.orphaned_files.items() if self.datastore.get_grid_by_path(path) != grid_id
        }

    def _on_atlas_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.debug(f"Atlas {'detected' if is_new_file else 'updated'}: {path}")
        gridstore = self.datastore.grids.get(grid_id)
        atlas_data = EpuParser.parse_atlas_manifest(path)
        if atlas_data != gridstore.atlas_data:
            gridstore.atlas_data = atlas_data
            logging.info(gridstore.atlas_data)

    def _on_gridsquare_metadata_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.info(f"Gridsquare metadata {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = EpuParser.gridsquare_dm_file_pattern.search(path).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridstore = self.datastore.grids.get(grid_id)
        gridsquare_metadata = EpuParser.parse_gridsquare_metadata(path)

        # Check if the gridsquares EntityStore has an API client configured
        if hasattr(gridstore.gridsquares, "_api_client") and gridstore.gridsquares._api_client:
            logging.info(f"Grid's gridsquares EntityStore has API client configured")
        else:
            logging.info(f"Grid's gridsquares EntityStore does NOT have API client configured")

        # Check if this is a new gridsquare or an update to an existing one
        if not gridstore.gridsquares.exists(gridsquare_id):
            logging.info(f"Creating new GridSquare: {gridsquare_id}")
            gridsquare_data = GridSquareData(
                id=gridsquare_id,
                metadata=gridsquare_metadata,
            )
        else:
            logging.info(f"Updating existing GridSquare: {gridsquare_id}")
            gridsquare_data = gridstore.gridsquares.get(gridsquare_id)
            gridsquare_data.metadata = gridsquare_metadata

        # Add the gridsquare to the grid's gridsquares EntityStore
        logging.info(f"Adding GridSquare {gridsquare_id} to Grid {grid_id}")
        gridstore.gridsquares.add(gridsquare_id, gridsquare_data)
        logging.info(f"Added GridSquare {gridsquare_id} to Grid {grid_id}")
        logging.info(gridsquare_data)

    def _on_gridsquare_manifest_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.info(f"Gridsquare manifest {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = re.search(EpuParser.gridsquare_dir_pattern, str(path)).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridstore = self.datastore.grids.get(grid_id)
        gridsquare_manifest = EpuParser.parse_gridsquare_manifest(path)

        if not gridstore.gridsquares.exists(gridsquare_id):
            gridsquare_data = GridSquareData(
                id=gridsquare_id,
                manifest=gridsquare_manifest,
            )
        else:
            gridsquare_data = gridstore.gridsquares.get(gridsquare_id)
            gridsquare_data.manifest = gridsquare_manifest

        gridstore.gridsquares.add(gridsquare_id, gridsquare_data)
        logging.info(gridsquare_data)

    def _on_foilhole_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.info(f"Foilhole {'detected' if is_new_file else 'updated'}: {path}")

        gridstore = self.datastore.grids.get(grid_id)
        data = EpuParser.parse_foilhole_manifest(path)

        # Here it is intentional that any previously recorded data for given foilhole is overwritten as
        # there are instances of multiple manifest files written to fs and in these cases
        # only the newest (by timestamp) is relevant.
        # TODO It is assumed that latest foilhole manifest by timestamp in filename will also be
        #  last to be written to fs, but additional filename-based checks wouldn't hurt - resolve latest
        #  based on timestamp found in filename.

        gridstore.foilholes.add(data.id, data)
        logging.info(data)

    def _on_micrograph_detected(self, path: str, grid_id, is_new_file: bool = True):
        logging.info(f"Micrograph {'detected' if is_new_file else 'updated'}: {path}")

        match = re.search(EpuParser.micrograph_xml_file_pattern, path)
        foilhole_id = match.group(1)
        location_id = match.group(2)

        gridstore = self.datastore.grids.get(grid_id)
        manifest = EpuParser.parse_micrograph_manifest(path)

        data = MicrographData(
            id=manifest.unique_id,
            location_id=location_id,
            gridsquare_id="",  # TODO
            high_res_path=Path(""),
            foilhole_id=foilhole_id,
            manifest_file=Path(path),
            manifest=manifest,
        )
        gridstore.micrographs.add(data.id, data)
        logging.info(data)

    def _on_session_complete(self):
        """
        TODO: explore how to reliably determine when session ended
            (and bear in mind that it could have been paused, to be resumed later)?
            Could Athena API be queried for this?
        """
        pass

    def _flush_events(self):
        if not self.changed_files:
            return

        batch_log = {"timestamp": datetime.now().isoformat(), "event_count": len(self.changed_files), "events": []}

        for src_path, (event, event_time, file_stat) in self.changed_files.items():
            event_data = {
                "timestamp": datetime.fromtimestamp(event_time).isoformat(),
                "event_type": event.event_type,
                "source_path": str(src_path),
                "relative_path": str(Path(src_path).relative_to(self.watch_dir)).replace("\\", "/"),
            }

            if file_stat:
                event_data.update(
                    {"size": file_stat.st_size, "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()}
                )

            if hasattr(event, "dest_path") and event.dest_path:
                event_data["destination_path"] = str(event.dest_path)
                try:
                    if os.path.exists(event.dest_path):
                        event_data["destination_size"] = os.path.getsize(event.dest_path)
                except OSError:
                    pass

            batch_log["events"].append(event_data)

        logging.info(batch_log)
        self.changed_files.clear()
        self.last_log_time = time.time()


if __name__ == "__main__":
    logging.warning("This module is not meant to be run directly. Import and use its components instead.")
    sys.exit(1)
