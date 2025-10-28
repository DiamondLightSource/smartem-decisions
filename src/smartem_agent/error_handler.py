import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from smartem_common.utils import get_logger

logger = get_logger(__name__)


class ErrorCategory(Enum):
    TRANSIENT_PARSER = "transient_parser"
    TRANSIENT_API = "transient_api"
    PERMANENT_CORRUPT = "permanent_corrupt"
    PERMANENT_MISSING = "permanent_missing"
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    file_path: Path
    category: ErrorCategory
    error_message: str
    first_seen: float
    retry_count: int = 0
    last_retry: float | None = None


class ErrorHandler:
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._errors: dict[Path, ErrorRecord] = {}
        self._error_counts: dict[ErrorCategory, int] = dict.fromkeys(ErrorCategory, 0)

    def categorize_error(self, error: Exception, file_path: Path) -> ErrorCategory:
        error_str = str(error).lower()

        if "permission denied" in error_str or "access denied" in error_str:
            return ErrorCategory.TRANSIENT_PARSER
        if "file not found" in error_str or "no such file" in error_str:
            return ErrorCategory.PERMANENT_MISSING
        if "parse" in error_str or "xml" in error_str or "malformed" in error_str:
            return ErrorCategory.TRANSIENT_PARSER
        if "connection" in error_str or "timeout" in error_str or "refused" in error_str:
            return ErrorCategory.TRANSIENT_API
        if "http" in error_str or "api" in error_str or "request" in error_str:
            return ErrorCategory.TRANSIENT_API
        if "corrupt" in error_str or "invalid" in error_str:
            return ErrorCategory.PERMANENT_CORRUPT

        return ErrorCategory.UNKNOWN

    def should_retry(self, error: Exception, file_path: Path) -> bool:
        category = self.categorize_error(error, file_path)

        if category in {
            ErrorCategory.PERMANENT_CORRUPT,
            ErrorCategory.PERMANENT_MISSING,
        }:
            return False

        if file_path in self._errors:
            record = self._errors[file_path]
            if record.retry_count >= self.max_retries:
                logger.error(
                    f"Max retries ({self.max_retries}) exceeded for {file_path.name}, "
                    f"category: {category.value}, error: {error}"
                )
                return False
        else:
            self._errors[file_path] = ErrorRecord(
                file_path=file_path,
                category=category,
                error_message=str(error),
                first_seen=time.time(),
            )

        return True

    def calculate_backoff_delay(self, file_path: Path) -> float:
        if file_path not in self._errors:
            return self.base_delay

        record = self._errors[file_path]
        delay = self.base_delay * (2**record.retry_count)
        return min(delay, self.max_delay)

    def record_retry(self, file_path: Path) -> None:
        if file_path in self._errors:
            record = self._errors[file_path]
            record.retry_count += 1
            record.last_retry = time.time()
            logger.info(
                f"Retry attempt {record.retry_count}/{self.max_retries} for {file_path.name}, "
                f"category: {record.category.value}, "
                f"next backoff: {self.calculate_backoff_delay(file_path):.1f}s"
            )

    def record_success(self, file_path: Path) -> None:
        if file_path in self._errors:
            record = self._errors.pop(file_path)
            logger.info(
                f"Successful retry for {file_path.name} after {record.retry_count} attempts, "
                f"category: {record.category.value}"
            )

    def record_permanent_failure(self, error: Exception, file_path: Path) -> None:
        category = self.categorize_error(error, file_path)
        self._error_counts[category] += 1

        logger.error(f"Permanent failure: {file_path.name}, category: {category.value}, error: {error}")

        if file_path in self._errors:
            del self._errors[file_path]

    def get_error_stats(self) -> dict:
        return {
            "active_errors": len(self._errors),
            "error_counts": {category.value: count for category, count in self._error_counts.items()},
            "errors_by_category": {
                category.value: sum(1 for e in self._errors.values() if e.category == category)
                for category in ErrorCategory
            },
        }

    def clear(self) -> None:
        self._errors.clear()
        self._error_counts = dict.fromkeys(ErrorCategory, 0)
