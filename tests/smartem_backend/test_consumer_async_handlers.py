"""Smoke tests for AsyncSession-backed consumer handlers.

Validates that the handlers converted from `run_in_threadpool(_db_work)` shims to
native `async with SessionLocal()` blocks still drive the expected ORM calls
(add / commit, lookups via `await session.execute(...)`).

Patches `consumer.SessionLocal` with a context-manager that yields a mocked
AsyncSession from `_async_db_stub.make_async_db()`. The mock returns a truthy
row by default, so existence-check branches are exercised without a real DB.
"""

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

os.environ["SKIP_DB_INIT"] = "true"

import pytest

from smartem_backend import consumer
from smartem_backend import mq_publisher as mq_publisher_module

from ._async_db_stub import make_async_db, make_execute_result


@pytest.fixture
def db():
    return make_async_db()


@pytest.fixture(autouse=True)
def patch_session_local(db, monkeypatch):
    @asynccontextmanager
    async def _session_factory():
        yield db

    monkeypatch.setattr(consumer, "SessionLocal", _session_factory)
    yield db


@pytest.fixture(autouse=True)
def stub_publisher(monkeypatch):
    publisher = MagicMock()
    publisher.publish_event = AsyncMock(return_value=True)
    monkeypatch.setattr(mq_publisher_module, "_publisher", publisher)
    yield publisher


class TestModelParameterUpdate:
    def test_inserts_and_commits(self, db):
        event_data = {
            "event_type": "grid.model_parameter_update",
            "grid_uuid": "grid-1",
            "prediction_model_name": "model-a",
            "key": "alpha",
            "value": 0.5,
            "metric": "motioncorrection",
            "group": "default",
        }

        import asyncio

        asyncio.run(consumer.handle_model_parameter_update(event_data))

        assert db.add.call_count == 1
        assert db.commit.await_count == 1


class TestAgentInstructionCreated:
    base_event = {
        "event_type": "agent.instruction.created",
        "instruction_id": "instr-1",
        "session_id": "sess-1",
        "agent_id": "agent-1",
        "instruction_type": "microscope.control.skip_gridsquares",
        "payload": {"gridsquare_ids": ["gs-1"]},
        "sequence_number": 1,
        "priority": "normal",
        "expires_at": None,
        "instruction_metadata": None,
    }

    def test_persists_when_session_exists(self, db):
        import asyncio

        asyncio.run(consumer.handle_agent_instruction_created(dict(self.base_event)))

        assert db.add.call_count == 1
        assert db.commit.await_count == 1

    def test_skips_when_session_missing(self, db):
        db.execute.return_value = make_execute_result(None)

        import asyncio

        asyncio.run(consumer.handle_agent_instruction_created(dict(self.base_event)))

        assert db.add.call_count == 0
        assert db.commit.await_count == 0


class TestCreateFoilHoleGroup:
    base_event = {
        "event_type": "foilhole.group_create",
        "group_uuid": "grp-1",
        "grid_uuid": "grid-1",
        "name": "groupie",
        "foilhole_uuids": ["fh-1", "fh-2"],
    }

    def test_creates_when_group_missing(self, db):
        db.execute.return_value = make_execute_result(None)

        import asyncio

        asyncio.run(consumer.handle_create_foilhole_group(dict(self.base_event)))

        assert db.add.call_count == 1
        assert db.add_all.call_count == 1
        assert db.commit.await_count == 1

    def test_extends_when_group_exists(self, db):
        existing_group = MagicMock()
        existing_group.uuid = "grp-1"
        existing_group.name = "old-name"
        db.execute.return_value = make_execute_result(existing_group)

        import asyncio

        asyncio.run(consumer.handle_create_foilhole_group(dict(self.base_event)))

        assert db.add_all.call_count == 1
        assert db.commit.await_count == 1


class TestActiveAgentSessionsHelper:
    def test_returns_scalars_list(self, db):
        sentinel = MagicMock()
        db.execute.return_value = make_execute_result([sentinel, sentinel])

        import asyncio

        result = asyncio.run(consumer._get_active_agent_sessions())

        assert result == [sentinel, sentinel]
