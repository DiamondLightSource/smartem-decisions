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


class TestMotionCorrectionComplete:
    base_event = {
        "event_type": "motion_correction.completed",
        "micrograph_uuid": "mic-1",
        "total_motion": 1.5,
        "average_motion": 0.1,
    }

    def test_publishes_registered_event(self, db, monkeypatch, stub_publisher):
        grid_row = MagicMock()
        grid_row.grid_uuid = "grid-1"
        db.execute.return_value.one.return_value = (grid_row,)
        db.execute.return_value.scalars.return_value.all.return_value = []

        async def _stub_check(*args, **kwargs):
            return 0.7

        async def _stub_prior(*args, **kwargs):
            return None

        async def _stub_publish(*args, **kwargs):
            return True

        monkeypatch.setattr(consumer, "_check_against_statistics", _stub_check)
        monkeypatch.setattr(consumer, "prior_update", _stub_prior)
        monkeypatch.setattr(consumer, "publish_motion_correction_registered", _stub_publish)

        import asyncio

        asyncio.run(consumer.handle_motion_correction_complete(dict(self.base_event)))

        assert db.add.call_count == 1
        assert db.commit.await_count == 1


class TestRefreshPredictions:
    base_event = {
        "event_type": "refresh.predictions",
        "grid_uuid": "grid-1",
    }

    def test_calls_predictions_helpers(self, db, monkeypatch):
        called: list[str] = []

        async def _stub_overall(grid_uuid, session):
            called.append(f"overall:{grid_uuid}")

        async def _stub_ordered(grid_uuid, session):
            called.append(f"ordered:{grid_uuid}")
            return []

        monkeypatch.setattr(consumer, "overall_predictions_update", _stub_overall)
        monkeypatch.setattr(consumer, "ordered_holes", _stub_ordered)

        import asyncio

        asyncio.run(consumer.handle_refresh_predictions(dict(self.base_event)))

        assert called == ["overall:grid-1", "ordered:grid-1"]


class TestGridCreated:
    base_event = {
        "event_type": "grid.created",
        "uuid": "grid-1",
        "name": "g1",
        "data_directory": "/tmp/x",
        "atlas_directory": "/tmp/x/atlas",
        "scan_start_datetime": None,
        "scan_end_datetime": None,
        "instrument_id": None,
        "acquisition_uuid": "acq-1",
    }

    def test_invokes_initialise(self, monkeypatch):
        called: list[str] = []

        async def _stub(grid_uuid, engine=None):
            called.append(grid_uuid)

        monkeypatch.setattr(consumer, "initialise_all_models_for_grid", _stub)

        import asyncio

        asyncio.run(consumer.handle_grid_created(dict(self.base_event)))

        assert called == ["grid-1"]
