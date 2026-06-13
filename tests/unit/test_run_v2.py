"""Unit tests for portal/run_v2.py (MySQL-only launcher).

Tests the launcher's top-level setup: import succeeds, ``PORTAL_DIR``
is the portal/ folder, the launcher fails fast if ``DATABASE_URL`` is
missing/non-MySQL, and the schema + config seed run on a real
SQLite-via-:memory: backend (under ``TESTING=1``).
"""
import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_run_v2_imports_cleanly(tmp_db, monkeypatch):
    """The module must import without errors against the tmp DB.

    The ``tmp_db`` fixture points ``DATABASE_URL`` at a tmp SQLite file
    and re-imports ``db``/``repository`` so the launcher's
    ``ensure_unified_schema()`` and ``repo.init_config_seed()`` run
    against the tmp DB.
    """
    # Force a MySQL URL so the launcher doesn't sys.exit. The test
    # backend is still SQLite-via-tmp_db (under TESTING=1) but the
    # launcher's URL check just needs the prefix.
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost:3306/db")

    import run_v2

    assert hasattr(run_v2, "PORTAL_DIR")
    assert run_v2.PORTAL_DIR.endswith("portal"), (
        f"PORTAL_DIR should end with 'portal', got: {run_v2.PORTAL_DIR}"
    )


def test_run_v2_refuses_empty_database_url(monkeypatch):
    """The launcher MUST refuse to start without a MySQL DATABASE_URL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    if "run_v2" in sys.modules:
        del sys.modules["run_v2"]

    with pytest.raises(SystemExit) as exc_info:
        import run_v2  # noqa: F401
    assert exc_info.value.code == 1


def test_run_v2_refuses_sqlite_database_url(monkeypatch):
    """The launcher MUST refuse to start with a SQLite DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///portal/content.db")

    if "run_v2" in sys.modules:
        del sys.modules["run_v2"]

    with pytest.raises(SystemExit) as exc_info:
        import run_v2  # noqa: F401
    assert exc_info.value.code == 1
