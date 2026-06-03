"""Functional tests for outline / chapter-outlines / danger-issue endpoints (M3 Task 6).

Endpoint coverage (5 total):
  GET  /api/novels/<n>/outline/<vol_ref>                          4-dim
  POST /api/novels/<n>/outline/<vol_ref>/edit                     4-dim
  GET  /api/novels/<n>/chapter-outlines/<vol_ref>                 2-dim
  PUT  /api/novels/<n>/chapter-outlines/<vol_ref>/<int:ch_num>    4-dim
  GET  /api/novels/<n>/danger-issue/<vol_ref>/<ch_num>            2-dim

Notes on path conventions (accumulated across Tasks 4 + 5 + 6):
  - ``<novel_name>``, ``<vol_ref>``, ``<ch_num>`` are all default string
    converters; they DO NOT match slashes. Use plain segments like
    ``vol-01`` and ``ch-001`` (or a bare integer for ``<int:ch_num>``).
  - The outline GET endpoint reads ``outline/<vol_ref>-chapters.md`` and
    falls back to ``outline/<vol_ref>``; we pre-create the dashed-chapters
    file so the happy path succeeds.
  - The outline /edit endpoint WRITES ``<vol_ref>-chapters.yaml`` (not .md)
    and attempts a DB sync — non-YAML strings just log a warning and the
    route still returns 200, so a plain content body works for the happy
    path.
  - The PUT chapter-outline route uses ``<int:ch_num>``; non-numeric ch_num
    values do not match the route (the bare string variant catches it via
    the chapter-outlines GET handler). A safe 405 probe is to GET the
    integer URL — only PUT is registered for that path.
  - The danger-issue route requires the file at
    ``outline/danger_issue_<vol_ref>/danger_issue_<ch_padded>.md``.
    The handler computes ``filename = f"danger_issue_{ch_num.replace('ch-','')}.md"``,
    so passing ``ch_num=001`` lands on ``danger_issue_001.md``.
  - LESSON (new): ``content_db.get_db()`` uses a hard-coded module-level
    ``DB_PATH`` (``portal/content.db``), NOT ``DATABASE_URL``. Routes that
    delegate to ``content_db`` therefore bypass the tmp_db fixture's
    SQLAlchemy DB. Tests that exercise such routes must monkeypatch
    ``content_db.DB_PATH`` at the tmp DB and seed the ``test_novel`` row
    in that file so ``_get_novel_id`` succeeds.
"""
import os
import sqlite3

import pytest


def _point_content_db_at_tmp(monkeypatch, tmp_db_url):
    """Redirect ``content_db.DB_PATH`` at the tmp SQLite DB and ensure the
    ``test_novel`` row exists in that file.

    ``content_db.get_db()`` opens raw sqlite3 against its module-level
    ``DB_PATH`` (defaults to ``portal/content.db``). The shared ``tmp_db``
    fixture only seeds the SQLAlchemy engine — content_db is oblivious to
    it. This helper bridges the two so chapter-outline DB calls hit the
    tmp DB and find the seeded novel.
    """
    db_file = tmp_db_url.replace("sqlite:///", "")
    import content_db as _cd
    monkeypatch.setattr(_cd, "DB_PATH", db_file)
    # The tmp_db fixture already created the schema (including the
    # ``novels`` table) via ensure_unified_schema(); make sure
    # ``test_novel`` is present so ``_get_novel_id`` resolves.
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


# ─── GET /api/novels/<n>/outline/<vol_ref> ─────────────────────────────────

class TestReadOutline:
    def test_happy_path_returns_outline(self, client, sample_novel, tmp_path):
        # Endpoint reads outline/<vol_ref>-chapters.md (preferred) or
        # outline/<vol_ref> as a fallback. Pre-create the preferred form.
        outline_dir = tmp_path / "novels" / sample_novel / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / "vol-01-chapters.md").write_text(
            "# 卷一大纲\n\n章节1: 开端\n", encoding="utf-8"
        )
        res = client.get(f"/api/novels/{sample_novel}/outline/vol-01")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "卷一大纲" in data.get("content", "")

    def test_not_found_returns_404(self, client, sample_novel):
        # No outline file on disk → 404.
        res = client.get(f"/api/novels/{sample_novel}/outline/vol-99")
        assert res.status_code == 404
        assert res.get_json().get("success") is False

    def test_wrong_method_put_returns_405(self, client, sample_novel):
        # GET-only route; PUT is not registered on either /outline/<vol_ref>
        # (GET) or /outline/<vol_ref>/edit (POST). PUT therefore returns 405.
        res = client.put(f"/api/novels/{sample_novel}/outline/vol-01")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/outline/<vol_ref>/edit ───────────────────────────

class TestEditOutline:
    def test_happy_path_writes_outline(self, client, sample_novel, tmp_path):
        res = client.post(
            f"/api/novels/{sample_novel}/outline/vol-01/edit",
            json={"content": "chapters:\n  - number: 1\n    title: 测试章节\n"},
        )
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
        # Endpoint writes to outline/<vol_ref>-chapters.yaml on disk.
        written = (
            tmp_path / "novels" / sample_novel / "outline" / "vol-01-chapters.yaml"
        )
        assert written.exists()

    def test_missing_field_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/outline/vol-01/edit",
            json={},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_empty_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/outline/vol-01/edit",
            json={"content": ""},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        # The /edit route is POST-only; GET falls through to the parent
        # outline route only if the path matches, but /vol-01/edit doesn't
        # match the bare outline route (it has an extra segment). The
        # /edit handler returns 405 for GET.
        res = client.get(f"/api/novels/{sample_novel}/outline/vol-01/edit")
        assert res.status_code == 405


# ─── GET /api/novels/<n>/chapter-outlines/<vol_ref> ────────────────────────

class TestGetChapterOutlines:
    def test_happy_path_returns_chapters_list(
        self, client, sample_novel, tmp_db, monkeypatch
    ):
        # content_db uses its own DB_PATH (raw sqlite3) rather than the
        # SQLAlchemy engine; redirect both at the tmp DB.
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # Seed one chapter outline row so the response carries data.
        from content_db import upsert_chapter_outline
        upsert_chapter_outline(
            sample_novel,
            "vol-01",
            1,
            {
                "title": "第一章",
                "function": ["开端"],
                "core_events": "测试事件",
                "foreshadowing": [],
                "ending_hook": "悬念",
                "is_danger_scene": False,
                "word_count": 3000,
            },
        )
        res = client.get(f"/api/novels/{sample_novel}/chapter-outlines/vol-01")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("volume") == "vol-01"
        assert isinstance(data.get("chapters"), list)
        assert len(data["chapters"]) >= 1

    def test_empty_volume_returns_empty_list(
        self, client, sample_novel, tmp_db, monkeypatch
    ):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # No rows seeded for vol-99 → empty list, still 200/success.
        res = client.get(f"/api/novels/{sample_novel}/chapter-outlines/vol-99")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("chapters") == []

    def test_wrong_method_delete_returns_405(self, client, sample_novel):
        # The /chapter-outlines/<vol_ref> route is GET-only.
        res = client.delete(f"/api/novels/{sample_novel}/chapter-outlines/vol-01")
        assert res.status_code == 405


# ─── PUT /api/novels/<n>/chapter-outlines/<vol_ref>/<int:ch_num> ───────────

class TestPutChapterOutline:
    def test_happy_path_updates_outline(
        self, client, sample_novel, tmp_db, monkeypatch
    ):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.put(
            f"/api/novels/{sample_novel}/chapter-outlines/vol-01/2",
            json={
                "title": "第二章",
                "function": ["发展"],
                "core_events": "新事件",
                "foreshadowing": ["伏笔A"],
                "ending_hook": "新悬念",
                "is_danger_scene": True,
                "word_count": 3500,
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # Verify the row was persisted via the DB helper.
        from content_db import get_chapter_outline
        row = get_chapter_outline(sample_novel, "vol-01", 2)
        assert row is not None
        assert row.get("title") == "第二章"

    def test_unknown_novel_returns_error(
        self, client, sample_novel, tmp_db, monkeypatch
    ):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # The DB helper raises ValueError for an unknown novel; the route
        # catches it and returns 500 with success=False.
        res = client.put(
            "/api/novels/no_such_novel/chapter-outlines/vol-01/1",
            json={"title": "x"},
        )
        # Accept any 4xx/5xx that signals failure with success=False.
        assert res.status_code >= 400
        assert res.get_json().get("success") is False

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # The route is PUT-only; POST is not registered for this path.
        res = client.post(
            f"/api/novels/{sample_novel}/chapter-outlines/vol-01/1",
            json={"title": "x"},
        )
        assert res.status_code == 405


# ─── GET /api/novels/<n>/danger-issue/<vol_ref>/<ch_num> ──────────────────

class TestReadDangerIssue:
    def test_happy_path_returns_danger_issue(self, client, sample_novel, tmp_path):
        # Filename on disk is danger_issue_<ch_padded>.md inside
        # outline/danger_issue_<vol_ref>/. Handler strips a leading 'ch-'
        # from ch_num, so passing '001' directly yields filename
        # 'danger_issue_001.md'.
        di_dir = (
            tmp_path
            / "novels"
            / sample_novel
            / "outline"
            / "danger_issue_vol-01"
        )
        di_dir.mkdir(parents=True, exist_ok=True)
        (di_dir / "danger_issue_001.md").write_text(
            "# 危机点\n\n关键冲突。\n", encoding="utf-8"
        )
        res = client.get(
            f"/api/novels/{sample_novel}/danger-issue/vol-01/001"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "危机点" in data.get("content", "")

    def test_not_found_returns_404(self, client, sample_novel):
        # No danger-issue file on disk → 404.
        res = client.get(
            f"/api/novels/{sample_novel}/danger-issue/vol-99/999"
        )
        assert res.status_code == 404
        assert res.get_json().get("success") is False

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # GET-only route.
        res = client.post(
            f"/api/novels/{sample_novel}/danger-issue/vol-01/001"
        )
        assert res.status_code == 405
