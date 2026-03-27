import logging
import threading
from datetime import UTC, datetime


class RemoteLogHandler(logging.Handler):
    def __init__(
        self,
        api_client,
        agent_id: str,
        session_id: str,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
    ):
        super().__init__(level=logging.INFO)
        self._api_client = api_client
        self._agent_id = agent_id
        self._session_id = session_id
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "level": record.levelname,
                "logger_name": record.name,
                "message": self.format(record) if self.formatter else record.getMessage(),
            }
            with self._lock:
                self._buffer.append(entry)
                if len(self._buffer) >= self._buffer_size:
                    self._flush_locked()
        except Exception:
            self.handleError(record)

    def _flush_locked(self):
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            self._api_client.send_logs(self._agent_id, self._session_id, batch)
        except Exception:
            pass

    def flush(self):
        with self._lock:
            self._flush_locked()

    def _flush_loop(self):
        while not self._stop_event.wait(self._flush_interval):
            self.flush()

    def close(self):
        self._stop_event.set()
        self._flush_thread.join(timeout=self._flush_interval + 1)
        self.flush()
        super().close()
