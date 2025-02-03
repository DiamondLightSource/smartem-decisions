from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from collections import deque
from datetime import datetime
import logging
import sys
from pathlib import Path
import os
import json
from fnmatch import fnmatch


class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, indent=2)
        return json.dumps({
            "message": record.msg,
            "level": record.levelname,
            "timestamp": datetime.now().isoformat()
        }, indent=2)


class RateLimitedHandler(FileSystemEventHandler):
    def __init__(self, patterns, log_interval=1.0):
        self.last_log_time = time.time()
        self.log_interval = log_interval
        self.pending_events = deque()
        self.patterns = patterns

    def matches_pattern(self, path):
        rel_path = str(Path(path).relative_to(self.watch_dir))
        return any(fnmatch(rel_path, pattern) for pattern in self.patterns)

    def on_any_event(self, event):
        if event.is_directory:
            return

        if not self.matches_pattern(event.src_path):
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

    def set_watch_dir(self, path):
        self.watch_dir = Path(path)

    def _flush_events(self):
        if not self.pending_events:
            return

        batch_log = {
            "timestamp": datetime.now().isoformat(),
            "event_count": len(self.pending_events),
            "events": []
        }

        for event, event_time, file_stat in self.pending_events:
            event_data = {
                "timestamp": datetime.fromtimestamp(event_time).isoformat(),
                "event_type": event.event_type,
                "source_path": event.src_path,
                "relative_path": str(Path(event.src_path).relative_to(self.watch_dir))
            }

            if file_stat:
                event_data.update({
                    "size": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })

            if hasattr(event, 'dest_path'):
                event_data["destination_path"] = event.dest_path
                if os.path.exists(event.dest_path):
                    event_data["destination_size"] = os.path.getsize(event.dest_path)

            batch_log["events"].append(event_data)

        logging.info(batch_log)
        self.pending_events.clear()
        self.last_log_time = time.time()


def watch_directory(path, patterns):
    json_formatter = JSONFormatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler('fs_changes.log')
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    path = Path(path).resolve()
    if not path.exists():
        raise ValueError(f"Directory {path} does not exist")

    logging.info({
        "message": f"Starting to watch directory: {str(path)} (including subdirectories)",
        "path": str(path),
        "patterns": patterns,
        "timestamp": datetime.now().isoformat()
    })

    observer = Observer()
    handler = RateLimitedHandler(patterns)
    handler.set_watch_dir(path)
    observer.schedule(handler, str(path), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info({
            "message": "Watching stopped",
            "timestamp": datetime.now().isoformat()
        })

    observer.join()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <directory_to_watch>")
        sys.exit(1)

    patterns = [
        "EpuSession.dm",
        "Metadata/GridSquare_*.dm",
        "Images-Disc*/GridSquare_*/GridSquare_*_*.xml",
        "Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml",
        "Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml",
        "Sample*/Atlas/Atlas.dm",
        "Sample*/Sample.dm",
    ]

    watch_directory(sys.argv[1], patterns)