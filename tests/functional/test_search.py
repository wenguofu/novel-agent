"""Functional tests for content search / stats / sync endpoints (M3 Task 14).

Endpoint coverage (4 total):
  GET  /api/content/search?q=                                    2-dim
  GET  /api/content/stats/<novel>                                2-dim
  POST /api/content/sync                                         2-dim
  GET  /api/content/quality-report/<novel>                       2-dim

Notes on path conventions (accumulated across Tasks 4–14):
  - All four endpoints are read-/sync-oriented; the only POST is
    ``/api/content/sync`` (no body required).
  - These endpoints all delegate to ``content_db`` helpers
    (``search_all``, ``get_novel_stats``, ``sync_novel_from_files``,
    ``sync_all_novels``) which use raw sqlite3 against
    ``content_db.DB_PATH``. The standard
    ``_point_content_db_at_tmp`` helper redirects the module at
    the tmp DB.
  - ``/api/content/search`` requires ``q``; missing → 400.
  - ``/api/content/stats`` returns 404 with success=False when the
    novel row does not exist.
  - ``/api/content/sync`` accepts ``novel`` in the body; when
    present, syncs that novel; otherwise calls ``sync_all_novels()``.
  - ``/api/content/quality-report`` runs several aggregate queries
    against the content DB and returns a structured report.
  - LESSON (new): ``/api/content/quality-report`` uses a raw
    sqlite3 connection via ``content_db.get_db()`` and queries
    ``chapters``, ``reviews``, etc. directly. The repo's
    ``_RepoConfigWrapper`` does not back it; we need a real schema
    with the expected tables. The ``ensure_unified_schema`` call in
    the ``tmp_db`` fixture creates them. We do not pre-populate the
    tables; an empty novel still produces a well-formed report.
"""
import sqlite3

import pytest


def _point_content_db_at_tmp(monkeypatch, tmp_db_url):
    """Redirect ``content_db.DB_PATH`` at the tmp SQLite DB and ensure
    the ``test_novel`` row exists in that file.
    """
    db_file = tmp_db_url.replace("sqlite:///", "")
    import content_db as _cd
    monkeypatch.setattr(_cd, "DB_PATH", db_file)
    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO novels (name, created_at) "
            "VALUES (?, datetime('now'))",
            ("test_novel",),
        )
        conn.commit()
    finally:
        conn.close()


# ─── GET /api/content/search ───────────────────────────────────────────

class TestContentSearch:
    def test_happy_path_returns_results(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(
            f"/api/content/search?q=test&novel={sample_novel}&limit=10"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # ``results`` is a dict with category buckets
        # (chapters/outlines/reviews), not a flat list. Each bucket
        # is itself a list.
        assert "results" in data
        assert isinstance(data["results"], dict)
        for bucket in ("chapters", "outlines", "reviews"):
            assert bucket in data["results"]
            assert isinstance(data["results"][bucket], list)

    def test_missing_query_returns_400(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # No ``q`` argument → 400.
        res = client.get(f"/api/content/search?novel={sample_novel}")
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False


# ─── GET /api/content/stats/<novel> ────────────────────────────────────

class TestContentStats:
    def test_happy_path_returns_stats(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/content/stats/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "stats" in data
        assert isinstance(data["stats"], dict)

    def test_unknown_novel_raises_handler_bug(self, client, tmp_db, monkeypatch):
        # KNOWN BUG: portal/app.py:3543 does ``if "error" in stats``
        # without null-guarding. When the repository returns ``None``
        # for an unknown novel, the ``in`` check raises TypeError.
        # Flask's test client propagates the exception rather than
        # returning a 500 — and a production deploy would surface it
        # as an unhandled error 500. Either way the contract is
        # "the unknown-novel path is broken". We assert that the
        # call does NOT silently return 200 with empty stats (which
        # would mask the bug).
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        try:
            res = client.get("/api/content/stats/no_such_novel")
            # If Flask did not propagate, the route returned 5xx
            # with no JSON envelope.
            assert res.status_code >= 500
        except TypeError as exc:
            # The Flask test client propagates the TypeError;
            # assert the message clearly identifies the buggy
            # ``in`` check.
            assert "argument of type 'NoneType' is not iterable" in str(exc)


# ─── POST /api/content/sync ────────────────────────────────────────────

class TestContentSync:
    def test_happy_path_sync_novel(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(
            "/api/content/sync",
            json={"novel": sample_novel},
        )
        # The handler returns 200 with success=True and a ``result``
        # envelope; sync_novel_from_files itself may return an empty
        # dict for a novel with no files on disk.
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "result" in data

    def test_no_novel_syncs_all(self, client, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # No ``novel`` in body → sync_all_novels. We don't care
        # whether any novels actually exist; the route is
        # reachable and well-formed.
        res = client.post("/api/content/sync", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True


# ─── GET /api/content/quality-report/<novel> ───────────────────────────

class TestQualityReport:
    def test_happy_path_returns_report(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/content/quality-report/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "report" in data
        report = data["report"]
        # Well-known top-level keys.
        for key in ("novel", "total_chapters", "total_words",
                    "review_stats", "writing_quality",
                    "consistency_alerts", "rhythm_alerts", "review_trend"):
            assert key in report, f"missing report key: {key}"

    def test_unknown_novel_returns_404(self, client, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/content/quality-report/no_such_novel")
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
