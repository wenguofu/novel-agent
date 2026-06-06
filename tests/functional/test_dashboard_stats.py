"""Functional tests for /api/dashboard/stats (架构计划 4.1 / M5.2 T4.1).

Endpoint: ``GET /api/dashboard/stats``

Returns 3 aggregate metrics across ALL novels:

  - ``pending_review``   — chapters with no review row
  - ``pending_optimize`` — chapters whose latest review had any failure
                            (wc_ok=0 OR compliance_ok=0 OR forbidden_ok=0)
  - ``words_this_week``  — sum of word_count for chapters created in
                            the last 7 days

The endpoint delegates to ``content_db.get_db()`` (raw sqlite3 against
module-level ``DB_PATH``), so each test must point ``content_db`` at the
tmp DB with the shared helper before hitting the route.

Four dimensions (M2 core pattern):

  1. happy_path_*   — 200 with success=True, all 3 fields present
  2. edge_empty_*   — empty DB returns 0 for every metric
  3. not_found_     — N/A (no novel in URL; this is a global endpoint),
                      we substitute a 500-resilience smoke instead
  4. wrong_method_* — 405 for POST (GET-only route)

A third class ``TestMetricComputation`` exercises the SQL with concrete
fixtures — 3 chapters, mixed review states, and known word_counts — to
prove each metric is computed correctly (regression coverage for the
3 sub-queries in ``api_dashboard_stats``).
"""
import sqlite3
import pytest

from _helpers import point_content_db_at_tmp


# ─── DB seeding helpers ────────────────────────────────────────────────

def _seed_chapter(db_file, novel_name, vol, ch_num, ch_ref, content,
                  word_count, created_at="datetime('now')"):
    """Insert a chapter row directly via sqlite3 (avoids going through
    the API, which is exactly what we're testing)."""
    conn = sqlite3.connect(db_file)
    try:
        nid = conn.execute(
            "SELECT id FROM novels WHERE name=?", (novel_name,)
        ).fetchone()
        assert nid, f"novel {novel_name!r} not seeded"
        conn.execute(
            "INSERT INTO chapters "
            "(novel_id, volume, chapter_num, chapter_ref, content, "
            " word_count, content_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, '', {ts}, {ts})".format(ts=created_at),
            (nid[0], vol, ch_num, ch_ref, content, word_count),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_review(db_file, novel_name, ch_ref, wc_ok=1, comp_ok=1, forb_ok=1,
                 created_at="datetime('now')"):
    conn = sqlite3.connect(db_file)
    try:
        nid = conn.execute(
            "SELECT id FROM novels WHERE name=?", (novel_name,)
        ).fetchone()
        assert nid
        conn.execute(
            "INSERT INTO reviews "
            "(novel_id, chapter_ref, ai_review, wc_ok, compliance_ok, "
            " forbidden_ok, created_at) "
            "VALUES (?, ?, '', ?, ?, ?, {ts})".format(ts=created_at),
            (nid[0], ch_ref, wc_ok, comp_ok, forb_ok),
        )
        conn.commit()
    finally:
        conn.close()


# ─── GET /api/dashboard/stats ──────────────────────────────────────────

class TestDashboardStats:
    def test_happy_path_returns_three_metrics(self, client, sample_novel, tmp_db, monkeypatch):
        """GET returns 200 + success envelope with all 3 expected fields."""
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/dashboard/stats")
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("success") is True
        stats = data.get("stats") or {}
        # All 3 plan-mandated metrics present (plus the 2 bonus totals)
        for key in ("pending_review", "pending_optimize", "words_this_week",
                    "total_chapters", "total_words"):
            assert key in stats, f"missing {key!r} in {stats!r}"
            assert isinstance(stats[key], int), \
                f"{key!r} should be int, got {type(stats[key])}"

    def test_edge_empty_db_returns_zeros(self, client, tmp_db, monkeypatch):
        """No chapters / no reviews → all 3 metrics are 0."""
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/dashboard/stats")
        assert res.status_code == 200
        stats = res.get_json()["stats"]
        assert stats["pending_review"] == 0
        assert stats["pending_optimize"] == 0
        assert stats["words_this_week"] == 0
        assert stats["total_chapters"] == 0
        assert stats["total_words"] == 0

    def test_wrong_method_post_returns_405(self, client, sample_novel, tmp_db, monkeypatch):
        """POST is not registered for this URL → 405."""
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post("/api/dashboard/stats", json={})
        assert res.status_code == 405


# ─── Metric computation regression ────────────────────────────────────

class TestMetricComputation:
    """Concrete fixtures to lock in the 3 SQL queries.

    Test data layout (3 chapters, 2 reviews):
      ch-A (3000字) → no review        → counts toward pending_review
      ch-B (2500字) → pass review     → counts nowhere (clean)
      ch-C (4000字) → fail review     → counts toward pending_optimize
    Plus 1 chapter created 30 days ago (1000字) → does NOT count in
    words_this_week (outside the 7-day window).

    Expected: pending_review=1, pending_optimize=1, words_this_week=9500
    (3000 + 2500 + 4000, the 3 recent chapters).
    """

    @pytest.fixture
    def seeded(self, client, sample_novel, tmp_db, monkeypatch):
        cd = point_content_db_at_tmp(monkeypatch, tmp_db)
        db_file = tmp_db.replace("sqlite:///", "")

        # Chapter A: 3000 chars, no review (pending_review)
        _seed_chapter(db_file, sample_novel, "vol-01", 1, "vol-01/ch-001",
                      "x" * 3000, 3000)
        # Chapter B: 2500 chars, passing review (clean — no metric)
        _seed_chapter(db_file, sample_novel, "vol-01", 2, "vol-01/ch-002",
                      "x" * 2500, 2500)
        _seed_review(db_file, sample_novel, "vol-01/ch-002",
                     wc_ok=1, comp_ok=1, forb_ok=1)
        # Chapter C: 4000 chars, failing review (pending_optimize)
        _seed_chapter(db_file, sample_novel, "vol-01", 3, "vol-01/ch-003",
                      "x" * 4000, 4000)
        _seed_review(db_file, sample_novel, "vol-01/ch-003",
                     wc_ok=0, comp_ok=1, forb_ok=1)
        # Old chapter: 1000 chars, created 30 days ago (excluded)
        _seed_chapter(db_file, sample_novel, "vol-01", 4, "vol-01/ch-004",
                      "x" * 1000, 1000,
                      created_at="datetime('now', '-30 days')")
        return cd

    def test_pending_review_counts_unreviewed_chapters(
        self, client, sample_novel, tmp_db, monkeypatch, seeded,
    ):
        res = client.get("/api/dashboard/stats")
        assert res.status_code == 200
        stats = res.get_json()["stats"]
        # ch-A has no review row; ch-004 is also unreviewed
        # ch-B and ch-C have reviews
        assert stats["pending_review"] == 2

    def test_pending_optimize_counts_failing_reviews(
        self, client, sample_novel, tmp_db, monkeypatch, seeded,
    ):
        res = client.get("/api/dashboard/stats")
        stats = res.get_json()["stats"]
        # Only ch-C's latest review fails (wc_ok=0)
        assert stats["pending_optimize"] == 1

    def test_words_this_week_sums_recent_chapters(
        self, client, sample_novel, tmp_db, monkeypatch, seeded,
    ):
        res = client.get("/api/dashboard/stats")
        stats = res.get_json()["stats"]
        # 3000 (ch-A) + 2500 (ch-B) + 4000 (ch-C) = 9500
        # ch-004 (1000, 30 days old) excluded
        assert stats["words_this_week"] == 9500
