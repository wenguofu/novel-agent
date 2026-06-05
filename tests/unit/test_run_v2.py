"""Unit tests for portal/run_v2.py (M3.1 W2 Task 2.4).

Targets line coverage 0% -> 60%. The launcher is hard to unit-test
fully because it imports app, patches content_db paths, and starts
a server. We test the importable bits: module-level constants and
the fact that ``run_v2`` doesn't blow up on import.

The ``tmp_db`` fixture is required: run_v2's top-level code calls
``ensure_unified_schema()`` and ``repo.init_config_seed()`` against
whatever ``DATABASE_URL`` is set when the module is imported. Without
the fixture, those calls would run against the real portal DB
(``portal/content.db``) and pollute it with test schema/seeds. The
fixture points ``DATABASE_URL`` at a tmp file and re-imports the
cached modules so run_v2 picks up the tmp-bound singletons.

The import happens INSIDE the test function, not at module scope, so
we don't pin to the wrong (real) DB — same import-trap lesson from
Task 2.2/2.3.

The ``if __name__ == "__main__":`` block at the bottom of run_v2.py
is excluded by ``.coveragerc`` (line 11) and is not exercised here.
"""
import importlib
import os
import sys
from unittest.mock import MagicMock, patch


def test_run_v2_imports_cleanly(tmp_db):
    """The module must import without errors against the tmp DB.

    Covers all the top-level setup: PORTAL_DIR, DATABASE_URL,
    ensure_unified_schema(), repo.init_config_seed(), content_db
    patching, app import, and context_builder patching.
    """
    import run_v2

    # Module-level constant: must end with 'portal' (the run_v2.py
    # file lives in portal/, so __file__ resolves there).
    assert hasattr(run_v2, "PORTAL_DIR")
    assert run_v2.PORTAL_DIR.endswith("portal"), (
        f"PORTAL_DIR should end with 'portal', got: {run_v2.PORTAL_DIR}"
    )

    # DATABASE_URL was either inherited from the tmp_db fixture or
    # defaulted by run_v2 itself; in either case it must point at
    # SQLite for this test.
    db_url = os.environ.get("DATABASE_URL", "")
    assert db_url.startswith("sqlite"), (
        f"DATABASE_URL should be sqlite (tmp_db fixture), got: {db_url}"
    )

    # The module patched content_db.get_db at import time. Verify
    # the patch landed: content_db should have a different
    # get_db than the one captured during the test's import.
    import content_db
    assert content_db.get_db.__name__ == "_unified_get_db", (
        f"content_db.get_db should be the run_v2 patch, got: {content_db.get_db}"
    )

    # The module set up the unified DB path on content_db.
    assert str(content_db.DB_PATH).endswith("content.db"), (
        f"content_db.DB_PATH should be the unified content.db, got: {content_db.DB_PATH}"
    )

    # Exercise the SQLite branch of _unified_get_db (lines 74, 78-83).
    # The if-check (line 74) is executed, the MySQL return (line 76)
    # is skipped, and the SQLite connect/PRAGMA path (78-83) runs.
    conn = content_db.get_db()
    try:
        # PRAGMA journal_mode=WAL should have been applied.
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal", f"Expected WAL mode, got: {mode}"
        # PRAGMA foreign_keys=ON should have been applied.
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1, f"Expected foreign_keys=1, got: {fk}"
    finally:
        conn.close()


def test_run_v2_mysql_mode_patches_app(monkeypatch):
    """In MySQL mode, run_v2 patches app's raw sqlite3 usage functions
    to be repo-backed (lines 99-148). Re-import run_v2 with a mocked
    MySQL DATABASE_URL and stubbed DB functions to prevent an actual
    MySQL connection.

    Without this test, lines 104-148 (the MySQL-mode patching block)
    are never executed and coverage stalls around 56%.
    """
    # First import: SQLite mode (uses the default portal/content.db
    # path from run_v2's own setdefault; the DB functions are real
    # but the connection target is a sqlite file that may or may not
    # exist — ensure_unified_schema is tolerant of existing schemas).
    import run_v2  # noqa: F401  (initial import to populate sys.modules)

    # Now flip to MySQL mode and re-import. We mock the DB-touching
    # functions so the reload doesn't try to connect to a real MySQL
    # server. The key thing is that the `else` branch at line 102
    # executes, which defines and assigns the patched functions.
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://fake@localhost/fake")

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []
    mock_engine = MagicMock()
    mock_engine.__enter__ = lambda s: s
    mock_engine.__exit__ = lambda s, *a: False

    with patch("db.ensure_unified_schema"), \
         patch("db.get_engine", return_value=mock_engine), \
         patch("sqlalchemy.inspect", return_value=mock_inspector), \
         patch("repository.get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        importlib.reload(run_v2)

        # In MySQL mode, the patching block (lines 99-148) should have
        # run and replaced app's raw sqlite3 usage functions with
        # repo-backed wrappers.
        import app
        assert app._init_usage_db.__name__ == "_patched_init_usage_db", (
            f"app._init_usage_db should be the MySQL-mode patch, got: {app._init_usage_db}"
        )
        assert app._upsert_daily_stats.__name__ == "_patched_upsert_daily_stats", (
            f"app._upsert_daily_stats should be the MySQL-mode patch, got: {app._upsert_daily_stats}"
        )
        assert app.log_token_usage.__name__ == "_patched_log_token_usage", (
            f"app.log_token_usage should be the MySQL-mode patch, got: {app.log_token_usage}"
        )
        assert app._db_load_config.__name__ == "_patched_db_load_config", (
            f"app._db_load_config should be the MySQL-mode patch, got: {app._db_load_config}"
        )
        assert app._db_save_config.__name__ == "_patched_db_save_config", (
            f"app._db_save_config should be the MySQL-mode patch, got: {app._db_save_config}"
        )
