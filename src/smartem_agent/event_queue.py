import heapq
import threading

from smartem_agent.event_classifier import ClassifiedEvent
from smartem_common.utils import get_logger

logger = get_logger(__name__)


class EventQueue:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: list[ClassifiedEvent] = []
        self._lock = threading.Lock()
        self._evicted_count = 0
        self._evicted_events: list[ClassifiedEvent] = []
        self._evicted_recovery_enabled = True

    def enqueue(self, event: ClassifiedEvent) -> None:
        with self._lock:
            if len(self._queue) >= self.max_size:
                evicted = heapq.heappop(self._queue)
                self._evicted_count += 1
                if self._evicted_recovery_enabled:
                    self._evicted_events.append(evicted)
                logger.warning(
                    f"Event queue full (size={self.max_size}), evicted event: "
                    f"{evicted.entity_type.value} {evicted.file_path.name} "
                    f"(total evicted: {self._evicted_count})"
                )

            heapq.heappush(self._queue, event)

    def dequeue_batch(self, max_size: int = 50) -> list[ClassifiedEvent]:
        with self._lock:
            batch_size = min(max_size, len(self._queue))
            batch = [heapq.heappop(self._queue) for _ in range(batch_size)]
            return batch

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()
            self._evicted_count = 0

    def get_evicted_count(self) -> int:
        return self._evicted_count

    def recover_evicted_events(self) -> int:
        with self._lock:
            recovered = 0
            for event in self._evicted_events:
                if len(self._queue) < self.max_size:
                    heapq.heappush(self._queue, event)
                    recovered += 1
            self._evicted_events = self._evicted_events[recovered:]
            if recovered > 0:
                logger.info(f"Recovered {recovered} evicted events back into queue")
            return recovered
