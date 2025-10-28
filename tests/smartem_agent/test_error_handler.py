import pytest

from smartem_agent.error_handler import ErrorCategory, ErrorHandler


class TestErrorHandler:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler(max_retries=3, base_delay=0.1, max_delay=1.0)

    @pytest.fixture
    def sample_file_path(self, tmp_path):
        return tmp_path / "test_file.xml"

    def test_initialization(self, error_handler):
        assert error_handler.max_retries == 3
        assert error_handler.base_delay == 0.1
        assert error_handler.max_delay == 1.0
        assert len(error_handler._errors) == 0

    def test_categorize_error_permission_denied(self, error_handler, sample_file_path):
        error = PermissionError("Permission denied: /path/to/file")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.TRANSIENT_PARSER

    def test_categorize_error_file_not_found(self, error_handler, sample_file_path):
        error = FileNotFoundError("File not found: /path/to/file")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.PERMANENT_MISSING

    def test_categorize_error_parse_error(self, error_handler, sample_file_path):
        error = ValueError("XML parse error: malformed data")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.TRANSIENT_PARSER

    def test_categorize_error_connection_error(self, error_handler, sample_file_path):
        error = ConnectionError("Connection refused")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.TRANSIENT_API

    def test_categorize_error_timeout(self, error_handler, sample_file_path):
        error = TimeoutError("Request timeout")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.TRANSIENT_API

    def test_categorize_error_corrupt_data(self, error_handler, sample_file_path):
        error = ValueError("Corrupt data detected")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.PERMANENT_CORRUPT

    def test_categorize_error_unknown(self, error_handler, sample_file_path):
        error = RuntimeError("Something unexpected happened")
        category = error_handler.categorize_error(error, sample_file_path)
        assert category == ErrorCategory.UNKNOWN

    def test_should_retry_permanent_missing(self, error_handler, sample_file_path):
        error = FileNotFoundError("File not found")
        should_retry = error_handler.should_retry(error, sample_file_path)
        assert not should_retry

    def test_should_retry_permanent_corrupt(self, error_handler, sample_file_path):
        error = ValueError("Corrupt data")
        should_retry = error_handler.should_retry(error, sample_file_path)
        assert not should_retry

    def test_should_retry_transient_first_attempt(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        should_retry = error_handler.should_retry(error, sample_file_path)
        assert should_retry

    def test_should_retry_max_retries_exceeded(self, error_handler, sample_file_path):
        error = ValueError("Parse error")

        for _ in range(3):
            assert error_handler.should_retry(error, sample_file_path)
            error_handler.record_retry(sample_file_path)

        should_retry = error_handler.should_retry(error, sample_file_path)
        assert not should_retry

    def test_calculate_backoff_delay_first_retry(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)

        delay = error_handler.calculate_backoff_delay(sample_file_path)
        assert delay == 0.1

    def test_calculate_backoff_delay_exponential(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)

        error_handler.record_retry(sample_file_path)
        delay1 = error_handler.calculate_backoff_delay(sample_file_path)
        assert delay1 == 0.2

        error_handler.record_retry(sample_file_path)
        delay2 = error_handler.calculate_backoff_delay(sample_file_path)
        assert delay2 == 0.4

        error_handler.record_retry(sample_file_path)
        delay3 = error_handler.calculate_backoff_delay(sample_file_path)
        assert delay3 == 0.8

    def test_calculate_backoff_delay_max_cap(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)

        for _ in range(10):
            error_handler.record_retry(sample_file_path)

        delay = error_handler.calculate_backoff_delay(sample_file_path)
        assert delay == 1.0

    def test_record_success_removes_error(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)
        error_handler.record_retry(sample_file_path)

        assert sample_file_path in error_handler._errors

        error_handler.record_success(sample_file_path)

        assert sample_file_path not in error_handler._errors

    def test_record_permanent_failure(self, error_handler, sample_file_path):
        error = ValueError("Corrupt data")
        error_handler.record_permanent_failure(error, sample_file_path)

        stats = error_handler.get_error_stats()
        assert stats["error_counts"]["permanent_corrupt"] == 1

    def test_get_error_stats_empty(self, error_handler):
        stats = error_handler.get_error_stats()

        assert stats["active_errors"] == 0
        assert stats["error_counts"]["transient_parser"] == 0
        assert stats["error_counts"]["transient_api"] == 0
        assert stats["error_counts"]["permanent_corrupt"] == 0
        assert stats["error_counts"]["permanent_missing"] == 0
        assert stats["error_counts"]["unknown"] == 0

    def test_get_error_stats_with_active_errors(self, error_handler, tmp_path):
        file1 = tmp_path / "file1.xml"
        file2 = tmp_path / "file2.xml"

        error1 = ValueError("Parse error")
        error2 = ConnectionError("Connection refused")

        error_handler.should_retry(error1, file1)
        error_handler.should_retry(error2, file2)

        stats = error_handler.get_error_stats()

        assert stats["active_errors"] == 2
        assert stats["errors_by_category"]["transient_parser"] == 1
        assert stats["errors_by_category"]["transient_api"] == 1

    def test_get_error_stats_with_permanent_failures(self, error_handler, tmp_path):
        file1 = tmp_path / "file1.xml"
        file2 = tmp_path / "file2.xml"

        error1 = FileNotFoundError("File not found")
        error2 = ValueError("Corrupt data")

        error_handler.record_permanent_failure(error1, file1)
        error_handler.record_permanent_failure(error2, file2)

        stats = error_handler.get_error_stats()

        assert stats["error_counts"]["permanent_missing"] == 1
        assert stats["error_counts"]["permanent_corrupt"] == 1

    def test_clear(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)
        error_handler.record_retry(sample_file_path)

        error_handler.clear()

        assert len(error_handler._errors) == 0
        stats = error_handler.get_error_stats()
        assert stats["active_errors"] == 0
        assert all(count == 0 for count in stats["error_counts"].values())

    def test_multiple_files_same_error_type(self, error_handler, tmp_path):
        files = [tmp_path / f"file{i}.xml" for i in range(5)]

        for file_path in files:
            error = ValueError("Parse error")
            error_handler.should_retry(error, file_path)

        stats = error_handler.get_error_stats()
        assert stats["active_errors"] == 5
        assert stats["errors_by_category"]["transient_parser"] == 5

    def test_retry_count_increments(self, error_handler, sample_file_path):
        error = ValueError("Parse error")
        error_handler.should_retry(error, sample_file_path)

        assert error_handler._errors[sample_file_path].retry_count == 0

        error_handler.record_retry(sample_file_path)
        assert error_handler._errors[sample_file_path].retry_count == 1

        error_handler.record_retry(sample_file_path)
        assert error_handler._errors[sample_file_path].retry_count == 2

    def test_error_message_stored(self, error_handler, sample_file_path):
        error = ValueError("Specific error message")
        error_handler.should_retry(error, sample_file_path)

        stored_error = error_handler._errors[sample_file_path]
        assert stored_error.error_message == "Specific error message"

    def test_retry_after_success(self, error_handler, sample_file_path):
        error = ValueError("Parse error")

        error_handler.should_retry(error, sample_file_path)
        error_handler.record_retry(sample_file_path)
        error_handler.record_success(sample_file_path)

        should_retry = error_handler.should_retry(error, sample_file_path)
        assert should_retry
        assert error_handler._errors[sample_file_path].retry_count == 0
