"""Functional tests for content search / stats / sync / quality-report
endpoints (M3 Task 14; M3.1 W3-T3.2 4-dim upgrade).

Endpoint coverage:
  GET  /api/content/search?q=                                    3-dim
    (search always returns 200; not_found dim is N/A — a query
    with no matches is success=True with empty results, not 404)
  GET  /api/content/stats/<novel>                                3-dim
    (novel is a path segment; missing_field dim is N/A)
  POST /api/content/sync                                         4-dim
    (empty body is valid → sync_all; not_found for an unknown
    novel is reported as success=True with error in the result
    envelope, NOT as 404)
  GET  /api/content/quality-report/<novel>                       3-dim
    (novel is a path segment; missing_field dim is N/A)

Notes on path conventions (accumulated across Tasks 4–14, M3.1):
  - All four endpoints are read-/sync-oriented; the only POST is
    ``/api/content/sync`` (no body required).
  - These endpoints all delegate to ``content_db`` helpers
    (``search_all``, ``get_novel_stats``, ``sync_novel_from_files``,
    ``sync_all_novels``) which use raw sqlite3 against
    ``content_db.DB_PATH``. The shared
    ``_helpers.point_content_db_at_tmp`` helper redirects the
    module at the tmp DB and seeds a minimal ``novels`` row.
  - ``/api/content/search`` requires ``q``; missing → 400.
  - ``/api/content/stats/<novel>`` returns 404 with success=False
    when the novel row does not exist (M3.1 W1 null-guard hotfix;
    full 4-dim coverage lives here per M3.1 W3-T3.2).
  - ``/api/content/sync`` accepts ``novel`` in the body; when
    present, syncs that novel; otherwise calls ``sync_all_novels()``.
    An unknown novel does NOT 404 — the route returns 200 with
    ``success=True`` and an ``error`` key inside ``result``.
  - ``/api/content/quality-report`` runs several aggregate queries
    against the content DB and returns a structured report.
  - ``/api/content/quality-report`` uses a raw sqlite3 connection
    via ``content_db.get_db()`` and queries ``chapters``,
    ``reviews``, etc. directly. The ``ensure_unified_schema`` call
    in the ``tmp_db`` fixture creates them. We do not pre-populate
    the tables; an empty novel still produces a well-formed report.
"""
import pytest

from _helpers import (
    assert_missing_field,
    assert_not_found,
    assert_wrong_method_405,
    point_content_db_at_tmp,
)


# ─── GET /api/content/search ───────────────────────────────────────────

class TestContentSearch:
    def test_happy_path_returns_results(self, client, sample_novel, tmp_db, monkeypatch):
        point_content_db_at_tmp(monkeypatch, tmp_db)
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
        point_content_db_at_tmp(monkeypatch, tmp_db)
        # No ``q`` argument → 400. The handler returns a Chinese
        # error message ("请提供查询词") and does NOT echo the missing
        # field name, so the helper's best-effort field-name check
        # is skipped here.
        res = client.get(f"/api/content/search?novel={sample_novel}")
        assert_missing_field(res)

    def test_wrong_method_post_returns_405(self, client, sample_novel, tmp_db, monkeypatch):
        # /api/content/search only accepts GET. POST → 405.
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(
            f"/api/content/search?q=test&novel={sample_novel}",
        )
        assert_wrong_method_405(res)


# ─── GET /api/content/stats/<novel> ────────────────────────────────────

class TestContentStats:
    def test_happy_path_returns_stats(self, client, sample_novel, tmp_db, monkeypatch):
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/content/stats/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "stats" in data
        assert_success_envelope_local(res)

    def test_not_found_returns_404(self, client, tmp_db, monkeypatch):
        # Unknown novel → 404 (regression for the M3.1 W1 null-guard
        # hotfix that converted an internal TypeError → 500 into a
        # structured 404 response).
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/content/stats/no_such_novel_xyz")
        assert_not_found(res)

    def test_wrong_method_post_returns_405(self, client, sample_novel, tmp_db, monkeypatch):
        # /api/content/stats/<novel> only accepts GET. POST → 405.
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(f"/api/content/stats/{sample_novel}")
        assert_wrong_method_405(res)


# ─── POST /api/content/sync ────────────────────────────────────────────

class TestContentSync:
    def test_happy_path_sync_novel(self, client, sample_novel, tmp_db, monkeypatch):
        point_content_db_at_tmp(monkeypatch, tmp_db)
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

    def test_not_found_novel_returns_error_in_result(self, client, tmp_db, monkeypatch):
        # Unknown novel does NOT 404 — the route returns 200 with
        # success=True and an error embedded in ``result`` (the
        # underlying ``sync_novel_from_files`` returns
        # ``{"error": "小说目录不存在: ..."}``). This is the
        # documented behaviour; the test pins it down.
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(
            "/api/content/sync",
            json={"novel": "no_such_novel_xyz"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "result" in data
        # Result envelope reports the directory-missing error.
        assert "error" in data["result"], \
            f"expected 'error' in result, got {data['result']!r}"

    def test_wrong_method_get_returns_405(self, client, tmp_db, monkeypatch):
        # /api/content/sync only accepts POST. GET → 405.
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/content/sync")
        assert_wrong_method_405(res)


# ─── GET /api/content/quality-report/<novel> ───────────────────────────

class TestQualityReport:
    def test_happy_path_returns_report(self, client, sample_novel, tmp_db, monkeypatch):
        point_content_db_at_tmp(monkeypatch, tmp_db)
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
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get("/api/content/quality-report/no_such_novel")
        assert_not_found(res)

    def test_wrong_method_post_returns_405(self, client, sample_novel, tmp_db, monkeypatch):
        # /api/content/quality-report/<novel> only accepts GET. POST → 405.
        point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(f"/api/content/quality-report/{sample_novel}")
        assert_wrong_method_405(res)


# ─── Local helper ──────────────────────────────────────────────────────
# The 3-dim test_happy_path_returns_stats in TestContentStats above
# uses assert_success_envelope, but the route returns the success key
# nested inside ``data["success"]`` — we just want to assert the
# envelope contract is present.  We could import assert_success_envelope
# from _helpers, but doing so would add a no-op assert on top of the
# already-present success=True check; instead we use a tiny local
# alias for clarity.

def assert_success_envelope_local(res):
    """Local alias: assert the response carries a JSON ``success`` key."""
    assert "success" in (res.get_json() or {}), \
        f"missing 'success' key in response: {res.get_data(as_text=True)!r}"
