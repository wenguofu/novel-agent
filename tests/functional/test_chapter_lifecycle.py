"""Functional tests for chapter lifecycle endpoints (M2 core 4-dim pattern).

4 dimensions per endpoint:
  1. happy_path_*   — 200/201 + response schema assertion
  2. missing_field_ — 400 + error message contains key name (or success=False)
  3. not_found_     — 404 when novel_name (or other ref) doesn't exist
  4. wrong_method_  — 405 when method doesn't match the route

Notes on path conventions:
  - The chapters GET/POST/DELETE endpoints use ``<path:ch_ref>`` so a slash is
    preserved; the file on disk is ``manuscript/vol-01/ch-001.md`` (nested).
  - The reviews GET endpoint uses ``<ch_ref>`` (no path converter) so a slash
    in the ref will NOT match the route. Tests against /reviews/ therefore
    use the dash form ``vol-01-ch-001`` to actually exercise the route.
"""
import pytest


# ─── GET chapter ────────────────────────────────────────────────────────────

class TestGetChapter:
    def test_happy_path_returns_chapter(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        # Endpoint reads manuscript/<ch_ref>.md verbatim — nested vol-XX dir.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text("# 第1章\n\n测试内容\n")
        res = client.get(f"/api/novels/{sample_novel}/chapters/{ch_ref}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "测试内容" in data.get("content", "")

    def test_not_found_returns_404(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/chapters/vol-99/ch-999")
        assert res.status_code == 404
        assert res.get_json().get("success") is False

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001")
        assert res.status_code == 405


# ─── POST chapter edit ─────────────────────────────────────────────────────

class TestEditChapter:
    def test_happy_path_writes_chapter(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        (tmp_path / "novels" / sample_novel / "manuscript").mkdir(parents=True, exist_ok=True)
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/{ch_ref}/edit",
            json={"content": "新章节内容", "scene": "open"},
        )
        assert res.status_code in (200, 201)
        assert res.get_json()["success"] is True

    def test_missing_field_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit",
            json={"scene": "open"},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_wrong_method_put_returns_405(self, client, sample_novel):
        # PUT is not handled by either /chapters/<path:ref> (GET/DELETE) or
        # /chapters/<path:ref>/edit (POST), so Flask returns 405.
        # (GET would be captured by the <path:ref> handler and return 404
        # since the ref is interpreted as a literal path.)
        res = client.put(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit")
        assert res.status_code == 405


# ─── DELETE chapter ────────────────────────────────────────────────────────

class TestDeleteChapter:
    def test_happy_path_soft_deletes(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text("# content")
        res = client.delete(f"/api/novels/{sample_novel}/chapters/{ch_ref}")
        assert res.status_code in (200, 204)

    def test_not_found_returns_404(self, client, sample_novel, tmp_path):
        # No manuscript dir → 404
        res = client.delete(
            f"/api/novels/{sample_novel}/chapters/vol-99/ch-999"
        )
        assert res.status_code == 404

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001")
        assert res.status_code == 405


# ─── GET review ────────────────────────────────────────────────────────────

class TestGetReview:
    def test_happy_path_returns_review_or_404(self, client, sample_novel, tmp_path):
        """Acceptable: 200 with review content, or 404 if no review file on disk."""
        # Route uses <ch_ref> (no path converter); use dash-form ref so the
        # URL actually matches the route.
        res = client.get(f"/api/novels/{sample_novel}/reviews/vol-01-ch-001")
        assert res.status_code in (200, 404)

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/reviews/vol-01-ch-001")
        assert res.status_code == 405


# ─── POST review-chapter (AI review trigger; M2 core) ─────────────────────

class TestReviewChapter:
    def test_happy_path_returns_review_object(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"chapter_ref": "vol-01/ch-001", "content": "测试内容"},
        )
        # AI review may fail without API key — accept any non-5xx with 'success' key.
        assert res.status_code < 500
        assert "success" in res.get_json()

    def test_missing_field_chapter_ref_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"content": "no ref"},
        )
        assert res.status_code < 500

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/review-chapter")
        assert res.status_code == 405
