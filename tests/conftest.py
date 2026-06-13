"""Shared pytest config: make scripts/ importable + default test env.

The portal now requires MySQL via ``DATABASE_URL``. To keep the test
suite (which uses SQLite-via-``:memory:`` per test) working, we:

  1. Add the scripts/ directory to sys.path so migration scripts are
     importable.
  2. Set ``TESTING=1`` at conftest import time so ``portal.db`` accepts
     the in-memory SQLite path.
  3. Provide a session-scope autouse fixture that points
     ``DATABASE_URL`` at a per-session SQLite file in a temp dir for
     any test that does NOT have its own ``tmp_db`` fixture (e.g. the
     root-level tests like ``test_init.py`` and ``test_schema.py``
     that import ``db`` at module scope). The schema is created once
     at session start so queries against an empty DB still work
     (rows just don't exist).
"""
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

PORTAL_DIR = Path(__file__).parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))

# Set TESTING=1 at module import so portal.db.validate_database_url()
# (called at portal.db import time) sees the permissive mode.
os.environ.setdefault("TESTING", "1")

# Default DATABASE_URL for the test session, used by any test that
# imports ``db`` without its own ``tmp_db`` fixture. Individual test
# files that use ``tmp_db`` override this.
_DEFAULT_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="novel_agent_tests_"))
_DEFAULT_TEST_DB = _DEFAULT_TEST_DB_DIR / "session_content.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DEFAULT_TEST_DB}")


def pytest_configure(config):
    """Create the schema in the session-level test DB once at start.

    Without this, tests that query the DB but don't seed data (e.g.
    ``test_context_builder``) would see "no such table" errors
    instead of getting the expected empty result / graceful
    handling.
    """
    if os.environ.get("DATABASE_URL", "").startswith("sqlite:///"):
        from db import ensure_unified_schema
        try:
            ensure_unified_schema()
        except Exception:
            pass
