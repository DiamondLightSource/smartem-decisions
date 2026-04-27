"""PostgreSQL LISTEN/NOTIFY plumbing for agent instruction delivery.

Replaces the steady-state polling that the SSE instruction stream used to do.
Writers issue NOTIFY in the same transaction as the INSERT/UPDATE; the SSE
handler holds a dedicated asyncpg connection LISTENing on this channel and
wakes only when a notification for its session arrives.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

INSTRUCTION_CHANNEL = "agent_instructions"


async def notify_instruction_pending(session: AsyncSession, agent_session_id: str) -> None:
    """Queue a NOTIFY for `agent_session_id` on the instruction channel.

    PostgreSQL fires queued NOTIFYs on COMMIT, so this must be called before
    the caller's commit. The notification reaches LISTENers atomically with
    the row mutation that motivates it.
    """
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": INSTRUCTION_CHANNEL, "payload": agent_session_id},
    )
