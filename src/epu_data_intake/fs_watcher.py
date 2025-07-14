import logging
import os
import re
import sys
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from epu_data_intake.fs_parser import EpuParser
from epu_data_intake.model.schemas import GridData, GridSquareData, MicrographData, MicroscopeData
from epu_data_intake.model.store import InMemoryDataStore, PersistentDataStore

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
DEFAULT_PATTERNS = [
    # TODO consider merging with props in EpuParser
    # TODO (techdebt) This should be treated as immutable - don't modify!
    # Support both root-level files and files within acquisition subdirectories
    "EpuSession.dm",
    "*/EpuSession.dm",
    "Metadata/GridSquare_*.dm",
    "*/Metadata/GridSquare_*.dm",
    "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "*/Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
    "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "*/Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
    "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "*/Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
    "Sample*/Atlas/Atlas.dm",
    "*/Sample*/Atlas/Atlas.dm",
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
    datastore: InMemoryDataStore | None = None
    watch_dir: Path | None = None

    # TODO test with a lower log_interval value, set lowest possible default, better naming
    def __init__(
        self,
        watch_dir,
        dry_run: bool = False,
        api_url: str | None = None,
        log_interval: float = 10.0,
        patterns: list[str] | None = None,
    ):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.patterns = patterns if patterns is not None else DEFAULT_PATTERNS.copy()
        self.verbose = logging.getLogger().level <= logging.INFO
        # Distinguish between new and previously seen files.
        self.changed_files = {}

        # Maintain a buffer of "orphaned" files - files that appear to belong to a grid that doesn't exist yet
        self.orphaned_files = {}  # path -> (event, timestamp, file_stat)

        # Track extracted instrument information per grid to avoid conflicts and duplicates
        self._extracted_instruments = {}  # grid_uuid -> MicroscopeData

        # TODO on Win there's primary and secondary output dirs - work directly with primary if possible otherwise
        #  operate across both. Note: data is first written to primary output dir then later maybe partially copied
        #  to secondary dir.
        self.watch_dir = watch_dir.absolute()  # TODO this could cause problems in Win - test!

        if dry_run:
            self.datastore = InMemoryDataStore(str(self.watch_dir))
        else:
            self.datastore = PersistentDataStore(str(self.watch_dir), api_url)
        logging.debug(
            "Instantiated new datastore, "
            + ("in-memory only" if dry_run else f"data will be permanently saved to backend: {api_url}")
        )

    def _instruments_match(self, inst1: MicroscopeData, inst2: MicroscopeData) -> bool:
        """Check if two instrument records are equivalent."""
        return (
            inst1.instrument_model == inst2.instrument_model
            and inst1.instrument_id == inst2.instrument_id
            and inst1.computer_name == inst2.computer_name
        )

    def _try_extract_instrument_info(self, file_path: str, grid_uuid: str) -> None:
        """
        Try to extract instrument info from any XML file and store it at the acquisition level.

        This method:
        1. Attempts to extract instrument information from the given XML file
        2. Stores it once per grid (acquisition) to avoid duplicates
        3. Detects and logs conflicts if different instrument info is found for the same grid
        4. Updates the acquisition record when instrument info is found

        Args:
            file_path: Path to the XML file to parse
            grid_uuid: UUID of the grid this file belongs to
        """
        if grid_uuid in self._extracted_instruments:
            return  # Already have instrument info for this grid

        try:
            instrument = EpuParser.parse_microscope_from_image_metadata(file_path)
            if instrument:
                if grid_uuid in self._extracted_instruments:
                    # Check for mismatch (double-check in case of race conditions)
                    existing = self._extracted_instruments[grid_uuid]
                    if not self._instruments_match(existing, instrument):
                        logging.error(
                            f"Instrument mismatch in grid {grid_uuid}: "
                            f"existing=Model:{existing.instrument_model}/ID:{existing.instrument_id} vs "
                            f"new=Model:{instrument.instrument_model}/ID:{instrument.instrument_id}"
                        )
                        return
                    logging.debug(f"Instrument info already extracted for grid {grid_uuid}, skipping duplicate")
                else:
                    # Store instrument info for this grid
                    self._extracted_instruments[grid_uuid] = instrument
                    logging.info(
                        f"Extracted instrument info from {Path(file_path).name}: "
                        f"Model={instrument.instrument_model}, ID={instrument.instrument_id}"
                    )

                    # Update acquisition record in the datastore
                    grid = self.datastore.get_grid(grid_uuid)
                    if grid and grid.acquisition_data:
                        grid.acquisition_data.instrument = instrument
                        self.datastore.update_grid(grid)

                        # Update acquisition via API if using PersistentDataStore
                        if hasattr(self.datastore, "api_client"):
                            try:
                                self.datastore.api_client.update_acquisition(grid.acquisition_data)
                                logging.info(
                                    f"Updated acquisition {grid.acquisition_data.id} via API "
                                    f"with instrument information"
                                )
                            except Exception as e:
                                logging.error(f"Failed to update acquisition {grid.acquisition_data.id} via API: {e}")

                        logging.info(f"Updated acquisition {grid.acquisition_data.id} with instrument information")
                    else:
                        logging.warning(f"Could not update acquisition record for grid {grid_uuid}")

        except Exception as e:
            logging.debug(f"Could not extract instrument info from {file_path}: {e}")

    # TODO unit test this method
    def matches_pattern(self, path: str) -> bool:
        try:
            rel_path = str(Path(path).relative_to(self.watch_dir))
            rel_path = rel_path.replace("\\", "/")  # Normalize path separators
            return any(fnmatch(rel_path, pattern) for pattern in self.patterns)
        except ValueError:
            return False

    # TODO Enhancement: log all events for session debugging and playback
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
            logging.warning(f"Error accessing file {event.src_path}: {str(e)}")
            return  # Skip processing this file if we can't access it

        new_file_detected = event.src_path not in self.changed_files
        self.changed_files[event.src_path] = (event, current_time, file_stat)

        # Skip processing if this is a duplicate event for the same file
        if not new_file_detected:
            return

        # New grid discovered? If so - instantiate in store
        if re.search(EpuParser.session_dm_pattern, event.src_path):
            assert self.datastore.get_grid_by_path(event.src_path) is None  # guaranteed because is a new file
            grid = GridData(data_dir=Path(event.src_path).parent.resolve())
            grid.acquisition_data = EpuParser.parse_epu_session_manifest(event.src_path)
            self.datastore.create_grid(grid)

        # try to work out which grid the touched file relates to
        grid_uuid = self.datastore.get_grid_by_path(event.src_path)
        if grid_uuid is None:
            # This must be an orphaned file since it matched one of patterns for files we are interested in,
            #   but a containing grid doesn't exist yet - store it for when we have the grid.
            logging.debug(f"Could not determine which grid this data belongs to: {event.src_path}, adding to orphans")
            self.orphaned_files[event.src_path] = (event, current_time, file_stat)
            return

        match event.src_path:
            case path if re.search(EpuParser.session_dm_pattern, path):
                self._on_acquisition_detected(path, grid_uuid, new_file_detected)
                # After processing the session file, check for any orphaned files belonging to this grid
                self._process_orphaned_files(grid_uuid)
            case path if re.search(EpuParser.atlas_dm_pattern, path):
                self._on_atlas_detected(path, grid_uuid, new_file_detected)
            case path if re.search(EpuParser.gridsquare_dm_file_pattern, path):
                self._on_gridsquare_metadata_detected(path, grid_uuid, new_file_detected)
            case path if re.search(EpuParser.gridsquare_xml_file_pattern, path):
                self._on_gridsquare_manifest_detected(path, grid_uuid, new_file_detected)
            case path if re.search(EpuParser.foilhole_xml_file_pattern, path):
                self._on_foilhole_detected(path, grid_uuid, new_file_detected)
            case path if re.search(EpuParser.micrograph_xml_file_pattern, path):
                self._on_micrograph_detected(path, grid_uuid, new_file_detected)

        # Try to extract instrument information from any XML file (GridSquare, FoilHole, Micrograph XMLs)
        # This is done opportunistically - we'll get instrument info from whichever file contains it first
        if event.src_path.endswith(".xml") and grid_uuid:
            self._try_extract_instrument_info(event.src_path, grid_uuid)

    def _on_acquisition_detected(self, path: str, grid_uuid: str, is_new_file: bool = True):
        logging.debug(f"Session manifest {'detected' if is_new_file else 'updated'}: {path}")
        acquisition_data = EpuParser.parse_epu_session_manifest(path)
        grid = self.datastore.get_grid(grid_uuid)

        if grid and acquisition_data != grid.acquisition_date:
            grid.acquisition_data = acquisition_data
            self.datastore.update_grid(grid)
            logging.debug(f"Updated acquisition_data for grid: {grid_uuid}")

    def _process_orphaned_files(self, grid_uuid: str):
        """Process any orphaned files that belong to this grid"""
        for path, (event, _timestamp, _file_stat) in self.orphaned_files.items():
            # Check if this orphaned file belongs to the new grid
            if self.datastore.get_grid_by_path(path) == grid_uuid:
                logging.debug(f"Processing previously orphaned file: {path}")
                self.on_any_event(event)  # Process the file as if we just received the event

        # Create a new dictionary excluding the processed files
        self.orphaned_files = {
            path: data
            for path, data in self.orphaned_files.items()
            if self.datastore.get_grid_by_path(path) != grid_uuid
        }

    def _on_atlas_detected(self, path: str, grid_uuid: str, is_new_file: bool = True):
        logging.debug(f"Atlas {'detected' if is_new_file else 'updated'}: {path}")
        atlas_data = EpuParser.parse_atlas_manifest(path)
        grid = self.datastore.get_grid(grid_uuid)
        if atlas_data != grid.atlas_data:
            grid.atlas_data = atlas_data
            self.datastore.update_grid(grid)
            logging.debug(f"Updated atlas_data for grid: {grid_uuid}")
            for gsid, gsp in grid.atlas_data.gridsquare_positions.items():
                gridsquare = GridSquareData(
                    gridsquare_id=str(gsid),
                    metadata=None,
                    grid_uuid=grid.uuid,
                    center_x=gsp.center[0],
                    center_y=gsp.center[1],
                    size_width=gsp.size[0],
                    size_height=gsp.size[1],
                )
                # need to check if each square exists already
                if found_grid_square := self.datastore.find_gridsquare_by_natural_id(str(gsid)):
                    gridsquare.uuid = found_grid_square.uuid
                    self.datastore.update_gridsquare(gridsquare)
                else:
                    self.datastore.create_gridsquare(gridsquare)
            logging.debug(f"Registered all squares for grid: {grid_uuid}")

    def _on_gridsquare_metadata_detected(self, path: str, grid_uuid: str, is_new_file: bool = True):
        logging.info(f"Gridsquare metadata {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = EpuParser.gridsquare_dm_file_pattern.search(path).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridsquare_metadata = EpuParser.parse_gridsquare_metadata(path)
        grid = self.datastore.get_grid(grid_uuid)

        # Check if this is a new gridsquare or an update to an existing one
        gridsquare = self.datastore.find_gridsquare_by_natural_id(gridsquare_id)
        if not gridsquare:
            gridsquare = GridSquareData(
                gridsquare_id=gridsquare_id,
                metadata=gridsquare_metadata,
                grid_uuid=grid.uuid,
            )
            logging.info(f"Creating new GridSquare: {gridsquare.uuid} of Grid {grid.uuid}")
            self.datastore.create_gridsquare(gridsquare)
        else:
            logging.info(f"Updating existing GridSquare: {gridsquare_id} of Grid {grid.uuid}")
            gridsquare.metadata = gridsquare_metadata
            self.datastore.update_gridsquare(gridsquare)

    def _on_gridsquare_manifest_detected(self, path: str, grid_uuid, is_new_file: bool = True):
        logging.info(f"Gridsquare manifest {'detected' if is_new_file else 'updated'}: {path}")

        gridsquare_id = re.search(EpuParser.gridsquare_dir_pattern, str(path)).group(1)
        assert gridsquare_id is not None, f"gridsquare_id should not be None: {gridsquare_id}"

        gridsquare_manifest = EpuParser.parse_gridsquare_manifest(path)
        grid = self.datastore.get_grid(grid_uuid)

        # Check if this is a new gridsquare or an update to an existing one
        gridsquare = self.datastore.find_gridsquare_by_natural_id(gridsquare_id)
        if not gridsquare:
            gridsquare = GridSquareData(
                gridsquare_id=gridsquare_id,
                manifest=gridsquare_manifest,
                grid_uuid=grid.uuid,
            )
            logging.info(
                f"Creating new GridSquare: {gridsquare.uuid} (ID: {gridsquare_id}) of Grid {gridsquare.grid_uuid}"
            )
            self.datastore.create_gridsquare(gridsquare)
            logging.info(f"GridSquare {gridsquare.uuid} created successfully")
        else:
            logging.info(
                f"Updating existing GridSquare: {gridsquare.uuid} (ID: {gridsquare_id}) of Grid {gridsquare.grid_uuid}"
            )
            gridsquare.manifest = gridsquare_manifest
            self.datastore.update_gridsquare(gridsquare)
            logging.info(f"GridSquare {gridsquare.uuid} updated successfully")

        logging.debug(gridsquare)

    def _on_foilhole_detected(self, path: str, grid_uuid: str, is_new_file: bool = True):
        logging.info(f"Foilhole {'detected' if is_new_file else 'updated'}: {path}")
        foilhole = EpuParser.parse_foilhole_manifest(path)

        # Here it is intentional that any previously recorded data for given foilhole is overwritten as
        # there are instances of multiple manifest files written to fs and in these cases
        # only the newest (by timestamp) is relevant.
        # TODO It is assumed that latest foilhole manifest by timestamp in filename will also be
        #  last to be written to fs, but additional filename-based checks wouldn't hurt - resolve latest
        #  based on timestamp found in filename.

        # Use upsert method which handles all UUID management and race conditions internally
        success = self.datastore.upsert_foilhole(foilhole)
        if not success:
            logging.warning(
                f"Parent gridsquare {foilhole.gridsquare_uuid} not found for foilhole {foilhole.id}. "
                f"This may be a race condition. Available gridsquares: {list(self.datastore.gridsquares.keys())}. "
                f"Skipping foilhole creation."
            )
            return

        logging.info(
            f"Successfully upserted foilhole {foilhole.id} (UUID: {foilhole.uuid}) "
            f"for gridsquare {foilhole.gridsquare_uuid}"
        )
        logging.debug(foilhole)

    def _on_micrograph_detected(self, path: str, grid_uuid: str, is_new_file: bool = True):
        logging.info(f"Micrograph {'detected' if is_new_file else 'updated'}: {path}")

        match = re.search(EpuParser.micrograph_xml_file_pattern, path)
        foilhole_id = match.group(1)
        location_id = match.group(2)

        micrograph_manifest = EpuParser.parse_micrograph_manifest(path)
        foilholes = [fh for fh in self.datastore.foilholes.values() if fh.id == foilhole_id]
        gridsquare_id = foilholes[0].gridsquare_id if foilholes else ""
        foilhole = self.datastore.find_foilhole_by_natural_id(foilhole_id)
        if not foilhole:
            logging.warning(
                f"Could not find foilhole by natural ID {foilhole_id}, "
                f"skipping micrograph creation for micrograph {micrograph_manifest.unique_id}"
            )
            return

        micrograph = MicrographData(
            id=micrograph_manifest.unique_id,
            foilhole_uuid=foilhole.uuid,
            foilhole_id=foilhole_id,
            location_id=location_id,
            gridsquare_id=gridsquare_id,
            high_res_path=Path(""),
            manifest_file=Path(path),
            manifest=micrograph_manifest,
        )
        success = self.datastore.upsert_micrograph(micrograph)
        if not success:
            logging.warning(f"Failed to upsert micrograph {micrograph.id}")

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
