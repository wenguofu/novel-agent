"""Unit tests for portal/init_unified_db.py (M3.1 W2 Task 2.3).

Targets line coverage 0% -> 80% on the unified DB initializer. The
init script is hard to test in isolation because it depends on
``DATABASE_URL`` and stdout. We use the ``tmp_db`` fixture from
``tests/unit/conftest.py`` to spin up a fresh SQLite DB and exercise
the real ``init()`` code path.

The import happens INSIDE each test function, not at module scope, so
we don't pin to the wrong (real) DB — this is the same import trap
that Task 2.2 hit on ``repository``.
"""
import pytest


# ─── Happy path ──────────────────────────────────────────────────────────

class TestInit:
    def test_init_creates_all_tables(self, tmp_db, capsys):
        """Run init() against a tmp DB; verify it creates the unified
        schema, seeds config data, prints the completion banner, and
        leaves the DB populated."""
        from init_unified_db import init
        init()
        captured = capsys.readouterr()

        # The banner should be the final stdout line.
        assert "Database initialization complete" in captured.out
        # Step banners should also be present (smoke check on stdout
        # contract).
        assert "Creating tables" in captured.out
        assert "Migrating data" in captured.out
        assert "Seeding default config data" in captured.out
        assert "Verification" in captured.out

        # Check the DB actually has tables.
        from db import get_engine
        from sqlalchemy import inspect
        engine = get_engine()
        tables = inspect(engine).get_table_names()
        # 24 tables are documented; allow some flexibility for
        # future schema changes.
        assert len(tables) >= 20, (
            f"Expected >= 20 tables, got {len(tables)}: {tables}"
        )

    def test_init_is_idempotent(self, tmp_db, capsys):
        """Calling init() twice must not raise. The tmp_db fixture
        already created the schema + seeded config; calling init()
        again re-runs create_all (no-op for existing tables) and
        re-seeds (idempotent inserts)."""
        from init_unified_db import init
        init()  # First call: tables already exist via tmp_db fixture
        capsys.readouterr()  # Discard first call's output
        init()  # Second call: must not raise
        captured = capsys.readouterr()
        assert "Database initialization complete" in captured.out

    def test_init_seeds_default_config(self, tmp_db, capsys):
        """After init() runs, the config tables must contain the
        default banned words / compliance rules / style presets."""
        from init_unified_db import init
        init()
        capsys.readouterr()

        # Import inside the function — repository is reloaded by
        # the tmp_db fixture and bound to the tmp DB.
        from repository import get_repo
        repo = get_repo()

        # Step 4 of init() runs list_novels / list_banned_words /
        # list_style_presets as its verification step. We re-run
        # them here to confirm the seed landed.
        assert isinstance(repo.list_novels(), list)
        banned = repo.list_banned_words()
        assert len(banned) >= 1, "Expected at least one banned word"
        styles = repo.list_style_presets()
        assert len(styles) >= 1, "Expected at least one style preset"


# ─── Verify branch: the except clause ───────────────────────────────────

class TestInitVerifyException:
    def test_init_completes_even_if_verification_raises(self, tmp_db, capsys, monkeypatch):
        """If the verification step (Step 4) raises, init() must
        still print the completion banner. This covers the
        ``except Exception`` branch at lines 61-62."""
        from init_unified_db import init
        from repository import get_repo

        # Stub list_novels to raise — this is the first call in
        # the verification step. The except branch should catch it
        # and continue.
        def _raise(*a, **kw):
            raise RuntimeError("simulated verify failure")

        repo = get_repo()
        monkeypatch.setattr(repo, "list_novels", _raise)

        # Must not raise.
        init()
        captured = capsys.readouterr()
        # Banner still printed.
        assert "Database initialization complete" in captured.out
        # Warning was emitted.
        assert "Verification warning" in captured.out
