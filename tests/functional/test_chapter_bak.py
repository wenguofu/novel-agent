"""Functional tests for chapter .bak history endpoints (architecture plan 1.1).

Covers the 4 new endpoints that power the Portal "历史" tab:
  - GET    /api/novels/<n>/chapters/<ch_ref>/bak
  - GET    /api/novels/<n>/chapters/<ch_ref>/bak/<filename>
  - POST   /api/novels/<n>/chapters/<ch_ref>/bak/<filename>/restore
  - DELETE /api/novels/<n>/chapters/<ch_ref>/bak/<filename>

The .bak filename pattern is ``<ref-with-dash>.rev{N}.md`` (e.g.
``vol-01-ch-001.rev1.md``), as written by the optimize-chapter
handler. The list endpoint filters by chapter_ref prefix so it only
returns that chapter's history.
"""
import os

import pytest


# ─── helpers ───────────────────────────────────────────────────────────────

def _make_bak_dir(tmp_path, novel_name):
    """Create the .bak directory and return the Path object."""
    bak = tmp_path / "novels" / novel_name / "manuscript" / ".bak"
    bak.mkdir(parents=True, exist_ok=True)
    return bak


def _write_bak(bak_dir, name, content, mtime=None):
    """Write a .bak file with optional mtime (epoch seconds) for ordering tests."""
    p = bak_dir / name
    p.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# ─── GET list ───────────────────────────────────────────────────────────────

class TestListChapterBak:
    def test_list_bak_returns_empty_when_no_backups(
            self, client, sample_novel):
        """Fresh chapter with no .bak directory → empty files list."""
        res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("files") == []

    def test_list_bak_returns_sorted_newest_first(
            self, client, sample_novel, tmp_path):
        """Pre-create 3 .bak files with distinct mtimes; list returns
        them in newest-first order."""
        bak = _make_bak_dir(tmp_path, sample_novel)
        _write_bak(bak, "vol-01-ch-001.rev1.md", "oldest",  mtime=1000)
        _write_bak(bak, "vol-01-ch-001.rev2.md", "middle",  mtime=2000)
        _write_bak(bak, "vol-01-ch-001.rev3.md", "newest",  mtime=3000)
        # A file for a different chapter must be ignored.
        _write_bak(bak, "vol-01-ch-002.rev1.md", "other",   mtime=4000)

        res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        files = data["files"]
        assert len(files) == 3, f"expected 3 files, got {files!r}"
        # Newest first
        revs = [f["rev"] for f in files]
        assert revs == [3, 2, 1], f"expected [3,2,1], got {revs!r}"
        # Schema sanity
        first = files[0]
        for key in ("filename", "rev", "size", "modified_at", "preview"):
            assert key in first, f"missing key {key!r} in {first!r}"
        assert first["filename"] == "vol-01-ch-001.rev3.md"
        assert first["rev"] == 3
        assert "newest" in first["preview"]


# ─── GET single file ────────────────────────────────────────────────────────

class TestGetChapterBak:
    def test_get_bak_returns_content(
            self, client, sample_novel, tmp_path):
        """Pre-create a bak with known content, GET returns it."""
        bak = _make_bak_dir(tmp_path, sample_novel)
        body = "# 原文\n\n这是历史版本内容。\n"
        _write_bak(bak, "vol-01-ch-001.rev1.md", body)

        res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"vol-01-ch-001.rev1.md"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("filename") == "vol-01-ch-001.rev1.md"
        assert data.get("content") == body


# ─── POST restore ───────────────────────────────────────────────────────────

class TestRestoreChapterBak:
    def test_restore_bak_copies_to_current(
            self, client, sample_novel, tmp_path):
        """Pre-create a bak, restore it, the current chapter file
        now matches the bak content."""
        # Set up: current chapter exists with different content.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        ch_file = ms_dir / "ch-001.md"
        ch_file.write_text("# 当前内容\n\n已被优化。\n", encoding="utf-8")

        # .bak contains the pre-optimize content.
        bak = _make_bak_dir(tmp_path, sample_novel)
        original = "# 原文\n\n优化前的版本。\n"
        _write_bak(bak, "vol-01-ch-001.rev1.md", original)

        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"vol-01-ch-001.rev1.md/restore"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("restored_from") == "vol-01-ch-001.rev1.md"

        # The on-disk chapter now matches the .bak content.
        assert ch_file.read_text(encoding="utf-8") == original


# ─── DELETE single ──────────────────────────────────────────────────────────

class TestDeleteChapterBak:
    def test_delete_bak_removes_file(
            self, client, sample_novel, tmp_path):
        """Pre-create a bak, delete it, list is empty."""
        bak = _make_bak_dir(tmp_path, sample_novel)
        _write_bak(bak, "vol-01-ch-001.rev1.md", "to-delete")

        res = client.delete(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"vol-01-ch-001.rev1.md"
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("deleted") == "vol-01-ch-001.rev1.md"
        assert not (bak / "vol-01-ch-001.rev1.md").exists()

        # List is now empty
        list_res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak"
        )
        assert list_res.get_json()["files"] == []


# ─── input validation ───────────────────────────────────────────────────────

class TestBakInputValidation:
    def test_bak_path_traversal_rejected(
            self, client, sample_novel, tmp_path):
        """Filenames with ``..`` or path separators are rejected with 400."""
        # ``../etc/passwd`` would escape the .bak dir; even when
        # url-encoded it must not match the safe pattern.
        res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"..%2Fetc%2Fpasswd"
        )
        # Flask url-decodes the path; check the decoded filename
        # fails the regex. Either 400 (rejected) or 404 (not found)
        # is acceptable — but it must NOT serve a file outside .bak.
        assert res.status_code in (400, 404), \
            f"expected 400/404, got {res.status_code}: {res.data!r}"

    def test_bak_get_rejects_non_matching_filename(
            self, client, sample_novel):
        """Filename that doesn't match ``<ref>.rev{N}.md`` is rejected."""
        res = client.get(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"not-a-bak-file.txt"
        )
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False

    def test_restore_bak_invalid_rev_returns_404(
            self, client, sample_novel, tmp_path):
        """A well-formed filename that doesn't exist on disk returns 404."""
        _make_bak_dir(tmp_path, sample_novel)
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"vol-01-ch-001.rev999.md/restore"
        )
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False

    def test_delete_bak_missing_returns_404(
            self, client, sample_novel, tmp_path):
        """Delete on a non-existent bak file returns 404."""
        _make_bak_dir(tmp_path, sample_novel)
        res = client.delete(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/bak/"
            f"vol-01-ch-001.rev1.md"
        )
        assert res.status_code == 404
        data = res.get_json()
        assert data["success"] is False
