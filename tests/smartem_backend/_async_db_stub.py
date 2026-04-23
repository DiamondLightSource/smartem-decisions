"""Test helpers for mocking AsyncSession in AsyncSQLAlchemy-based endpoints.

The real AsyncSession exposes `await db.execute(stmt)` returning a Result with
`.scalars().first()/all()/one()/one_or_none()`. These helpers build a
MagicMock-compatible stand-in so existing tests can assert on `db.add`,
`db.add_all`, `db.commit`, etc. without a real database.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


def _scalars_result(value: Any) -> MagicMock:
    """Build an object with .first/.all/.one/.one_or_none returning `value`.

    For `.all()`, pass a list; for single-row fetches, pass the row object.
    """
    scalars = MagicMock()
    if isinstance(value, list):
        scalars.all.return_value = value
        scalars.first.return_value = value[0] if value else None
        scalars.one.return_value = value[0] if len(value) == 1 else None
        scalars.one_or_none.return_value = value[0] if len(value) == 1 else None
    else:
        scalars.first.return_value = value
        scalars.one.return_value = value
        scalars.one_or_none.return_value = value
        scalars.all.return_value = [value] if value is not None else []
    return scalars


def make_execute_result(value: Any) -> MagicMock:
    """Return a Result-shaped mock where `.scalars()` yields `value`."""
    result = MagicMock()
    result.scalars.return_value = _scalars_result(value)
    result.scalar.return_value = value
    result.first.return_value = value
    result.all.return_value = value if isinstance(value, list) else ([value] if value is not None else [])
    result.fetchone.return_value = (value,) if value is not None else None
    return result


_DEFAULT_ROW = object()


def make_async_db(first_value: Any = _DEFAULT_ROW) -> MagicMock:
    """Build an AsyncSession-like mock.

    Default: any `await db.execute(...)` resolves to a Result whose
    scalars().first() is a truthy object (i.e., the queried row exists).
    Override for specific tests via `db.execute.return_value = make_execute_result(None)`
    to simulate a 404, or assign a custom side_effect.
    """
    db = MagicMock()
    db.execute = AsyncMock(return_value=make_execute_result(first_value))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.close = AsyncMock()
    db.get = AsyncMock(return_value=first_value)
    # .add and .add_all remain sync per AsyncSession's actual API
    return db
