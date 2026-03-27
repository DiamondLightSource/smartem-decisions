import logging
import time
from unittest.mock import MagicMock

from smartem_agent.remote_log_handler import RemoteLogHandler


class TestRemoteLogHandler:
    def _make_handler(self, api_client=None, buffer_size=10, flush_interval=60.0):
        client = api_client or MagicMock()
        handler = RemoteLogHandler(
            api_client=client,
            agent_id="test-agent",
            session_id="test-session",
            buffer_size=buffer_size,
            flush_interval=flush_interval,
        )
        return handler, client

    def test_emit_buffers_records(self):
        handler, client = self._make_handler(buffer_size=50)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        client.send_logs.assert_not_called()
        handler.close()

    def test_flush_on_buffer_full(self):
        handler, client = self._make_handler(buffer_size=2)
        for i in range(2):
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"message {i}",
                args=None,
                exc_info=None,
            )
            handler.emit(record)
        client.send_logs.assert_called_once()
        call_args = client.send_logs.call_args
        assert call_args[0][0] == "test-agent"
        assert call_args[0][1] == "test-session"
        assert len(call_args[0][2]) == 2
        handler.close()

    def test_flush_sends_buffered_logs(self):
        handler, client = self._make_handler()
        record = logging.LogRecord(
            name="mylogger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warning msg",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        handler.flush()
        client.send_logs.assert_called_once()
        log_entry = client.send_logs.call_args[0][2][0]
        assert log_entry["level"] == "WARNING"
        assert log_entry["logger_name"] == "mylogger"
        assert log_entry["message"] == "warning msg"
        handler.close()

    def test_close_flushes_remaining(self):
        handler, client = self._make_handler()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="final message",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        handler.close()
        client.send_logs.assert_called()

    def test_failed_send_does_not_raise(self):
        client = MagicMock()
        client.send_logs.side_effect = Exception("network error")
        handler, _ = self._make_handler(api_client=client, buffer_size=1)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        handler.close()

    def test_timed_flush(self):
        handler, client = self._make_handler(flush_interval=0.2)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="timed test",
            args=None,
            exc_info=None,
        )
        handler.emit(record)
        time.sleep(0.4)
        client.send_logs.assert_called()
        handler.close()
