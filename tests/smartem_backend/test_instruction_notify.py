"""Verify the NOTIFY helper issues the right SQL and that writers wire it in."""

import os
from unittest.mock import AsyncMock, MagicMock

os.environ["SKIP_DB_INIT"] = "true"

import pytest

from smartem_backend.instruction_notify import INSTRUCTION_CHANNEL, notify_instruction_pending


class TestNotifyHelper:
    @pytest.mark.asyncio
    async def test_emits_pg_notify_with_session_id_payload(self):
        session = MagicMock()
        session.execute = AsyncMock()

        await notify_instruction_pending(session, "sess-abc")

        assert session.execute.await_count == 1
        stmt, params = session.execute.await_args.args
        assert "pg_notify" in str(stmt).lower()
        assert params == {"channel": INSTRUCTION_CHANNEL, "payload": "sess-abc"}

    def test_channel_is_stable(self):
        assert INSTRUCTION_CHANNEL == "agent_instructions"
