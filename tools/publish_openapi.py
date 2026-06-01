#!/usr/bin/env python3
"""Regenerate the canonical OpenAPI spec and report whether the API content changed.

This repository is the canonical publisher of the SmartEM OpenAPI specification
(ADR 0020). The committed spec lives at ``docs/api/openapi.json`` and downstream
repositories (smartem-frontend, smartem-devtools) consume it.

``info.version`` is ``setuptools_scm``-derived and changes on every commit, so a
naive diff would report a change every time. We therefore compare the spec with
the volatile ``info.version`` and ``servers`` normalised out, and rewrite the file
only when the actual API surface differs. When it does, the freshly generated spec
(carrying the current version) is written, so the committed version marks the
commit at which the contract last changed.

Prints ``changed=true`` or ``changed=false`` to stdout (consumed by CI).
"""

import json
import os
from pathlib import Path

os.environ.setdefault("SKIP_DB_INIT", "true")

from smartem_backend.api_server import app  # noqa: E402

DEST = Path("docs/api/openapi.json")


def _content_only(spec: dict) -> str:
    """Serialise the spec with the volatile fields removed, for change detection."""
    clone = json.loads(json.dumps(spec))
    clone.get("info", {}).pop("version", None)
    clone.pop("servers", None)
    return json.dumps(clone, sort_keys=True)


def main() -> None:
    new_spec = app.openapi()
    changed = True
    if DEST.exists():
        existing = json.loads(DEST.read_text())
        changed = _content_only(existing) != _content_only(new_spec)

    if changed:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(json.dumps(new_spec, indent=2, sort_keys=True) + "\n")

    print(f"changed={'true' if changed else 'false'}")


if __name__ == "__main__":
    main()
