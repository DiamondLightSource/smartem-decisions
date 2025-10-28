import time
from collections import deque
from dataclasses import dataclass

from smartem_common.utils import get_logger

logger = get_logger(__name__)


@dataclass
class MetricsSample:
    timestamp: float
    value: float


class ProcessingMetrics:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._latencies: deque[MetricsSample] = deque(maxlen=window_size)
        self._retry_counts: dict[str, int] = {}
        self._success_count = 0
        self._failure_count = 0
        self._start_time = time.time()

    def record_latency(self, latency_ms: float) -> None:
        self._latencies.append(MetricsSample(timestamp=time.time(), value=latency_ms))

    def record_success(self) -> None:
        self._success_count += 1

    def record_failure(self) -> None:
        self._failure_count += 1

    def record_retry(self, category: str) -> None:
        self._retry_counts[category] = self._retry_counts.get(category, 0) + 1

    def get_latency_percentiles(self) -> dict[str, float]:
        if not self._latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "max": 0.0}

        sorted_latencies = sorted(sample.value for sample in self._latencies)
        count = len(sorted_latencies)

        def percentile(p: float) -> float:
            index = int(count * p)
            if index >= count:
                index = count - 1
            return sorted_latencies[index]

        return {
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
            "mean": sum(sorted_latencies) / count,
            "max": sorted_latencies[-1],
        }

    def get_retry_distribution(self) -> dict[str, int]:
        return dict(self._retry_counts)

    def get_throughput(self) -> float:
        elapsed = time.time() - self._start_time
        if elapsed == 0:
            return 0.0
        return (self._success_count + self._failure_count) / elapsed

    def get_success_rate(self) -> float:
        total = self._success_count + self._failure_count
        if total == 0:
            return 0.0
        return self._success_count / total

    def get_summary(self) -> dict:
        return {
            "latency_percentiles": self.get_latency_percentiles(),
            "retry_distribution": self.get_retry_distribution(),
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": self.get_success_rate(),
            "throughput_per_second": self.get_throughput(),
            "uptime_seconds": time.time() - self._start_time,
        }

    def clear(self) -> None:
        self._latencies.clear()
        self._retry_counts.clear()
        self._success_count = 0
        self._failure_count = 0
        self._start_time = time.time()
