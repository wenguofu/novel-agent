"""Shared fixtures for functional tests.

Strategy: spin up a temporary SQLite DB in tmp_path, point DATABASE_URL
at it, run the same init path as run_v2.py (schema + config seed), then
yield a Flask test_client. Each test gets a clean DB.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure portal/ is on sys.path so we can import `app` directly.
PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))
# Ensure this test dir is on sys.path so tests can ``from _helpers
# import ...`` the shared M3.1 helpers colocated in this directory.
FUNCTIONAL_DIR = Path(__file__).resolve().parent
if str(FUNCTIONAL_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTIONAL_DIR))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB in tmp_path; yield the DB URL.

    Snapshots and restores ``sys.modules`` so the re-import dance needed
    to pick up the new ``DATABASE_URL`` does not leak into other test
    files that share this pytest process.
    """
    db_file = tmp_path / "test_content.db"
    db_url = f"sqlite:///{db_file}"
    # Snapshot the modules we will clobber so we can restore them after
    # the test, keeping cross-file test isolation intact.
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
    # Restore the original modules so subsequent test files see the
    # pristine state they expect.
    for m in list(sys.modules):
        if m.startswith(prefix) and m not in snapshot:
            del sys.modules[m]
    for m, mod in snapshot.items():
        sys.modules[m] = mod


@pytest.fixture
def client(tmp_db):
    """Flask test client bound to the tmp DB."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_novel(client, tmp_db, tmp_path, monkeypatch):
    """Pre-create a novel named 'test_novel' with minimal data.

    Also creates the novels/test_novel/ directory so file endpoints don't 500.
    Returns the novel name.
    """
    from repository import get_repo
    repo = get_repo()
    repo.upsert_novel("test_novel", title="Test Novel", genre="xianxia")
    novels_dir = tmp_path / "novels"
    novels_dir.mkdir(parents=True, exist_ok=True)
    novel_dir = novels_dir / "test_novel"
    novel_dir.mkdir(exist_ok=True)
    # Redirect app.get_novels_dir() at the test novels dir so endpoints
    # that resolve files via the filesystem (e.g. /api/novels/<name>)
    # operate on the tmp DB's novel, not the real project.
    import app as _app
    monkeypatch.setattr(_app, "get_novels_dir", lambda: str(novels_dir))
    return "test_novel"
