"""Shared fixtures for unit tests.

Mirrors ``tests/functional/conftest.py``'s ``tmp_db`` fixture so unit
tests under ``tests/unit/`` have access to a fresh SQLite DB without
having to depend on the sibling functional package.

The fixture spins up an isolated SQLite file in ``tmp_path``, points
``DATABASE_URL`` at it, then forces a clean re-import of the modules
that cache the engine/session factory at import time. Snapshots and
restores ``sys.modules`` so the dance does not leak across test files.
"""
import sys
from pathlib import Path

import pytest

# Ensure portal/ is on sys.path so we can import ``repository`` directly.
PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB in tmp_path; yield the DB URL."""
    db_file = tmp_path / "test_content.db"
    db_url = f"sqlite:///{db_file}"
    prefix = ("db", "repository", "app", "content_db", "config", "context_builder")
    snapshot = {m: mod for m, mod in sys.modules.items() if m.startswith(prefix)}
    for m in list(snapshot):
        del sys.modules[m]
    monkeypatch.setenv("DATABASE_URL", db_url)
    from db import ensure_unified_schema
    from repository import get_repo
    ensure_unified_schema()
    repo = get_repo()
    repo.init_config_seed()
    yield db_url
    # Restore the original modules so other test files see pristine state.
    for m in list(sys.modules):
        if m.startswith(prefix) and m not in snapshot:
            del sys.modules[m]
    for m, mod in snapshot.items():
        sys.modules[m] = mod
