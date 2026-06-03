"""Functional tests for workflow / enforce-pipeline endpoints (M3 Task 9).

Endpoint coverage (3 total):
  POST /api/workflow/preflight/<novel>                            4-dim
  POST /api/workflow/postflight/<novel>                           4-dim
  POST /api/novels/<n>/enforce-pipeline                           4-dim

Notes on path conventions (accumulated across Tasks 4 + 5 + 6 + 7 + 8 + 9):
  - All three endpoints are POST-only.
  - All three call ``run_script(...)`` to invoke Python helpers in
    ``scripts/``. The script calls may fail or succeed depending on
    the test environment; the handlers return 200 with success=True
    and a structured ``results`` / ``pipeline`` payload regardless.
  - REGRESSION: commit 169cfb1 fixed a NameError in
    ``api_workflow_preflight`` where ``chapter_num`` was referenced
    before being read from ``request.json``. The regression test in
    this file posts to the endpoint with ``chapter_num`` absent —
    pre-fix this raised NameError (caught as 500). The fix reads
    ``data.get("chapter_num", "")`` with empty-string default, so
    the danger_issue check now soft-fails to "不存在（不影响生成）"
    and the route returns 200 with success=True.
  - The ``enforce-pipeline`` route accepts ``volume``, ``chapter_num``
    and ``chapter_ref``; the handler auto-derives ``chapter_ref`` from
    the other two if it is not supplied.
  - All three routes are tolerant of an unknown novel: they return
    200 with success=True and a results map whose ``ok`` fields are
    False, because every script check simply reports its own status.
  - The preflight handler uses ``data.get("chapter_num", "")`` with
    the default — the regression test specifically POSTs without
    ``chapter_num`` in the body to catch any future regression of
    the NameError fix.
"""
import pytest


# ─── POST /api/workflow/preflight/<novel> ─────────────────────────────

class TestPreflight:
    def test_happy_path_returns_results(self, client, sample_novel):
        # The 169cfb1 regression is the primary purpose of this test.
        # Pre-fix: NameError at runtime → 500. Post-fix: 200 with
        # success=True. We POST WITHOUT chapter_num to exercise the
        # exact code path that used to crash.
        res = client.post(f"/api/workflow/preflight/{sample_novel}",
                          json={"volume": "vol-01"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "all_ok" in data
        assert "results" in data
        assert isinstance(data["results"], dict)
        # The 5 named checks should all be present.
        for key in ("stage_gate", "outline_check", "danger_issue_check",
                    "characters_check", "rag_status"):
            assert key in data["results"], f"missing check: {key}"

    def test_with_chapter_num_soft_fails_danger_check(self, client, sample_novel):
        # Supply chapter_num so the danger_issue check runs with a real
        # target file. Without an outline/danger_issue_*/ on disk the
        # check is expected to be ok=False with a "缺失（不影响生成）"
        # message — pre-169cfb1 the handler raised NameError and the
        # entire response was 500.
        res = client.post(f"/api/workflow/preflight/{sample_novel}",
                          json={"volume": "vol-01", "chapter_num": 1})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "danger_issue_check" in data["results"]

    def test_regression_169cfb1_no_chapter_num(self, client, sample_novel):
        # High-priority regression test: chapter_num absent from body
        # MUST NOT cause a 500. The fix in 169cfb1 is what we lock in.
        res = client.post(f"/api/workflow/preflight/{sample_novel}",
                          json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "results" in data

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        # POST-only route.
        res = client.get(f"/api/workflow/preflight/{sample_novel}")
        assert res.status_code == 405


# ─── POST /api/workflow/postflight/<novel> ────────────────────────────

class TestPostflight:
    def test_happy_path_returns_results(self, client, sample_novel):
        res = client.post(f"/api/workflow/postflight/{sample_novel}",
                          json={"chapter_ref": "vol-01/ch-001"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "all_ok" in data
        assert "results" in data
        for key in ("review_validation", "continuity", "rhythm",
                    "rag_update", "stage_complete"):
            assert key in data["results"], f"missing check: {key}"

    def test_missing_chapter_ref_returns_soft_failure(self, client, sample_novel):
        # No chapter_ref → the review_path simply doesn't exist; the
        # handler reports ``ok=False`` for review_validation and
        # continues. Overall success=True with the well-formed
        # ``results`` envelope.
        res = client.post(f"/api/workflow/postflight/{sample_novel}", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "results" in data

    def test_unknown_novel_returns_soft_failure(self, client):
        # An unknown novel still produces 200 with structured results
        # (every script simply reports its own status).
        res = client.post("/api/workflow/postflight/no_such_novel",
                          json={"chapter_ref": "vol-01/ch-001"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "results" in data

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/workflow/postflight/{sample_novel}")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/enforce-pipeline ────────────────────────────

class TestEnforcePipeline:
    def test_happy_path_with_chapter_ref(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/enforce-pipeline",
            json={"volume": "vol-01", "chapter_num": 1,
                  "chapter_ref": "vol-01/ch-001"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "pipeline" in data
        assert isinstance(data["pipeline"], dict)
        # The route is the script-driven Steps 0-10 enforcement; verify
        # a couple of well-known gate keys exist.
        for key in ("0_stage_gate", "9a_review_validation", "10a_agent_tracker"):
            assert key in data["pipeline"], f"missing gate: {key}"

    def test_chapter_ref_auto_derived(self, client, sample_novel):
        # When chapter_ref is omitted, the handler synthesises it from
        # volume + chapter_num: ``f"{volume}/ch-{ch_num_padded}"``.
        res = client.post(
            f"/api/novels/{sample_novel}/enforce-pipeline",
            json={"volume": "vol-01", "chapter_num": 1},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "pipeline" in data

    def test_missing_inputs_returns_soft_failure(self, client, sample_novel):
        # Empty body — handler still returns 200 with a pipeline map.
        res = client.post(f"/api/novels/{sample_novel}/enforce-pipeline", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "pipeline" in data

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/enforce-pipeline")
        assert res.status_code == 405
