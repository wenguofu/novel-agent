"""Regression tests for harness plan item [8] — atomic writes in
``portal/content_db.py``.

The three ``upsert_*`` functions (``upsert_chapter_outline``,
``upsert_danger_issue``, ``upsert_story_tracking``) used to call
``conn.execute(INSERT)`` followed by an explicit ``conn.commit()``.
If ``conn.execute`` raised mid-statement (constraint violation,
disk-full, etc.) the explicit commit had not yet run, and a
subsequent call to ``conn.close()`` would auto-rollback — but the
**partial** write could still be visible to readers if the
connection was reused before close.

This commit replaces the explicit-commit pattern with
``with conn:`` (sqlite3.Connection context manager), which
guarantees:

  - commit on successful block exit
  - rollback on any exception inside the block
  - the transaction boundary is explicit in the source

These tests pin the new contract.
"""
import pytest

from content_db import (
    upsert_chapter_outline,
    upsert_danger_issue,
    upsert_story_tracking,
    get_chapter_outline,
    get_danger_issues,
    get_story_tracking,
)


NOVEL = "atomic-writes-test-novel"


@pytest.fixture(autouse=True)
def _ensure_test_novel():
    """Create a throwaway novel so _get_novel_id() resolves."""
    from content_db import get_db
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO novels (name, title) VALUES (?, ?)",
            (NOVEL, "Atomic Writes Test"),
        )
        conn.commit()
    finally:
        conn.close()
    yield


class TestUpsertChapterOutlineAtomicity:
    """upsert_chapter_outline must use a transaction boundary."""

    def test_happy_path_writes_row(self):
        upsert_chapter_outline(NOVEL, "vol-01", 1, {
            "title": "Test",
            "function": ["setup"],
            "core_events": "evt",
            "foreshadowing": [],
            "ending_hook": "",
            "is_danger_scene": False,
            "word_count": 100,
        })
        row = get_chapter_outline(NOVEL, "vol-01", 1)
        assert row is not None
        assert row["title"] == "Test"
        assert row["word_count"] == 100

    def test_rollback_on_execute_failure(self, monkeypatch):
        """If conn.execute() raises inside the with-block, the
        write must be rolled back — the next read should not see
        a half-applied mutation."""
        import content_db

        # First, seed a baseline row that we can compare against
        upsert_chapter_outline(NOVEL, "vol-01", 1, {
            "title": "Original", "word_count": 100,
        })
        baseline = get_chapter_outline(NOVEL, "vol-01", 1)
        assert baseline["title"] == "Original"

        def exploding_execute(self, sql, *a, **kw):
            # Blow up on the write. SELECTs in _get_novel_id pass
            # through unchanged.
            if "INSERT INTO chapter_outlines" in sql:
                raise RuntimeError("simulated disk failure")
            return self._original_execute(sql, *a, **kw)

        # Patch content_db.get_db to return a connection whose
        # ``execute`` method explodes on the INSERT. We delegate
        # to the original sqlite3 connection so reads still work.
        real_get_db = content_db.get_db
        original_execute = None  # captured per-connection below

        class ExplodingConn:
            def __init__(self, real):
                self._real = real
                self._original_execute = real.execute
            def execute(self, sql, *a, **kw):
                return exploding_execute(self, sql, *a, **kw)
            def __enter__(self):
                return self._real.__enter__()
            def __exit__(self, exc_type, exc, tb):
                return self._real.__exit__(exc_type, exc, tb)
            def commit(self):
                return self._real.commit()
            def rollback(self):
                return self._real.rollback()
            def close(self):
                return self._real.close()

        def wrapped_get_db():
            return ExplodingConn(real_get_db())

        monkeypatch.setattr(content_db, "get_db", wrapped_get_db)

        with pytest.raises(RuntimeError, match="simulated disk failure"):
            upsert_chapter_outline(NOVEL, "vol-01", 1, {
                "title": "Should Not Stick", "word_count": 999,
            })

        # The rollback should have preserved the original row
        row = get_chapter_outline(NOVEL, "vol-01", 1)
        assert row is not None
        assert row["title"] == "Original", (
            f"rollback failed: title was mutated to {row['title']!r}; "
            f"the with-block did not roll back the failed write"
        )
        assert row["word_count"] == 100


class TestUpsertDangerIssueAtomicity:
    def test_happy_path_writes_row(self):
        import json
        upsert_danger_issue(NOVEL, "vol-01", 1, {
            "danger_level": "high",
            "core_danger": "x",
            "content": "y",
            "rhythm_data": {"k": "v"},
            "foreshadowing_data": ["seed"],
        })
        rows = get_danger_issues(NOVEL, "vol-01")
        assert len(rows) == 1
        assert rows[0]["danger_level"] == "high"
        assert rows[0]["foreshadowing_data"] == ["seed"]


class TestUpsertStoryTrackingAtomicity:
    def test_happy_path_writes_row(self):
        upsert_story_tracking(NOVEL, "character", "lin_feng", "alive")
        upsert_story_tracking(NOVEL, "character", "lin_feng", "wounded")
        rows = get_story_tracking(NOVEL, "character")
        assert len(rows) == 1
        assert rows[0]["record_value"] == "wounded", (
            "upsert should overwrite on conflict"
        )


class TestNoExplicitCommitInUpsertFunctions:
    """Static guard: the three upsert_* functions must not contain
    a raw ``conn.commit()`` call. They must use ``with conn:``
    instead so the transaction boundary is unambiguous.
    """

    @pytest.mark.parametrize("func_name", [
        "upsert_chapter_outline",
        "upsert_danger_issue",
        "upsert_story_tracking",
    ])
    def test_no_explicit_commit(self, func_name):
        import inspect
        import content_db
        from pathlib import Path
        # Read the source file directly (inspect.getsource works too,
        # but reading + grep is more robust against import side effects)
        src_path = Path(content_db.__file__).read_text(encoding="utf-8")
        # Extract just the function body
        func = getattr(content_db, func_name)
        src = inspect.getsource(func)
        # Allow the comment to mention "explicit conn.commit()", but
        # the code itself must not call it.
        code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
        code_body = "\n".join(code_lines)
        assert "conn.commit()" not in code_body, (
            f"{func_name} still calls conn.commit() explicitly; "
            f"replace with `with conn:` for atomic transactions"
        )
        # Positive assertion: must use the with-block
        assert "with conn:" in src, (
            f"{func_name} must use `with conn:` for transaction "
            f"boundary (sqlite3 auto-commit/rollback)"
        )
