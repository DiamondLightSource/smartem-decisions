"""Regression guards for issue #248.

Two invariants keep post-commit SELECTs from re-appearing in `api_server.py`:

1. `SessionLocal` must be built with `expire_on_commit=False`; otherwise every
   attribute access on a just-committed entity triggers a lazy SELECT.
2. No `db.refresh(...)` calls may be reintroduced in `api_server.py`.

Running a full FastAPI+Postgres harness for this would be disproportionate to a
config-plus-deletion fix; the checks below are static-inspection guards that run
without any database. End-to-end verification is covered by the manual load test
described in the PR description.
"""

import ast
import inspect
from pathlib import Path

from smartem_backend import api_server


def test_session_local_has_expire_on_commit_false():
    """Assert the sessionmaker() call in api_server.py passes expire_on_commit=False.

    Uses AST inspection rather than reading `api_server.SessionLocal.kw` so the
    test runs regardless of whether the DB is actually initialised (the runtime
    object is None when SKIP_DB_INIT=true).
    """
    source_path = Path(inspect.getfile(api_server))
    tree = ast.parse(source_path.read_text())

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "sessionmaker"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        expire = kwargs.get("expire_on_commit")
        assert isinstance(expire, ast.Constant) and expire.value is False, (
            "sessionmaker() in api_server.py must pass expire_on_commit=False so that "
            "attributes read by publish_*() and response models after db.commit() do "
            "not trigger lazy SELECTs (issue #248)."
        )
        return

    raise AssertionError("No sessionmaker() call found in api_server.py")


def test_no_db_refresh_calls_in_api_server():
    source_path = Path(inspect.getfile(api_server))
    tree = ast.parse(source_path.read_text())

    offending: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "refresh":
            offending.append(node.lineno)

    assert not offending, (
        f"Found db.refresh() call(s) in api_server.py at line(s) {offending}. "
        "These were removed in issue #248 because they cause N+1 SELECTs under "
        "high throughput. With expire_on_commit=False, just-inserted entities "
        "keep their attributes populated after commit without re-reading."
    )
