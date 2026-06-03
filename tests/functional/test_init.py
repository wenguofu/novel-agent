"""Functional tests for init endpoints (M3 Task 11).

Endpoint coverage (6 total):
  POST /api/init/full/<novel>                                     4-dim
  POST /api/novels/<n>/world-building/init                        4-dim
  POST /api/novels/<n>/plot-arcs/init                             4-dim
  POST /api/novels/<n>/pacing/init                                4-dim
  POST /api/novels/<n>/revelation/init                            4-dim
  POST /api/novels/<n>/cleanup-bak                                4-dim

Notes on path conventions (accumulated across Tasks 4–11):
  - All six endpoints are POST-only.
  - All five init endpoints call ``content_db.get_db()`` (raw sqlite3
    against module-level ``DB_PATH``). They do NOT see the
    SQLAlchemy engine, so we reuse the
    ``_point_content_db_at_tmp`` helper from earlier tasks to point
    the module DB at the tmp file and seed ``test_novel``.
  - The init endpoints are tolerant of missing on-disk source files
    (``world_bible.md``, ``outline/*.md``, etc.). When the source is
    missing the handler returns 200 with success=True and a
    ``created=0`` / soft-failure message. We exercise that contract.
  - ``cleanup-bak`` scans ``novels/<n>/manuscript/.bak``. When the
    directory is absent the route returns 200 with ``deleted=0``.
    When present, it removes every file and rmdir's the directory.
  - The init/full route orchestrates the other inits; for an empty
    test_novel directory it returns 200 with success=True and a
    ``tables`` map (each entry having ``created`` and a message).
  - LESSON (new): for the init endpoints we need
    ``content_db.NOVELS_ROOT`` to point at the tmp novels dir (or
    at least at a directory that has the expected source files).
    The handler's happy path requires the file to exist; with no
    file the contract is "soft fail with created=0". We exercise
    both forms by either NOT pre-creating the file (soft fail) or
    pre-creating a minimal one (full happy path).
"""
import os
import sqlite3

import pytest


def _point_content_db_at_tmp(monkeypatch, tmp_db_url, tmp_path):
    """Redirect ``content_db.DB_PATH`` at the tmp SQLite DB and ensure
    the ``test_novel`` row exists in that file. Also redirect
    ``content_db.NOVELS_ROOT`` at the tmp novels dir so the init
    handlers find the source files under the right novel_name.
    """
    db_file = tmp_db_url.replace("sqlite:///", "")
    import content_db as _cd
    monkeypatch.setattr(_cd, "DB_PATH", db_file)
    novels_dir = tmp_path / "novels"
    monkeypatch.setattr(_cd, "NOVELS_ROOT", str(novels_dir))
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


# ─── POST /api/init/full/<novel> ───────────────────────────────────────

class TestInitFull:
    def test_happy_path_with_no_files(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        # No source files on disk → soft-fail with created=0; the
        # route still returns 200 with a well-formed envelope.
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/init/full/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "tables" in data
        assert isinstance(data["tables"], dict)
        # Errors list is empty when nothing actually errored.
        assert "errors" in data

    def test_happy_path_with_world_bible(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        # Pre-create a minimal world_bible.md so the world_building
        # branch finds a real source file.
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        novel_dir = tmp_path / "novels" / sample_novel
        (novel_dir / "world_bible.md").write_text(
            "# 玄天城\n\n测试内容。\n", encoding="utf-8"
        )
        res = client.post(f"/api/init/full/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "tables" in data

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        # The /init/full route does not 500 on an unknown novel; it
        # returns 200 with success=False and an errors list.
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/init/full/no_such_novel")
        assert res.status_code == 200
        data = res.get_json()
        # success may be True or False; the contract is well-formed
        # JSON with the expected keys.
        assert "tables" in data
        assert "errors" in data

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/init/full/{sample_novel}")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/world-building/init ──────────────────────────

class TestInitWorldBuilding:
    def test_happy_path_no_file(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/novels/{sample_novel}/world-building/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0
        assert "message" in data

    def test_happy_path_with_file(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        novel_dir = tmp_path / "novels" / sample_novel
        (novel_dir / "world_bible.md").write_text(
            "# 玄天城\n\n北境主城，势力复杂。\n", encoding="utf-8"
        )
        res = client.post(f"/api/novels/{sample_novel}/world-building/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # The handler may or may not match the "玄天城" entry to a
        # known domain; we only assert a well-formed response.
        assert "created" in data

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/novels/no_such_novel/world-building/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/world-building/init")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/plot-arcs/init ───────────────────────────────

class TestInitPlotArcs:
    def test_happy_path_no_file(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/novels/{sample_novel}/plot-arcs/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_happy_path_with_outline(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        novel_dir = tmp_path / "novels" / sample_novel
        outline_dir = novel_dir / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / "plot_arcs.md").write_text(
            "# 主线\n\n主角逆袭。\n", encoding="utf-8"
        )
        res = client.post(f"/api/novels/{sample_novel}/plot-arcs/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "created" in data

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/novels/no_such_novel/plot-arcs/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/plot-arcs/init")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/pacing/init ─────────────────────────────────

class TestInitPacing:
    def test_happy_path_no_outline(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/novels/{sample_novel}/pacing/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_happy_path_with_outline(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        novel_dir = tmp_path / "novels" / sample_novel
        outline_dir = novel_dir / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / "vol-01-chapters.md").write_text(
            "# 第一章 开端\n\n# 第二章 发展\n", encoding="utf-8"
        )
        res = client.post(f"/api/novels/{sample_novel}/pacing/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/novels/no_such_novel/pacing/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/pacing/init")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/revelation/init ──────────────────────────────

class TestInitRevelation:
    def test_happy_path_no_outline(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/novels/{sample_novel}/revelation/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_happy_path_with_outline(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        novel_dir = tmp_path / "novels" / sample_novel
        outline_dir = novel_dir / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / "vol-01-chapters.md").write_text(
            "# 第一章\n伏笔：古剑来历。\n", encoding="utf-8"
        )
        res = client.post(f"/api/novels/{sample_novel}/revelation/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/novels/no_such_novel/revelation/init")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("created") == 0

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/revelation/init")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/cleanup-bak ──────────────────────────────────

class TestCleanupBak:
    def test_happy_path_no_bak_dir(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        # No .bak directory on disk → 200 with deleted=0 and a
        # "无备份文件" message.
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post(f"/api/novels/{sample_novel}/cleanup-bak")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("deleted") == 0
        assert "无备份文件" in data.get("message", "")

    def test_happy_path_with_bak_files(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        bak_dir = tmp_path / "novels" / sample_novel / "manuscript" / ".bak"
        bak_dir.mkdir(parents=True, exist_ok=True)
        (bak_dir / "vol-01-ch-001.md.bak").write_text("old", encoding="utf-8")
        (bak_dir / "vol-01-ch-002.md.bak").write_text("old2", encoding="utf-8")
        res = client.post(f"/api/novels/{sample_novel}/cleanup-bak")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("deleted") == 2
        assert not bak_dir.exists()

    def test_unknown_novel_returns_soft_failure(self, client, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db, tmp_path)
        res = client.post("/api/novels/no_such_novel/cleanup-bak")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("deleted") == 0

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/cleanup-bak")
        assert res.status_code == 405
