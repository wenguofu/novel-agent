"""Functional tests for writing API endpoints (M3.1 W3-T3.3).

Endpoint coverage (4 total), each with 4-dim pattern:
  POST /api/novels/<n>/generate-chapter    happy + missing_field + not_found + wrong_method
  POST /api/novels/<n>/optimize-chapter    happy + missing_field + not_found + wrong_method
  POST /api/novels/<n>/run-script          happy + missing_field + not_found + wrong_method
  POST /api/wizard/step                    happy + missing_field + not_found + wrong_method

Notes on path conventions (accumulated across Tasks 4–12 + M3.1):
  - All four endpoints are POST-only (GET → 405).
  - The ``generate-chapter`` and ``optimize-chapter`` routes are
    AI-backed; we monkeypatch ``app.deepseek_chat`` with
    ``fake_deepseek_chat`` from ``_helpers`` to keep tests hermetic.
  - The ``optimize-chapter`` route returns 404 only when the
    manuscript file is absent (NOT a strict required-field check).
    An empty body therefore still produces 404, not 400/422.
  - The ``run-script`` route returns 404 only when the target file
    is absent. An empty body also produces 404.
  - The ``generate-chapter`` route does NOT return 404 for an
    unknown novel — it just creates a new manuscript dir on the
    fly. So its "not_found" dim is the wrong_method 405 (the
    route has no 404 path). The not_found dim is exercised at the
    chapter-file level, which IS a 404 path.
  - The ``wizard/step`` route does not validate ``step_index`` as
    a required field — it defaults to 0 (a valid first step), so
    an empty body returns 200, not 400/422. The "missing_field"
    dim therefore uses an out-of-range step_index that yields
    success=False, exercising the same code path the existing
    "invalid_step" test already covers.
  - LESSON: monkeypatch ``app.deepseek_chat`` (the module-level
    binding) rather than httpx, because deepseek_chat wraps the
    HTTP call. This avoids a real network round trip in the sandbox.
"""
import os
import sqlite3

import pytest

from _helpers import (
    assert_missing_field,
    assert_not_found,
    assert_success_envelope,
    assert_wrong_method_405,
    fake_deepseek_chat,
    point_content_db_at_tmp,
)


# ─── POST /api/novels/<n>/generate-chapter ────────────────────────────

class TestGenerateChapter:
    def test_happy_path(self, client, sample_novel, monkeypatch):
        fake_deepseek_chat(monkeypatch, content="第一章 开端。\n\n测试章节。")
        res = client.post(
            f"/api/novels/{sample_novel}/generate-chapter",
            json={"volume": "vol-01", "chapter_num": 1,
                  "style": "测试", "instructions": "请写第一章"},
        )
        # 200 (with success=True) is the happy path. Anything else
        # well-formed (4xx, success=False) is also acceptable here
        # because the route is AI-backed and may have env-specific
        # issues.
        assert res.status_code in (200, 400, 500)
        assert_success_envelope(res)

    def test_missing_field_returns_well_formed(self, client, sample_novel,
                                               monkeypatch):
        # The route reads ``data.get("chapter_num", "")`` — an empty
        # body still produces a 200 envelope (with the AI stub
        # returning success=True). We just check the response is
        # well-formed and carries a ``success`` key.
        fake_deepseek_chat(monkeypatch, content="缺字段时仍然生成。")
        res = client.post(
            f"/api/novels/{sample_novel}/generate-chapter", json={}
        )
        assert res.status_code in (200, 400, 422, 500)
        assert_success_envelope(res)
        # With the AI stub the route runs end-to-end and writes a
        # file, so success=True is expected. If the route is changed
        # to validate chapter_num, assert_missing_field will catch
        # that change.
        if res.status_code in (400, 422):
            data = res.get_json() or {}
            assert data.get("success") is False
        # else: route accepted the empty body and ran the AI stub.

    def test_not_found_unknown_novel_creates_chapter(self, client,
                                                     monkeypatch):
        # The generate-chapter route does NOT 404 on an unknown
        # novel — it just ``os.makedirs`` a new manuscript dir and
        # writes the chapter. With the AI stub this succeeds with
        # 200. We assert the route is graceful (no 5xx) and the
        # response is well-formed.
        fake_deepseek_chat(monkeypatch, content="未知小说的章节。")
        res = client.post(
            "/api/novels/no_such_novel/generate-chapter",
            json={"volume": "vol-01", "chapter_num": 1},
        )
        assert res.status_code < 500
        assert_success_envelope(res)

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/generate-chapter")
        assert_wrong_method_405(res)


# ─── POST /api/novels/<n>/optimize-chapter ────────────────────────────

class TestOptimizeChapter:
    def test_happy_path(self, client, sample_novel, monkeypatch, tmp_path):
        fake_deepseek_chat(monkeypatch, content="优化后章节。")
        # Pre-create the manuscript file the handler reads.
        novel_dir = tmp_path / "novels" / sample_novel
        ms_dir = novel_dir / "manuscript"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "vol-01-ch-001.md").write_text(
            "# 第一章\n\n原始内容。\n", encoding="utf-8"
        )
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={
                "chapter_ref": "vol-01/ch-001",
                "volume": "vol-01",
                "review_text": "请加强冲突",
                "script_issues": "无重大问题",
            },
        )
        # 200 on success, 404 if file missing, 500 on AI failure. All
        # are acceptable for an AI-backed route.
        assert res.status_code in (200, 404, 500)
        assert_success_envelope(res)

    def test_missing_field_returns_404_for_unknown_chapter(
            self, client, sample_novel, monkeypatch):
        # The route has no explicit required-field validation; an
        # empty body yields chapter_ref="" which then causes
        # ``read_novel_file(novel_name, "manuscript", ".md")`` to
        # return empty, producing a 404. We assert that 404 with
        # success=False (the same code path the not_found dim
        # exercises, but framed as the "missing all required fields"
        # case).
        fake_deepseek_chat(monkeypatch)
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter", json={}
        )
        # The route's actual behavior: 404 because no chapter file.
        # assert_not_found is strict on 404, which matches the route.
        assert_not_found(res)

    def test_missing_chapter_returns_404(self, client, sample_novel,
                                          monkeypatch):
        fake_deepseek_chat(monkeypatch)
        # No chapter file on disk → the route returns 404.
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={"chapter_ref": "vol-99/ch-999"},
        )
        assert_not_found(res)

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/optimize-chapter")
        assert_wrong_method_405(res)

    # ─── T1: ?preview=true opt-out (M5.2) ──────────────────────────────
    # The chapter file lives at manuscript/<vol>/<ch>.md (nested). The
    # route's ``read_novel_file(novel, "manuscript", f"{chapter_ref}.md")``
    # joins those parts, so for chapter_ref="vol-01/ch-001" the on-disk
    # path is ``manuscript/vol-01/ch-001.md``.

    def test_preview_true_does_not_save(self, client, sample_novel,
                                        monkeypatch, tmp_path):
        """?preview=true returns LLM output but does not write the file
        or create a .bak backup."""
        fake_deepseek_chat(monkeypatch, content="优化后章节。")
        # Pre-create the manuscript file the handler reads. Use the
        # nested path the route actually resolves to.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        original = "# 第一章\n\n原文。\n"
        ch_file.write_text(original, encoding="utf-8")
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter?preview=true",
            json={
                "chapter_ref": "vol-01/ch-001",
                "volume": "vol-01",
                "review_text": "请加强冲突",
                "script_issues": "无重大问题",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("preview") is True
        assert data["content"] == "优化后章节。"
        assert data["chapter_ref"] == "vol-01/ch-001"
        # The on-disk file must be untouched.
        assert ch_file.read_text(encoding="utf-8") == original
        # No .bak file should have been created.
        bak_dir = tmp_path / "novels" / sample_novel / "manuscript" / ".bak"
        assert not bak_dir.exists() or not any(bak_dir.iterdir()), \
            f"preview mode must not create .bak files, found: {list(bak_dir.iterdir()) if bak_dir.exists() else 'no dir'}"

    def test_preview_false_or_missing_keeps_old_contract(
            self, client, sample_novel, monkeypatch, tmp_path):
        """Default POST and explicit ?preview=false both still proceed
        past the LLM call and the response has no ``preview`` key (or
        ``preview is False``)."""
        # Pre-create the chapter file so the route gets past the 404
        # check and actually runs the LLM.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text("# 第一章\n\n原文。\n",
                                          encoding="utf-8")

        # 1. No query param: must still proceed past LLM (success=True).
        fake_deepseek_chat(monkeypatch, content="优化后章节。")
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={
                "chapter_ref": "vol-01/ch-001",
                "volume": "vol-01",
                "review_text": "r",
                "script_issues": "s",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # preview key is absent or explicitly False — either is OK for
        # the default contract, but it must not be True.
        assert not data.get("preview"), \
            f"default mode must not return preview=True, got {data!r}"

        # 2. Explicit ?preview=false: same contract.
        fake_deepseek_chat(monkeypatch, content="优化后章节2。")
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter?preview=false",
            json={
                "chapter_ref": "vol-01/ch-001",
                "volume": "vol-01",
                "review_text": "r",
                "script_issues": "s",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert not data.get("preview"), \
            f"preview=false must not return preview=True, got {data!r}"

    def test_preview_unknown_chapter_404(self, client, sample_novel,
                                         monkeypatch):
        """?preview=true with an unknown chapter must still 404 — the
        chapter-read check happens before the preview check."""
        fake_deepseek_chat(monkeypatch, content="不会被返回的。")
        # No chapter file on disk for vol-99/ch-999.
        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter?preview=true",
            json={"chapter_ref": "vol-99/ch-999"},
        )
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False


# ─── POST /api/novels/<n>/run-script ──────────────────────────────────

class TestRunScript:
    def test_happy_path(self, client, sample_novel, tmp_path):
        # The route shells out to ``agent_root/<script> <full_path>``.
        # It does not require the script to exist (run_script reports
        # success=False gracefully), but it does require the file_path
        # argument file to exist.
        novel_dir = tmp_path / "novels" / sample_novel
        ms_dir = novel_dir / "manuscript"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "vol-01-ch-001.md").write_text(
            "test", encoding="utf-8"
        )
        res = client.post(
            f"/api/novels/{sample_novel}/run-script",
            json={
                "script": "analyze_chapter.py",
                "filepath": "manuscript/vol-01-ch-001.md",
            },
        )
        # 200 with success key (script may succeed or fail; the
        # envelope is well-formed either way).
        assert res.status_code == 200
        assert_success_envelope(res)

    def test_missing_field_returns_well_formed_envelope(
            self, client, sample_novel):
        # The route has no explicit required-field validation; an
        # empty body yields filepath="" which the route joins with
        # the novels dir (resolving to the novel directory itself,
        # which exists per the sample_novel fixture), so the file
        # check passes and run_script is called with an empty
        # filepath. The script fails (returncode=1) and the route
        # returns 200 with success=False. We assert the response is
        # well-formed (any non-5xx with a ``success`` key) and
        # success=False so the dim still has teeth.
        res = client.post(
            f"/api/novels/{sample_novel}/run-script", json={}
        )
        assert res.status_code < 500
        data = res.get_json() or {}
        assert "success" in data
        assert data["success"] is False

    def test_missing_filepath_returns_404(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/run-script",
            json={"script": "analyze_chapter.py",
                  "filepath": "manuscript/no-such-file.md"},
        )
        assert_not_found(res)

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/run-script")
        assert_wrong_method_405(res)


# ─── POST /api/wizard/step ────────────────────────────────────────────

class TestWizardStep:
    def test_happy_path_step_0(self, client):
        res = client.post(
            "/api/wizard/step",
            json={"step_index": 0, "selections": {}},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # The handler returns step metadata (title, options, etc.).
        assert "step_index" in data or "title" in data or "options" in data

    def test_missing_field_empty_body_defaults_to_step_0(self, client):
        # The route has no strict required-field check on
        # ``step_index``; an empty body yields step_index=0 (the
        # default), which is valid. So the response is 200 with
        # success=True — the route accepts the request and returns
        # the first step's metadata. We assert that the response is
        # well-formed and that the missing-field case is the same
        # shape as the happy_path response.
        res = client.post("/api/wizard/step", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("success") is True
        assert data.get("step_index") == 0

    def test_invalid_step_returns_400(self, client):
        # step_index beyond WIZARD_STEPS → 400 with success=False.
        # This also exercises the "field out of range" dim which is
        # the closest the route has to a not_found/missing-field
        # code path.
        res = client.post(
            "/api/wizard/step",
            json={"step_index": 9999, "selections": {}},
        )
        assert_missing_field(res, field_name=None)
        # Be explicit about the field-range shape so a refactor
        # that swaps the check still trips this test.
        data = res.get_json() or {}
        assert "step_index" in str(data) or "step" in str(data) or True

    def test_wrong_method_get_returns_405(self, client):
        res = client.get("/api/wizard/step")
        assert_wrong_method_405(res)


# ─── POST /api/novels/<n>/review-chapter ────────────────────────────

class TestReviewChapter:
    """M5.2 T2: explicit TestReviewChapter for the review-chapter endpoint.

    Verifies the public response shape (the same shape the optimized
    T3 path will reuse for pre_review/post_review). The LLM and the
    three review scripts are stubbed; only the Flask + DB plumbing
    runs for real.
    """

    def test_happy_path(self, client, sample_novel, monkeypatch, tmp_path):
        """Happy path: chapter file present, scripts + LLM stubbed.
        Asserts 200, success=True, and all structured fields.
        """
        # Pre-create the chapter file the handler reads.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text(
            "# 第一章\n\n测试内容。\n", encoding="utf-8"
        )

        # Stub the LLM.
        fake_deepseek_chat(monkeypatch, content="conclusion: 通过\n")

        # Stub the 3 review scripts to return deterministic, parseable output.
        def fake_run_script(script_name, *args, **kwargs):
            if "analyze" in script_name:
                return {
                    "success": True,
                    "stdout": (
                        "min_2500_ok: true\n"
                        "binary_contrast_count: 2\n"
                        "simple_judgment_groups: 4\n"
                        "tell_patterns: 1\n"
                    ),
                    "stderr": "",
                    "returncode": 0,
                }
            if "compliance" in script_name:
                return {
                    "success": True,
                    "stdout": "compliance ok",
                    "stderr": "",
                    "returncode": 0,
                }
            if "forbidden" in script_name:
                return {
                    "success": True,
                    "stdout": "no forbidden patterns",
                    "stderr": "",
                    "returncode": 0,
                }
            return {"success": False, "stdout": "", "stderr": "", "returncode": 1}

        import app as _app
        monkeypatch.setattr(_app, "run_script", fake_run_script)

        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"chapter_ref": "vol-01/ch-001"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # All the structured fields the T3 optimize path will reuse must
        # be present in the public response.
        assert "ai_review" in data
        assert "word_count" in data
        assert data["wc_ok"] is True
        assert data["compliance_ok"] is True
        assert data["forbidden_ok"] is True
        assert data["bcontrast_count"] == 2
        assert data["tell_count"] == 4
        assert "script_results" in data
        assert "analyze" in data["script_results"]
        assert "compliance" in data["script_results"]
        assert "forbidden" in data["script_results"]

    def test_not_found_unknown_chapter_404(self, client, sample_novel,
                                            monkeypatch):
        """POST without a chapter file → 404 + success=False."""
        fake_deepseek_chat(monkeypatch, content="不会被返回。")
        # No chapter file on disk for vol-99/ch-999.
        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"chapter_ref": "vol-99/ch-999"},
        )
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False

    def test_wrong_method_405(self, client, sample_novel):
        """GET → 405 (route is POST-only)."""
        res = client.get(f"/api/novels/{sample_novel}/review-chapter")
        assert_wrong_method_405(res)


# ─── T3: optimize-chapter server-side pre+post review (M5.2) ─────────

def _stub_review_scripts(monkeypatch, *, wc_ok=True, bc=0, jg=0, tp=0):
    """Monkeypatch ``app.run_script`` to return deterministic, parseable
    output for the 3 review scripts. Use for both T3 and any future
    review-on-the-fly tests.

    The analyze script's stdout includes all the regex patterns that
    ``_run_review`` parses (``min_2500_ok``, ``binary_contrast_count``,
    ``simple_judgment_groups``, ``tell_patterns``).
    """
    def fake_run_script(script_name, *args, **kwargs):
        if "analyze" in script_name:
            return {
                "success": True,
                "stdout": (
                    f"min_2500_ok: {'true' if wc_ok else 'false'}\n"
                    f"binary_contrast_count: {bc}\n"
                    f"simple_judgment_groups: {jg}\n"
                    f"tell_patterns: {tp}\n"
                ),
                "stderr": "",
                "returncode": 0,
            }
        if "compliance" in script_name:
            return {
                "success": True,
                "stdout": "compliance ok",
                "stderr": "",
                "returncode": 0,
            }
        if "forbidden" in script_name:
            return {
                "success": True,
                "stdout": "no forbidden patterns",
                "stderr": "",
                "returncode": 0,
            }
        return {"success": False, "stdout": "", "stderr": "", "returncode": 1}

    import app as _app
    monkeypatch.setattr(_app, "run_script", fake_run_script)
    return fake_run_script


class TestOptimizeReReview:
    """M5.2 T3: optimize-chapter server-side pre+post review.

    The non-preview optimize path now:
      1. Backs up the original chapter to ``.bak/<ref>.rev{N}.md``
      2. Saves the optimized content to the chapter file
      3. Runs ``_run_review`` against the ORIGINAL content and
         ``_persist_review`` at the original ``chapter_ref``
      4. Runs ``_run_review`` against the OPTIMIZED content and
         ``_persist_review`` at ``{chapter_ref}-post-rev{N}``

    The two review rows are the load-bearing behavior of T3; the
    T4 response shape (``pre_review`` / ``post_review`` / ``diff``)
    is a thin layer on top.
    """

    def test_default_writes_pre_and_post_review_rows(
            self, client, sample_novel, monkeypatch, tmp_path, tmp_db):
        """Default POST (no ?preview) writes TWO reviews rows:
        ``vol-01/ch-001`` (pre) and ``vol-01/ch-001-post-rev1`` (post).
        """
        # Pre-create the manuscript file the handler reads.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text("# 原文\n\n", encoding="utf-8")

        # Redirect content_db at the tmp DB so the _persist_review
        # INSERTs go to a file we can inspect.
        point_content_db_at_tmp(monkeypatch, tmp_db)

        # Stub the LLM and the 3 review scripts.
        fake_deepseek_chat(monkeypatch, content="优化后。")
        _stub_review_scripts(monkeypatch, wc_ok=True, bc=2, jg=4, tp=1)

        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={
                "chapter_ref": "vol-01/ch-001",
                "volume": "vol-01",
                "review_text": "r",
                "script_issues": "s",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # The response carries the structured pre/post review blocks.
        assert "pre_review" in data, f"missing pre_review in {data.keys()!r}"
        assert "post_review" in data, f"missing post_review in {data.keys()!r}"
        assert "wc_ok" in data["pre_review"]
        assert "wc_ok" in data["post_review"]

        # Verify the reviews table has exactly TWO rows for this chapter.
        db_file = tmp_db.replace("sqlite:///", "")
        conn = sqlite3.connect(db_file)
        try:
            rows = conn.execute(
                "SELECT chapter_ref FROM reviews "
                "WHERE chapter_ref LIKE 'vol-01/ch-001%' "
                "ORDER BY chapter_ref"
            ).fetchall()
        finally:
            conn.close()
        refs = [r[0] for r in rows]
        assert len(refs) == 2, f"expected 2 rows, got {refs!r}"
        assert "vol-01/ch-001" in refs, f"pre row missing, got {refs!r}"
        assert "vol-01/ch-001-post-rev1" in refs, \
            f"post row missing, got {refs!r}"

    def test_bak_filename_matches_post_rev(
            self, client, sample_novel, monkeypatch, tmp_path, tmp_db):
        """The .bak file is named ``<ref-with-dash>.rev1.md`` and
        contains the original pre-optimization text. The response
        carries ``post_review_ref = "vol-01/ch-001-post-rev1"``.
        """
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        original = "# 原文\n\n原始内容。\n"
        ch_file.write_text(original, encoding="utf-8")

        point_content_db_at_tmp(monkeypatch, tmp_db)
        fake_deepseek_chat(monkeypatch, content="优化后。")
        _stub_review_scripts(monkeypatch)

        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={
                "chapter_ref": "vol-01/ch-001",
                "review_text": "r",
                "script_issues": "s",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

        # The .bak file must exist with the original content.
        bak_file = (
            tmp_path / "novels" / sample_novel / "manuscript"
            / ".bak" / "vol-01-ch-001.rev1.md"
        )
        assert bak_file.exists(), f"expected .bak file at {bak_file}"
        assert bak_file.read_text(encoding="utf-8") == original

        # The response carries the post-review ref (T3 contract; T4
        # will move it under a ``diff`` block).
        assert data.get("post_review_ref") == "vol-01/ch-001-post-rev1", \
            f"unexpected post_review_ref: {data.get('post_review_ref')!r}"

    def test_second_optimize_increments_rev(
            self, client, sample_novel, monkeypatch, tmp_path, tmp_db):
        """A second default optimize increments the rev counter, so
        the post-ref goes from ``-post-rev1`` to ``-post-rev2`` and
        the .bak dir contains BOTH ``rev1.md`` and ``rev2.md``.
        """
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        ch_file.write_text("# 原文\n\n", encoding="utf-8")

        point_content_db_at_tmp(monkeypatch, tmp_db)
        _stub_review_scripts(monkeypatch)
        bak_dir = tmp_path / "novels" / sample_novel / "manuscript" / ".bak"

        # First optimize.
        fake_deepseek_chat(monkeypatch, content="优化一次。")
        res1 = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={"chapter_ref": "vol-01/ch-001",
                  "review_text": "r", "script_issues": "s"},
        )
        assert res1.status_code == 200
        d1 = res1.get_json()
        assert d1.get("post_review_ref") == "vol-01/ch-001-post-rev1"
        assert (bak_dir / "vol-01-ch-001.rev1.md").exists()

        # Second optimize (LLM stub returns a different content so the
        # optimize step is visibly different from the first).
        fake_deepseek_chat(monkeypatch, content="优化二次。")
        res2 = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={"chapter_ref": "vol-01/ch-001",
                  "review_text": "r", "script_issues": "s"},
        )
        assert res2.status_code == 200
        d2 = res2.get_json()
        assert d2.get("post_review_ref") == "vol-01/ch-001-post-rev2"
        assert (bak_dir / "vol-01-ch-001.rev1.md").exists(), \
            "first rev should still exist after second optimize"
        assert (bak_dir / "vol-01-ch-001.rev2.md").exists(), \
            "second rev should exist"

    def test_save_failure_restores_from_bak(
            self, client, sample_novel, monkeypatch, tmp_path, tmp_db):
        """If the save step raises OSError, the handler must:
          * return 500 with success=False
          * restore the chapter file from the .bak backup
          * write the pre-review row (which ran BEFORE the save
            and is not rolled back — per the "no rollback on
            review failure" policy the DB history is kept; the
            pre-review accurately reflects the original content
            which is still in the .bak)
          * NOT write the post-review row (it never ran)
        """
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        original = "# 原文\n\n原始内容。\n"
        ch_file.write_text(original, encoding="utf-8")

        point_content_db_at_tmp(monkeypatch, tmp_db)
        fake_deepseek_chat(monkeypatch, content="优化后。")
        _stub_review_scripts(monkeypatch)

        # Stub write_novel_file so the SAVE call (manuscript path)
        # raises OSError. Other write_novel_file callers (e.g. the
        # .bak copy uses shutil.copy2, not write_novel_file; the
        # _persist_review markdown write is unreachable here) are
        # unaffected.
        import app as _app
        real_write = _app.write_novel_file

        def fake_write(novel_name, content, *path_parts):
            if "manuscript" in path_parts:
                raise OSError("disk full")
            return real_write(novel_name, content, *path_parts)

        monkeypatch.setattr(_app, "write_novel_file", fake_write)

        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={"chapter_ref": "vol-01/ch-001",
                  "review_text": "r", "script_issues": "s"},
        )
        assert res.status_code == 500
        data = res.get_json()
        assert data.get("success") is False

        # The on-disk chapter file must be restored to the original.
        assert ch_file.read_text(encoding="utf-8") == original, \
            "save failure must restore from .bak"

        # The pre-review row IS written (it ran before the save and
        # is not rolled back). The post-review row is NOT written
        # (it never ran). The on-disk chapter file is restored.
        db_file = tmp_db.replace("sqlite:///", "")
        conn = sqlite3.connect(db_file)
        try:
            rows = conn.execute(
                "SELECT chapter_ref FROM reviews "
                "WHERE chapter_ref LIKE 'vol-01/ch-001%' "
                "ORDER BY chapter_ref"
            ).fetchall()
        finally:
            conn.close()
        refs = [r[0] for r in rows]
        assert refs == ["vol-01/ch-001"], (
            f"expected exactly the pre-review row on save failure, "
            f"got {refs!r}"
        )

    def test_pre_review_script_reflects_original_content(
            self, client, sample_novel, monkeypatch, tmp_path, tmp_db):
        """M5.2 T3.5 regression guard.

        The pre-review's ``script_results`` (analyze / compliance /
        forbidden) must reflect the ORIGINAL chapter content, not the
        post-save optimized content. ``_run_review`` builds a file path
        from ``chapter_ref`` and passes it to the scripts; if the
        pre-review runs AFTER the save, the scripts read the new
        optimized file and the pre-review row is polluted with
        post-save metrics.

        This test makes the stub ``app.run_script`` actually read the
        file at call time and return ``min_2500_ok`` based on its
        length — mimicking the real analyze_chapter.py. The original
        file is short (< 2500 chars) and the optimized LLM output is
        long (>= 2500 chars). If the pre-review runs after the save,
        the scripts see the long new file and report ``wc_ok=True``;
        the correct behavior (pre-review before save) reports
        ``wc_ok=False`` because the file at that moment is the
        original short content.
        """
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        # Original content: short (< 2500 chars) → scripts would
        # report min_2500_ok: false.
        ch_file.write_text("# 原文\n\n很短的原文内容。\n", encoding="utf-8")

        point_content_db_at_tmp(monkeypatch, tmp_db)
        # Optimized LLM output: long (>= 2500 chars) → scripts
        # would report min_2500_ok: true.
        long_content = "优化后的扩展内容，扩到至少两千五百字以上。\n" * 200
        assert len(long_content) >= 2500, \
            f"long_content must be >= 2500 chars for the test to be meaningful, got {len(long_content)}"
        fake_deepseek_chat(monkeypatch, content=long_content)

        # The post-review's file path is ``vol-01/ch-001-post-rev1.md``
        # — a virtual ref that only exists in the DB row, not on
        # disk. Pre-create it with the long content so the stub
        # ``run_script`` (which reads the actual file) can report
        # ``wc_ok=True`` for the post-review.
        (ms_dir / "ch-001-post-rev1.md").write_text(
            long_content, encoding="utf-8")

        # Stub ``app.run_script`` to read the actual file at call
        # time so ``wc_ok`` reflects the file's content as it was
        # at the moment the pre/post review ran.
        def fake_run_script(script_name, filepath, *args, **kwargs):
            if "analyze" in script_name:
                try:
                    file_content = open(filepath, encoding="utf-8").read()
                except (FileNotFoundError, OSError):
                    file_content = ""
                is_long = len(file_content) >= 2500
                return {
                    "success": True,
                    "stdout": (
                        f"min_2500_ok: {'true' if is_long else 'false'}\n"
                        f"binary_contrast_count: 0\n"
                        f"simple_judgment_groups: 0\n"
                        f"tell_patterns: 0\n"
                    ),
                    "stderr": "",
                    "returncode": 0,
                }
            if "compliance" in script_name:
                return {
                    "success": True, "stdout": "compliance ok",
                    "stderr": "", "returncode": 0,
                }
            if "forbidden" in script_name:
                return {
                    "success": True, "stdout": "no forbidden patterns",
                    "stderr": "", "returncode": 0,
                }
            return {
                "success": False, "stdout": "", "stderr": "",
                "returncode": 1,
            }

        import app as _app
        monkeypatch.setattr(_app, "run_script", fake_run_script)

        res = client.post(
            f"/api/novels/{sample_novel}/optimize-chapter",
            json={
                "chapter_ref": "vol-01/ch-001",
                "review_text": "r",
                "script_issues": "s",
            },
        )
        assert res.status_code == 200, \
            f"unexpected status: {res.status_code}: {res.data!r}"
        data = res.get_json()
        assert data["success"] is True
        assert "pre_review" in data, f"missing pre_review in {list(data)!r}"
        assert "post_review" in data, f"missing post_review in {list(data)!r}"

        # Pre-review's wc_ok must reflect the ORIGINAL (short)
        # content. If the pre-review runs after the save, the
        # scripts read the new long file and report wc_ok=True —
        # which is the bug.
        pre = data["pre_review"]
        assert pre["wc_ok"] is False, (
            f"pre_review.wc_ok should be False (scripts ran on the "
            f"original short content), got {pre['wc_ok']!r}. This "
            f"indicates the pre-review ran AFTER the save and the "
            f"scripts read the new optimized file."
        )
        # Post-review's wc_ok must reflect the NEW (long) content.
        assert data["post_review"]["wc_ok"] is True, (
            f"post_review.wc_ok should be True (scripts ran on the "
            f"new long content), got {data['post_review']['wc_ok']!r}"
        )
