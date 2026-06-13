"""Shared fixtures for unit tests.

Mirrors ``tests/functional/conftest.py``'s ``tmp_db`` fixture so unit
tests under ``tests/unit/`` have access to a fresh SQLite DB without
having to depend on the sibling functional package.

The fixture spins up an isolated SQLite file in ``tmp_path``, points
``DATABASE_URL`` at it, then forces a clean re-import of the modules
that cache the engine/session factory at import time. Snapshots and
restores ``sys.modules`` so the dance does not leak across test files.

Note: production code now requires MySQL via ``DATABASE_URL``. The
``TESTING=1`` env var (set in this conftest at module load time, below)
opts the runtime into a permissive mode that allows the in-memory
SQLite path used by the test suite. The portal refuses to start
without ``TESTING=1`` if ``DATABASE_URL`` is empty or non-MySQL.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure portal/ is on sys.path so we can import ``repository`` directly.
PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))

# Set TESTING=1 at module import time so portal.db.validate_database_url()
# (called at portal.db import time) sees the permissive mode. The
# autouse fixture below is for tests that mutate the env mid-run.
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _keep_testing_set(monkeypatch):
    """Make sure TESTING=1 stays set even if a test mutates the env."""
    monkeypatch.setenv("TESTING", "1")
    yield


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB in tmp_path; yield the DB URL."""
    db_file = tmp_path / "test_content.db"
    db_url = f"sqlite:///{db_file}"
    prefix = ("db", "repository", "app", "content_db", "config", "context_builder", "init_unified_db")
    snapshot = {m: mod for m, mod in sys.modules.items() if m.startswith(prefix)}
    for m in list(snapshot):
        del sys.modules[m]
    # Temporarily move portal/config.db and portal/usage.db out of the
    # way so ensure_unified_schema() doesn't migrate real data into the
    # tmp DB (and rename the real files to .bak).
    hidden = []
    for name in ("config.db", "usage.db"):
        path = PORTAL_DIR / name
        if path.exists():
            hidden_path = path.with_suffix(path.suffix + ".testhidden")
            os.rename(str(path), str(hidden_path))
            hidden.append((path, hidden_path))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TESTING", "1")
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
    # Restore the hidden real DB files.
    for orig, hidden_path in hidden:
        if hidden_path.exists():
            os.rename(str(hidden_path), str(orig))
    # ensure_unified_schema() may have renamed portal/config.db or
    # portal/usage.db to .bak if they existed. Restore them.
    for name in ("config.db", "usage.db"):
        bak = PORTAL_DIR / (name + ".bak")
        orig = PORTAL_DIR / name
        if bak.exists() and not orig.exists():
            os.rename(str(bak), str(orig))
