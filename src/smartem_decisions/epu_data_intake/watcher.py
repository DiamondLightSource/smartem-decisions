from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from collections import deque
from datetime import datetime
import logging
import sys
from pathlib import Path
import os


class RateLimitedHandler(FileSystemEventHandler):
    def __init__(self, log_interval=1.0):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.pending_events = deque()

    def on_any_event(self, event):
        if event.is_directory:
            return

        current_time = time.time()
        file_stat = None
        try:
            if os.path.exists(event.src_path):
                file_stat = os.stat(event.src_path)
        except (FileNotFoundError, PermissionError):
            pass

        self.pending_events.append((event, current_time, file_stat))

        if current_time - self.last_log_time >= self.log_interval:
            self._flush_events()

    def _flush_events(self):
        if not self.pending_events:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        logging.info(f"\n{timestamp} - {len(self.pending_events)} event(s) detected:")

        for event, event_time, file_stat in self.pending_events:
            event_timestamp = datetime.fromtimestamp(event_time).strftime('%H:%M:%S.%f')[:-3]
            size_info = f", size: {file_stat.st_size:,} bytes" if file_stat else ""
            mtime_info = f", modified: {datetime.fromtimestamp(file_stat.st_mtime).strftime('%H:%M:%S.%f')[:-3]}" if file_stat else ""

            logging.info(f"  [{event_timestamp}] {event.event_type}: {event.src_path}{size_info}{mtime_info}")
            if hasattr(event, 'dest_path'):
                dest_size = os.path.getsize(event.dest_path) if os.path.exists(event.dest_path) else None
                dest_size_info = f", size: {dest_size:,} bytes" if dest_size is not None else ""
                logging.info(f"    -> {event.dest_path}{dest_size_info}")

        self.pending_events.clear()
        self.last_log_time = time.time()


def watch_directory(path):
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler('fs_changes.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    path = Path(path).resolve()
    if not path.exists():
        raise ValueError(f"Directory {path} does not exist")

    observer = Observer()
    handler = RateLimitedHandler()
    observer.schedule(handler, str(path), recursive=True)

    logging.info(f"Starting to watch directory: {path} (including subdirectories)")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Watching stopped")

    observer.join()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <directory_to_watch>")
        sys.exit(1)

    watch_directory(sys.argv[1])