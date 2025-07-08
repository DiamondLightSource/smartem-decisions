#!/usr/bin/env python3
"""
Filesystem Recording and Replay Tool

Records all filesystem changes in a directory and can replay them elsewhere.
Cross-platform support for Windows and Linux with diff-based incremental recording.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    print("Installing required dependency: watchdog")
    os.system(f"{sys.executable} -m pip install watchdog")
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer


@dataclass
class FSEvent:
    timestamp: float
    event_type: str  # created, modified, deleted, moved, appended, truncated, patched
    src_path: str
    dest_path: str | None = None
    is_directory: bool = False
    content: str | None = None  # For small text files
    size: int | None = None
    # New fields for diff-based recording
    content_hash: str | None = None  # SHA256 hash for integrity
    binary_chunk_id: str | None = None  # Reference to binary chunk in tar
    operation_data: dict[str, Any] | None = None  # append_data, patch_info, etc.
    file_position: int | None = None  # For append/patch operations
    is_placeholder: bool = False  # True if this is a placeholder file


class FSRecorder(FileSystemEventHandler):
    def __init__(
        self,
        watch_dir: str,
        output_file: str,
        skip_binary_content: bool = True,
        force_text_extensions: list[str] = None,
        force_binary_extensions: list[str] = None,
    ):
        self.watch_dir = Path(watch_dir).resolve()
        self.output_file = Path(output_file)
        self.events: list[FSEvent] = []
        self.observer = Observer()
        self.running = False

        # Binary content handling settings
        self.skip_binary_content = skip_binary_content
        self.force_text_extensions = {ext.lower().lstrip(".") for ext in (force_text_extensions or [])}
        self.force_binary_extensions = {ext.lower().lstrip(".") for ext in (force_binary_extensions or [])}

        # Track file states for diff calculation
        self.file_states: dict[str, dict[str, Any]] = {}
        self.binary_chunks: dict[str, bytes] = {}
        self.chunk_counter = 0

        # Track unreadable files for reporting
        self.unreadable_files: list[str] = []

        # Track placeholder files for reporting
        self.placeholder_files: list[str] = []

        # Create temp directory for binary chunks
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fsrecorder_"))

        # Capture initial state
        self._capture_initial_state()

    def _normalize_path(self, path: Path) -> str:
        """Convert path to POSIX format for cross-platform compatibility"""
        return str(PurePosixPath(path))

    def _is_binary_file(self, file_path: Path) -> bool:
        """Determine if a file is binary or text based on content and extension overrides"""
        file_extension = file_path.suffix.lower().lstrip(".")

        # Check extension overrides first
        if file_extension in self.force_text_extensions:
            return False
        if file_extension in self.force_binary_extensions:
            return True

        # Common text file extensions
        text_extensions = {
            "txt",
            "md",
            "json",
            "xml",
            "html",
            "htm",
            "css",
            "js",
            "py",
            "java",
            "cpp",
            "c",
            "h",
            "hpp",
            "cs",
            "php",
            "rb",
            "go",
            "rs",
            "sh",
            "bat",
            "ps1",
            "yml",
            "yaml",
            "toml",
            "ini",
            "cfg",
            "conf",
            "log",
            "csv",
            "tsv",
            "sql",
            "r",
            "tex",
            "latex",
            "rtf",
            "dockerfile",
            "makefile",
            "gitignore",
            "gitattributes",
            "license",
            "readme",
            "dm",  # Add dm as text based on your use case
        }

        # Common binary file extensions
        binary_extensions = {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
            "tiff",
            "tif",
            "webp",
            "ico",
            "svg",
            "mp4",
            "avi",
            "mov",
            "wmv",
            "flv",
            "mkv",
            "webm",
            "mp3",
            "wav",
            "flac",
            "ogg",
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "zip",
            "rar",
            "7z",
            "tar",
            "gz",
            "bz2",
            "xz",
            "exe",
            "dll",
            "so",
            "dylib",
            "bin",
            "dat",
            "db",
            "sqlite",
            "mrc",  # Add mrc as binary based on your use case
        }

        if file_extension in text_extensions:
            return False
        if file_extension in binary_extensions:
            return True

        # For unknown extensions, try to detect by content
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)  # Read first 1KB
                if not chunk:
                    return False  # Empty file, treat as text

                # Check for null bytes (common in binary files)
                if b"\x00" in chunk:
                    return True

                # Check if content is mostly printable ASCII
                try:
                    chunk.decode("utf-8")
                    return False  # Successfully decoded as UTF-8, likely text
                except UnicodeDecodeError:
                    return True  # Cannot decode as UTF-8, likely binary
        except (PermissionError, OSError):
            # If we can't read the file, default to text
            return False

    def _should_use_placeholder(self, file_path: Path) -> bool:
        """Check if a file should be replaced with a placeholder"""
        if not self.skip_binary_content:
            return False
        return self._is_binary_file(file_path)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except (PermissionError, OSError) as e:
            print(f"Warning: Cannot read file {file_path}: {e}")
            # Track unreadable file for reporting
            self.unreadable_files.append(str(file_path))
            # Return a special hash to indicate the file couldn't be read
            return f"unreadable_{file_path.stat().st_size}_{file_path.stat().st_mtime}"

    def _store_binary_chunk(self, content: bytes) -> str:
        """Store binary content and return chunk ID"""
        chunk_id = f"chunk_{self.chunk_counter}"
        self.chunk_counter += 1

        chunk_file = self.temp_dir / f"{chunk_id}.bin"
        chunk_file.write_bytes(content)

        return chunk_id

    def _capture_initial_state(self):
        """Capture the initial state of the directory"""
        print(f"Capturing initial state of {self.watch_dir}")
        for root, _dirs, files in os.walk(self.watch_dir):
            root_path = Path(root)

            # Record directory creation
            if root_path != self.watch_dir:
                rel_path = root_path.relative_to(self.watch_dir)
                norm_path = self._normalize_path(rel_path)
                event = FSEvent(timestamp=time.time(), event_type="initial_dir", src_path=norm_path, is_directory=True)
                self.events.append(event)

            # Record file creation
            for file in files:
                file_path = root_path / file
                rel_path = file_path.relative_to(self.watch_dir)
                norm_path = self._normalize_path(rel_path)

                size = file_path.stat().st_size
                content_hash = self._calculate_file_hash(file_path)

                # Store initial file state
                self.file_states[norm_path] = {"size": size, "hash": content_hash, "content": None}

                content = None
                binary_chunk_id = None
                is_placeholder = self._should_use_placeholder(file_path)

                if is_placeholder:
                    # Create placeholder - store only size information
                    self.placeholder_files.append(str(file_path))
                    # Don't store any content for placeholders
                elif size < 1024 * 1024:  # 1MB limit for inline content
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        self.file_states[norm_path]["content"] = content
                    except Exception:
                        # Binary file or permission error - try to store as chunk
                        try:
                            binary_content = file_path.read_bytes()
                            binary_chunk_id = self._store_binary_chunk(binary_content)
                        except (PermissionError, OSError) as e:
                            print(f"Warning: Cannot read file content for {file_path}: {e}")
                            # Track unreadable file for reporting
                            self.unreadable_files.append(str(file_path))
                            # Skip storing content for unreadable files
                            pass
                else:
                    # Large file - store as chunk
                    try:
                        binary_content = file_path.read_bytes()
                        binary_chunk_id = self._store_binary_chunk(binary_content)
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Cannot read large file content for {file_path}: {e}")
                        # Track unreadable file for reporting
                        self.unreadable_files.append(str(file_path))
                        # Skip storing content for unreadable files
                        pass

                # Get file timestamps
                stat = file_path.stat()

                event = FSEvent(
                    timestamp=time.time(),
                    event_type="initial_file",
                    src_path=norm_path,
                    is_directory=False,
                    content=content,
                    size=size,
                    content_hash=content_hash,
                    binary_chunk_id=binary_chunk_id,
                    operation_data={"mtime": stat.st_mtime, "atime": stat.st_atime},
                    is_placeholder=is_placeholder,
                )
                self.events.append(event)

    def on_created(self, event: FileSystemEvent):
        self._record_event(event, "created")

    def on_modified(self, event: FileSystemEvent):
        self._record_event(event, "modified")

    def on_deleted(self, event: FileSystemEvent):
        self._record_event(event, "deleted")

    def on_moved(self, event: FileSystemEvent):
        src_rel = Path(event.src_path).relative_to(self.watch_dir)
        dest_rel = Path(event.dest_path).relative_to(self.watch_dir)

        src_norm = self._normalize_path(src_rel)
        dest_norm = self._normalize_path(dest_rel)

        # Update file state tracking
        if src_norm in self.file_states:
            self.file_states[dest_norm] = self.file_states.pop(src_norm)

        fs_event = FSEvent(
            timestamp=time.time(),
            event_type="moved",
            src_path=src_norm,
            dest_path=dest_norm,
            is_directory=event.is_directory,
        )
        self.events.append(fs_event)
        print(f"MOVED: {src_norm} -> {dest_norm}")

    def _record_event(self, event: FileSystemEvent, event_type: str):
        event_path = Path(event.src_path)
        rel_path = event_path.relative_to(self.watch_dir)
        norm_path = self._normalize_path(rel_path)

        if event.is_directory:
            # Handle directory events
            fs_event = FSEvent(
                timestamp=time.time(),
                event_type=event_type,
                src_path=norm_path,
                is_directory=True,
            )
            self.events.append(fs_event)
            print(f"{event_type.upper()}: {norm_path}")
            return

        # Handle file events with diff-based recording
        if event_type == "deleted":
            # Remove from state tracking
            self.file_states.pop(norm_path, None)
            fs_event = FSEvent(
                timestamp=time.time(),
                event_type=event_type,
                src_path=norm_path,
                is_directory=False,
            )
            self.events.append(fs_event)
            print(f"DELETED: {norm_path}")
            return

        if not event_path.exists():
            return

        # Get current file state
        current_size = event_path.stat().st_size
        current_hash = self._calculate_file_hash(event_path)

        # Check if this is a new file or modification
        if event_type == "created" or norm_path not in self.file_states:
            self._record_file_creation(event_path, norm_path, current_size, current_hash)
        else:
            self._record_file_modification(event_path, norm_path, current_size, current_hash)

    def _record_file_creation(self, file_path: Path, norm_path: str, size: int, content_hash: str):
        """Record file creation event"""
        content = None
        binary_chunk_id = None
        is_placeholder = self._should_use_placeholder(file_path)

        if is_placeholder:
            # Create placeholder - store only size information
            self.placeholder_files.append(str(file_path))
            # Don't store any content for placeholders
        elif size < 1024 * 1024:  # 1MB limit
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                try:
                    binary_content = file_path.read_bytes()
                    binary_chunk_id = self._store_binary_chunk(binary_content)
                except (PermissionError, OSError) as e:
                    print(f"Warning: Cannot read file content for {file_path}: {e}")
                    # Track unreadable file for reporting
                    self.unreadable_files.append(str(file_path))
                    # Skip storing content for unreadable files
                    pass
        else:
            try:
                binary_content = file_path.read_bytes()
                binary_chunk_id = self._store_binary_chunk(binary_content)
            except (PermissionError, OSError) as e:
                print(f"Warning: Cannot read large file content for {file_path}: {e}")
                # Track unreadable file for reporting
                self.unreadable_files.append(str(file_path))
                # Skip storing content for unreadable files
                pass

        # Update state tracking
        self.file_states[norm_path] = {"size": size, "hash": content_hash, "content": content}

        fs_event = FSEvent(
            timestamp=time.time(),
            event_type="created",
            src_path=norm_path,
            is_directory=False,
            content=content,
            size=size,
            content_hash=content_hash,
            binary_chunk_id=binary_chunk_id,
            is_placeholder=is_placeholder,
        )
        self.events.append(fs_event)
        print(f"CREATED: {norm_path}" + (" (binary placeholder)" if is_placeholder else ""))

    def _record_file_modification(self, file_path: Path, norm_path: str, current_size: int, current_hash: str):
        """Record file modification with diff-based approach"""
        old_state = self.file_states.get(norm_path, {})
        old_size = old_state.get("size", 0)
        old_hash = old_state.get("hash", "")

        # Skip if file hasn't actually changed
        if current_hash == old_hash:
            return

        # Determine modification type
        if current_size > old_size:
            # Likely an append operation
            self._record_append_operation(file_path, norm_path, old_size, current_size, current_hash)
        elif current_size < old_size:
            # File was truncated
            self._record_truncate_operation(file_path, norm_path, current_size, current_hash)
        else:
            # Same size but different content - full modification
            self._record_full_modification(file_path, norm_path, current_size, current_hash)

    def _record_append_operation(self, file_path: Path, norm_path: str, old_size: int, new_size: int, new_hash: str):
        """Record file append operation"""
        try:
            # Read only the appended content
            try:
                with open(file_path, "rb") as f:
                    f.seek(old_size)
                    appended_content = f.read(new_size - old_size)

                # Try to decode as text, otherwise store as binary
                append_data = None
                binary_chunk_id = None

                try:
                    append_data = appended_content.decode("utf-8")
                except Exception:
                    binary_chunk_id = self._store_binary_chunk(appended_content)
            except (PermissionError, OSError) as e:
                print(f"Warning: Cannot read appended content for {file_path}: {e}")
                # Track unreadable file for reporting
                self.unreadable_files.append(str(file_path))
                # Skip storing content for unreadable files
                append_data = None
                binary_chunk_id = None

            # Update state
            self.file_states[norm_path].update({"size": new_size, "hash": new_hash})

            fs_event = FSEvent(
                timestamp=time.time(),
                event_type="appended",
                src_path=norm_path,
                is_directory=False,
                content=append_data,
                size=new_size,
                content_hash=new_hash,
                binary_chunk_id=binary_chunk_id,
                file_position=old_size,
                operation_data={"append_size": new_size - old_size},
            )
            self.events.append(fs_event)
            print(f"APPENDED: {norm_path} (+{new_size - old_size} bytes)")

        except Exception as e:
            print(f"Error recording append for {norm_path}: {e}")
            self._record_full_modification(file_path, norm_path, new_size, new_hash)

    def _record_truncate_operation(self, file_path: Path, norm_path: str, new_size: int, new_hash: str):
        """Record file truncation operation"""
        # Update state
        self.file_states[norm_path].update({"size": new_size, "hash": new_hash})

        fs_event = FSEvent(
            timestamp=time.time(),
            event_type="truncated",
            src_path=norm_path,
            is_directory=False,
            size=new_size,
            content_hash=new_hash,
            operation_data={"new_size": new_size},
        )
        self.events.append(fs_event)
        print(f"TRUNCATED: {norm_path} to {new_size} bytes")

    def _record_full_modification(self, file_path: Path, norm_path: str, size: int, content_hash: str):
        """Record full file modification"""
        content = None
        binary_chunk_id = None
        is_placeholder = self._should_use_placeholder(file_path)

        if is_placeholder:
            # For placeholder files, just track the size change
            if str(file_path) not in self.placeholder_files:
                self.placeholder_files.append(str(file_path))
        elif size < 1024 * 1024:  # 1MB limit
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                self.file_states[norm_path]["content"] = content
            except Exception:
                try:
                    binary_content = file_path.read_bytes()
                    binary_chunk_id = self._store_binary_chunk(binary_content)
                except (PermissionError, OSError) as e:
                    print(f"Warning: Cannot read file content for {file_path}: {e}")
                    # Track unreadable file for reporting
                    self.unreadable_files.append(str(file_path))
                    # Skip storing content for unreadable files
                    pass
        else:
            try:
                binary_content = file_path.read_bytes()
                binary_chunk_id = self._store_binary_chunk(binary_content)
            except (PermissionError, OSError) as e:
                print(f"Warning: Cannot read large file content for {file_path}: {e}")
                # Track unreadable file for reporting
                self.unreadable_files.append(str(file_path))
                # Skip storing content for unreadable files
                pass

        # Update state
        self.file_states[norm_path].update({"size": size, "hash": content_hash})

        fs_event = FSEvent(
            timestamp=time.time(),
            event_type="modified",
            src_path=norm_path,
            is_directory=False,
            content=content,
            size=size,
            content_hash=content_hash,
            binary_chunk_id=binary_chunk_id,
            is_placeholder=is_placeholder,
        )
        self.events.append(fs_event)
        print(f"MODIFIED: {norm_path}" + (" (binary placeholder)" if is_placeholder else ""))

    def start_recording(self):
        """Start recording filesystem events"""
        print(f"Starting recording of {self.watch_dir}")
        print(f"Recording will be saved to {self.output_file}")
        print("Press Ctrl+C to stop recording")

        self.observer.schedule(self, str(self.watch_dir), recursive=True)
        self.observer.start()
        self.running = True

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_recording()

    def stop_recording(self):
        """Stop recording and save events with binary chunks"""
        print("\nStopping recording...")
        self.running = False
        self.observer.stop()
        self.observer.join()

        # Create tar.gz archive
        self._create_archive()

        # Cleanup temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

        print(f"Recording saved to {self.output_file}")
        print(f"Captured {len(self.events)} events")

        # Report unreadable files
        unique_unreadable = list(set(self.unreadable_files))
        if unique_unreadable:
            print(f"\nUnreadable files report ({len(unique_unreadable)} files):")
            for file_path in sorted(unique_unreadable):
                print(f"  - {file_path}")
            print(
                "\nNote: These files were tracked but their content could not be read due to permission restrictions."
            )
        else:
            print("\nAll files were readable during recording.")

        # Report placeholder files
        unique_placeholders = list(set(self.placeholder_files))
        if unique_placeholders:
            print(f"\nBinary placeholder files report ({len(unique_placeholders)} files):")
            for file_path in sorted(unique_placeholders):
                print(f"  - {file_path}")
            print("\nNote: These binary files were replaced with empty placeholders to reduce archive size.")

    def _create_archive(self):
        """Create tar.gz archive with recording and binary chunks"""
        print("\nPacking recording data...")

        # Prepare recording data
        events_data = [asdict(event) for event in self.events]
        recording = {
            "metadata": {
                "recorded_at": datetime.now().isoformat(),
                "watch_dir": str(self.watch_dir),
                "total_events": len(self.events),
                "version": "2.0",
                "platform": sys.platform,
            },
            "events": events_data,
        }

        # Create recording.json in temp directory
        print("Creating recording metadata...")
        recording_file = self.temp_dir / "recording.json"
        recording_file.write_text(json.dumps(recording, indent=2))

        # Create tar.gz archive
        print("Creating compressed archive...")
        chunk_count = len(list(self.temp_dir.glob("*.bin")))
        with tarfile.open(self.output_file, "w:gz") as tar:
            # Add recording.json
            tar.add(recording_file, arcname="recording.json")

            # Add all binary chunks
            if chunk_count > 0:
                print(f"Packing {chunk_count} binary chunks...")
            for chunk_file in self.temp_dir.glob("*.bin"):
                tar.add(chunk_file, arcname=f"chunks/{chunk_file.name}")

        print(f"✓ Archive created with {chunk_count} binary chunks")
        print(f"✓ Packing complete: {self.output_file}")


class FSReplayer:
    def __init__(self, recording_file: str, target_dir: str):
        self.recording_file = Path(recording_file)
        self.target_dir = Path(target_dir)
        self.events: list[FSEvent] = []
        self.chunks_dir: Path | None = None
        self.temp_dir: Path | None = None

        self._load_recording()

    def _load_recording(self):
        """Load recording from tar.gz archive or legacy JSON file"""
        if not self.recording_file.exists():
            raise FileNotFoundError(f"Recording file not found: {self.recording_file}")

        # Check if it's a tar.gz archive or legacy JSON
        if self.recording_file.suffix.lower() == ".gz" or tarfile.is_tarfile(self.recording_file):
            self._load_from_archive()
        else:
            self._load_from_json()

        print(f"Loaded recording with {len(self.events)} events")
        print(f"Recorded from: {self.metadata['watch_dir']}")
        print(f"Recorded at: {self.metadata['recorded_at']}")

    def _load_from_archive(self):
        """Load recording from tar.gz archive"""
        print("\nUnpacking recording archive...")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fsreplayer_"))

        print("Extracting archive contents...")
        with tarfile.open(self.recording_file, "r:gz") as tar:
            tar.extractall(self.temp_dir)

        # Load recording.json
        print("Loading recording metadata...")
        recording_file = self.temp_dir / "recording.json"
        if not recording_file.exists():
            raise ValueError("Invalid archive: missing recording.json")

        data = json.loads(recording_file.read_text())
        self.metadata = data["metadata"]

        # Set chunks directory
        self.chunks_dir = self.temp_dir / "chunks"

        # Count binary chunks
        chunk_count = len(list(self.chunks_dir.glob("*.bin"))) if self.chunks_dir.exists() else 0
        if chunk_count > 0:
            print(f"Found {chunk_count} binary chunks")

        print("Processing events...")
        for event_data in data["events"]:
            event = FSEvent(**event_data)
            self.events.append(event)

        print(f"✓ Unpacking complete: {len(self.events)} events loaded")

    def _load_from_json(self):
        """Load recording from legacy JSON file"""
        data = json.loads(self.recording_file.read_text())
        self.metadata = data["metadata"]

        for event_data in data["events"]:
            event = FSEvent(**event_data)
            self.events.append(event)

    def _normalize_target_path(self, src_path: str) -> Path:
        """Convert POSIX path to target platform path"""
        # Convert POSIX path to target platform
        posix_path = PurePosixPath(src_path)
        return self.target_dir / Path(*posix_path.parts)

    def _load_binary_chunk(self, chunk_id: str) -> bytes:
        """Load binary chunk content"""
        if not self.chunks_dir:
            raise ValueError("No chunks directory available")

        chunk_file = self.chunks_dir / f"{chunk_id}.bin"
        if not chunk_file.exists():
            raise FileNotFoundError(f"Binary chunk not found: {chunk_id}")

        return chunk_file.read_bytes()

    def _is_unreadable_file(self, event: FSEvent) -> bool:
        """Check if a file was unreadable during recording based on its hash format"""
        return event.content_hash and event.content_hash.startswith("unreadable_")

    def replay(
        self,
        speed_multiplier: float = 1.0,
        verify_integrity: bool = True,
        max_delay: float = None,
        burst_mode: bool = False,
        skip_unreadable: bool = False,
    ):
        """Replay the recording to target directory

        Args:
            speed_multiplier: Speed multiplier for timing (1.0 = exact timing)
            verify_integrity: Enable integrity verification
            max_delay: Maximum delay between events in seconds (None = no limit)
            burst_mode: If True, process events as fast as possible with minimal delays
            skip_unreadable: If True, skip creating files that were unreadable during recording
        """
        print(f"Replaying to {self.target_dir}")

        if burst_mode:
            print("Burst mode: Processing events as fast as possible")
        else:
            print(f"Speed multiplier: {speed_multiplier}x")
            if max_delay:
                print(f"Maximum delay capped at: {max_delay}s")

        # Create target directory
        self.target_dir.mkdir(parents=True, exist_ok=True)

        verification_errors = []
        skipped_unreadable_count = 0
        start_time = time.time()
        total_original_duration = 0

        if len(self.events) > 1:
            total_original_duration = self.events[-1].timestamp - self.events[0].timestamp

        try:
            for i, event in enumerate(self.events):
                # Calculate and apply delay
                if i > 0 and not burst_mode:
                    time_diff = event.timestamp - self.events[i - 1].timestamp
                    delay = time_diff / speed_multiplier

                    # Apply maximum delay cap if specified
                    if max_delay and delay > max_delay:
                        delay = max_delay

                    # Minimum delay to prevent overwhelming the system
                    if delay > 0.001:  # 1ms minimum
                        time.sleep(delay)
                elif burst_mode and i > 0:
                    # Minimal delay in burst mode to prevent system overload
                    time.sleep(0.001)

                was_skipped = self._replay_event(event, skip_unreadable=skip_unreadable)
                if was_skipped:
                    skipped_unreadable_count += 1

                # Verify integrity after certain operations
                if verify_integrity and event.content_hash and not event.is_directory:
                    # Skip verification for unreadable files
                    if not self._is_unreadable_file(event):
                        error = self._verify_file_integrity(event)
                        if error:
                            verification_errors.append(error)

                # Progress indicator with timing info
                if i % 50 == 0:  # Every 50 events for better performance
                    elapsed = time.time() - start_time
                    progress_pct = ((i + 1) / len(self.events)) * 100
                    print(f"Progress: {i + 1}/{len(self.events)} events ({progress_pct:.1f}%) - {elapsed:.1f}s elapsed")

            elapsed_total = time.time() - start_time
            print(f"\\nReplay completed in {elapsed_total:.1f}s!")

            if total_original_duration > 0:
                compression_ratio = total_original_duration / elapsed_total
                print(f"Time compression: {compression_ratio:.1f}x (original: {total_original_duration:.1f}s)")

            if skip_unreadable and skipped_unreadable_count > 0:
                print(f"\\nSkipped {skipped_unreadable_count} unreadable files during replay.")

            if verification_errors:
                print(f"\\nIntegrity verification found {len(verification_errors)} issues:")
                for error in verification_errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(verification_errors) > 5:
                    print(f"  ... and {len(verification_errors) - 5} more")
            else:
                print("\\nIntegrity verification passed!")

        finally:
            # Cleanup temp directory if created
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _verify_file_integrity(self, event: FSEvent) -> str | None:
        """Verify file integrity after replay"""
        if not event.content_hash:
            return None

        target_path = self._normalize_target_path(event.src_path)

        if not target_path.exists():
            return f"File missing after replay: {event.src_path}"

        try:
            actual_hash = self._calculate_file_hash(target_path)
            if actual_hash != event.content_hash:
                return (
                    f"Hash mismatch for {event.src_path}: "
                    f"expected {event.content_hash[:8]}..., got {actual_hash[:8]}..."
                )
        except Exception as e:
            return f"Error verifying {event.src_path}: {e}"

        return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except (PermissionError, OSError) as e:
            print(f"Warning: Cannot read file {file_path}: {e}")
            # Track unreadable file for reporting
            self.unreadable_files.append(str(file_path))
            # Return a special hash to indicate the file couldn't be read
            return f"unreadable_{file_path.stat().st_size}_{file_path.stat().st_mtime}"

    def _replay_event(self, event: FSEvent, skip_unreadable: bool = False):
        """Replay a single filesystem event"""
        target_path = self._normalize_target_path(event.src_path)

        # Skip unreadable files if requested
        if skip_unreadable and self._is_unreadable_file(event):
            print(f"Skipped unreadable file: {event.src_path}")
            return True

        try:
            if event.event_type in ["initial_dir", "created"] and event.is_directory:
                target_path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {event.src_path}")

            elif event.event_type in ["initial_file", "created"] and not event.is_directory:
                self._replay_file_creation(event, target_path)

            elif event.event_type == "modified" and not event.is_directory:
                self._replay_file_modification(event, target_path)

            elif event.event_type == "appended" and not event.is_directory:
                self._replay_file_append(event, target_path)

            elif event.event_type == "truncated" and not event.is_directory:
                self._replay_file_truncate(event, target_path)

            elif event.event_type == "deleted":
                if target_path.exists():
                    if event.is_directory:
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()
                    print(f"Deleted: {event.src_path}")

            elif event.event_type == "moved":
                dest_path = self._normalize_target_path(event.dest_path)
                if target_path.exists():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(target_path), str(dest_path))
                    print(f"Moved: {event.src_path} -> {event.dest_path}")

        except Exception as e:
            print(f"Error replaying event {event.event_type} for {event.src_path}: {e}")

        return False

    def _replay_file_creation(self, event: FSEvent, target_path: Path):
        """Replay file creation event"""
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if getattr(event, "is_placeholder", False):
            # Create empty placeholder file with correct size
            with open(target_path, "wb") as f:
                if event.size:
                    f.write(b"\0" * event.size)
            print(f"Created binary placeholder file: {event.src_path} ({event.size} bytes)")
        elif event.content is not None:
            # Text content
            target_path.write_text(event.content)
            print(f"Created file: {event.src_path}")
        elif event.binary_chunk_id:
            # Binary content from chunk
            binary_content = self._load_binary_chunk(event.binary_chunk_id)
            target_path.write_bytes(binary_content)
            print(f"Created file: {event.src_path}")
        else:
            # Create empty file with correct size
            with open(target_path, "wb") as f:
                if event.size:
                    f.write(b"\0" * event.size)
            print(f"Created file: {event.src_path}")

        # Set timestamps if available
        if event.operation_data and "mtime" in event.operation_data:
            try:
                mtime = event.operation_data["mtime"]
                atime = event.operation_data.get("atime", mtime)
                os.utime(target_path, (atime, mtime))
            except Exception as e:
                print(f"Warning: Could not set timestamps for {event.src_path}: {e}")

    def _replay_file_modification(self, event: FSEvent, target_path: Path):
        """Replay file modification event"""
        if not target_path.exists():
            print(f"Warning: Cannot modify non-existent file {event.src_path}")
            return

        if getattr(event, "is_placeholder", False):
            # For placeholder files, just update the size
            with open(target_path, "r+b") as f:
                f.truncate(event.size or 0)
                if event.size:
                    f.seek(0)
                    f.write(b"\0" * event.size)
            print(f"Modified binary placeholder file: {event.src_path} ({event.size} bytes)")
        elif event.content is not None:
            # Text content - full replacement
            target_path.write_text(event.content)
            print(f"Modified file: {event.src_path}")
        elif event.binary_chunk_id:
            # Binary content - full replacement
            binary_content = self._load_binary_chunk(event.binary_chunk_id)
            target_path.write_bytes(binary_content)
            print(f"Modified file: {event.src_path}")
        else:
            print(f"Modified file: {event.src_path}")

    def _replay_file_append(self, event: FSEvent, target_path: Path):
        """Replay file append operation"""
        if not target_path.exists():
            print(f"Warning: Cannot append to non-existent file {event.src_path}")
            return

        # Position to append location
        if event.file_position is not None:
            # Ensure file is the correct size before append
            current_size = target_path.stat().st_size
            if current_size != event.file_position:
                print(
                    f"Warning: File size mismatch for {event.src_path}. "
                    f"Expected {event.file_position}, got {current_size}"
                )

        if event.content is not None:
            # Text append
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(event.content)
        elif event.binary_chunk_id:
            # Binary append
            binary_content = self._load_binary_chunk(event.binary_chunk_id)
            with open(target_path, "ab") as f:
                f.write(binary_content)

        append_size = event.operation_data.get("append_size", 0) if event.operation_data else 0
        print(f"Appended to file: {event.src_path} (+{append_size} bytes)")

    def _replay_file_truncate(self, event: FSEvent, target_path: Path):
        """Replay file truncation operation"""
        if not target_path.exists():
            print(f"Warning: Cannot truncate non-existent file {event.src_path}")
            return

        new_size = event.operation_data.get("new_size", 0) if event.operation_data else 0

        with open(target_path, "r+b") as f:
            f.truncate(new_size)

        print(f"Truncated file: {event.src_path} to {new_size} bytes")


def main():
    parser = argparse.ArgumentParser(description="Filesystem Recording and Replay Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Record command
    record_parser = subparsers.add_parser("record", help="Record filesystem changes")
    record_parser.add_argument("directory", help="Directory to monitor")
    record_parser.add_argument("-o", "--output", required=True, help="Output recording file (.tar.gz)")
    record_parser.add_argument(
        "--skip-binary-content",
        action="store_true",
        default=True,
        help="Replace binary files with empty placeholders (default: True)",
    )
    record_parser.add_argument(
        "--no-skip-binary-content",
        action="store_false",
        dest="skip_binary_content",
        help="Store full content of binary files (overrides --skip-binary-content)",
    )
    record_parser.add_argument(
        "--force-text-extensions",
        nargs="*",
        default=[],
        help="File extensions to always treat as text (e.g., --force-text-extensions dm dat)",
    )
    record_parser.add_argument(
        "--force-binary-extensions",
        nargs="*",
        default=[],
        help="File extensions to always treat as binary (e.g., --force-binary-extensions log txt)",
    )

    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay filesystem changes")
    replay_parser.add_argument("recording", help="Recording file to replay (.tar.gz or legacy .json)")
    replay_parser.add_argument("target", help="Target directory for replay")
    replay_parser.add_argument(
        "-s",
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for custom mode (default behavior uses fast mode: 100x)",
    )
    replay_parser.add_argument("--max-delay", type=float, help="Maximum delay between events in seconds")
    replay_parser.add_argument("--burst", action="store_true", help="Burst mode: process events as fast as possible")
    replay_parser.add_argument(
        "--dev-mode",
        action="store_true",
        help=(
            "Maximum speed for rapid iteration and smoke tests (1000x + burst). "
            "Use for quick feedback loops, basic functionality testing, "
            "or when you just need the end result fast."
        ),
    )
    replay_parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Balanced acceleration for realistic testing (100x + 1s delays). DEFAULT mode. "
            "Use for timing-sensitive apps, integration testing, or when system stability matters."
        ),
    )
    replay_parser.add_argument(
        "--exact",
        action="store_true",
        help=(
            "Preserve original timing exactly (1x speed). "
            "Use when you need to reproduce exact timing behavior or debug timing-dependent issues."
        ),
    )
    replay_parser.add_argument("--no-verify", action="store_true", help="Skip integrity verification")
    replay_parser.add_argument(
        "--skip-unreadable", action="store_true", help="Skip creating files that were unreadable during recording"
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Show recording information")
    info_parser.add_argument("recording", help="Recording file to analyze (.tar.gz or legacy .json)")

    args = parser.parse_args()

    if args.command == "record":
        recorder = FSRecorder(
            args.directory,
            args.output,
            args.skip_binary_content,
            args.force_text_extensions,
            args.force_binary_extensions,
        )

        # Print binary content handling info
        if args.skip_binary_content:
            print("Binary content handling: Skip binary files (replace with placeholders)")
            if args.force_text_extensions:
                print(f"Force text extensions: {', '.join(args.force_text_extensions)}")
            if args.force_binary_extensions:
                print(f"Force binary extensions: {', '.join(args.force_binary_extensions)}")
        else:
            print("Binary content handling: Store full content of all files")

        # Handle Ctrl+C gracefully
        def signal_handler(sig, frame):
            recorder.stop_recording()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        recorder.start_recording()

    elif args.command == "replay":
        replayer = FSReplayer(args.recording, args.target)

        # Handle preset modes
        if args.dev_mode:
            print("Development mode: maximum acceleration for fast testing")
            replayer.replay(
                speed_multiplier=1000.0,
                verify_integrity=not args.no_verify,
                max_delay=0.1,
                burst_mode=True,
                skip_unreadable=args.skip_unreadable,
            )
        elif args.fast:
            print("Fast mode: 100x speed with reasonable delays")
            replayer.replay(
                speed_multiplier=100.0,
                verify_integrity=not args.no_verify,
                max_delay=1.0,
                burst_mode=False,
                skip_unreadable=args.skip_unreadable,
            )
        elif args.exact:
            print("Exact mode: preserving original timing")
            replayer.replay(
                speed_multiplier=1.0,
                verify_integrity=not args.no_verify,
                max_delay=None,
                burst_mode=False,
                skip_unreadable=args.skip_unreadable,
            )
        else:
            # Check if user specified custom settings
            has_custom_settings = args.speed != 1.0 or args.max_delay is not None or args.burst

            if has_custom_settings:
                # User specified custom settings - use them
                print(f"Custom mode: {args.speed}x speed")
                replayer.replay(
                    speed_multiplier=args.speed,
                    verify_integrity=not args.no_verify,
                    max_delay=args.max_delay,
                    burst_mode=args.burst,
                    skip_unreadable=args.skip_unreadable,
                )
            else:
                # No preset or custom settings specified - default to fast mode
                print("Fast mode (default): 100x speed with reasonable delays")
                replayer.replay(
                    speed_multiplier=100.0,
                    verify_integrity=not args.no_verify,
                    max_delay=1.0,
                    burst_mode=False,
                    skip_unreadable=args.skip_unreadable,
                )

    elif args.command == "info":
        if not Path(args.recording).exists():
            print(f"Recording file not found: {args.recording}")
            sys.exit(1)

        # Load recording data
        recording_path = Path(args.recording)

        if recording_path.suffix.lower() == ".gz" or tarfile.is_tarfile(recording_path):
            # Load from tar.gz archive
            with tempfile.TemporaryDirectory(prefix="fsinfo_") as temp_dir:
                temp_path = Path(temp_dir)
                with tarfile.open(recording_path, "r:gz") as tar:
                    tar.extractall(temp_path)

                recording_file = temp_path / "recording.json"
                if not recording_file.exists():
                    print("Invalid archive: missing recording.json")
                    sys.exit(1)

                data = json.loads(recording_file.read_text())

                # Count binary chunks
                chunks_dir = temp_path / "chunks"
                chunk_count = len(list(chunks_dir.glob("*.bin"))) if chunks_dir.exists() else 0
        else:
            # Legacy JSON format
            data = json.loads(recording_path.read_text())
            chunk_count = 0

        metadata = data["metadata"]
        events = data["events"]

        print("Recording Information:")
        print(f"  File: {args.recording}")
        print(f"  Recorded from: {metadata['watch_dir']}")
        print(f"  Recorded at: {metadata['recorded_at']}")
        print(f"  Total events: {metadata['total_events']}")
        print(f"  Format version: {metadata.get('version', '1.0')}")
        print(f"  Source platform: {metadata.get('platform', 'unknown')}")
        if chunk_count > 0:
            print(f"  Binary chunks: {chunk_count}")

        # Event type breakdown
        event_types = {}
        for event in events:
            event_type = event["event_type"]
            event_types[event_type] = event_types.get(event_type, 0) + 1

        print("  Event breakdown:")
        for event_type, count in sorted(event_types.items()):
            print(f"    {event_type}: {count}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
