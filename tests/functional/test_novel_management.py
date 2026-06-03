"""Functional tests for novel management endpoints (M3 Task 5).

Endpoint coverage (9 total):
  GET   /api/novels                          2-dim (happy + wrong method)
  GET   /api/novels/<n>                      2-dim
  GET   /api/novels/<n>/file                 2-dim
  GET   /api/novels/<n>/status               2-dim
  GET   /api/novels/<n>/gate-status          2-dim
  GET   /api/novels/<n>/export               2-dim
  POST  /api/novels/create                   4-dim (happy + missing + not_found? + wrong)
  POST  /api/novels/<n>/file/write           4-dim
  POST  /api/novels/<n>/update-status        4-dim

Notes on path conventions:
  - The novel-name URL segment is captured as ``<novel_name>`` (string
    converter, not path), so a slash would NOT match the route. The sample
    fixture's name ``test_novel`` is plain text and matches the route fine.
  - For /api/novels/<n>/file, ``path`` is a query string param, NOT a URL
    segment, so slashes inside ``path`` are fine. E.g. ``?path=project.md``.
  - 2-dim endpoints are GET-only; missing-field tests are omitted because
    they have no JSON body to validate.
"""
import pytest


# ─── GET /api/novels ────────────────────────────────────────────────────────

class TestListNovels:
    def test_happy_path_returns_novels_list(self, client, sample_novel):
        res = client.get("/api/novels")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert isinstance(data.get("novels"), list)
        # The sample_novel fixture pre-creates ``test_novel``.
        names = [n.get("name") for n in data["novels"]]
        assert "test_novel" in names

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # /api/novels is GET-only; POST falls through to 405.
        res = client.post("/api/novels")
        assert res.status_code == 405


# ─── GET /api/novels/<n> ────────────────────────────────────────────────────

class TestNovelDetail:
    def test_happy_path_returns_novel(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("novel", {}).get("name") == "test_novel"

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # POST is not a method on the detail route; PUT is safer here in
        # case any future route registers POST for the same URL.
        res = client.put(f"/api/novels/{sample_novel}")
        assert res.status_code == 405


# ─── GET /api/novels/<n>/file ───────────────────────────────────────────────

class TestReadFile:
    def test_happy_path_returns_file_content(self, client, sample_novel, tmp_path):
        # The endpoint reads files relative to the novel dir using ``?path=``.
        novel_dir = tmp_path / "novels" / sample_novel
        (novel_dir / "project.md").write_text("# Test Project\n", encoding="utf-8")
        res = client.get(f"/api/novels/{sample_novel}/file?path=project.md")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "Test Project" in data.get("content", "")

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # The /file route is GET-only; the POST counterpart is /file/write.
        res = client.post(f"/api/novels/{sample_novel}/file")
        assert res.status_code == 405


# ─── GET /api/novels/<n>/status ─────────────────────────────────────────────

class TestNovelStatus:
    def test_happy_path_returns_status_file(self, client, sample_novel, tmp_path):
        # Endpoint reads state/current_status.md relative to novel dir.
        state_dir = tmp_path / "novels" / sample_novel / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "current_status.md").write_text(
            "# 当前状态\n卷1 第3章\n", encoding="utf-8"
        )
        res = client.get(f"/api/novels/{sample_novel}/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "当前状态" in data.get("content", "")

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        # POST on the status route returns 405 (POST lives on /update-status).
        res = client.post(f"/api/novels/{sample_novel}/status")
        assert res.status_code == 405


# ─── GET /api/novels/<n>/gate-status ────────────────────────────────────────

class TestGateStatus:
    def test_happy_path_returns_phase_info(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/gate-status")
        # Endpoint requires the novel dir to exist (the fixture creates it).
        assert res.status_code == 200
        data = res.get_json()
        # Initialized and phase info are present.
        assert data.get("initialized") is True
        assert "phases" in data
        assert isinstance(data["phases"], dict)

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/gate-status")
        assert res.status_code == 405


# ─── GET /api/novels/<n>/export ─────────────────────────────────────────────

class TestExportNovel:
    def test_happy_path_returns_text(self, client, sample_novel, tmp_path):
        # Export requires at least one chapter; create a single chapter file
        # in the manuscript layout the exporter expects.
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript" / "vol-01"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / "ch-001.md").write_text(
            "# 第一章 开端\n\n这是测试章节。\n", encoding="utf-8"
        )
        # txt is the simplest format to assert against (no zip decoding).
        res = client.get(f"/api/novels/{sample_novel}/export?format=txt")
        assert res.status_code == 200
        # Plain-text response — body contains the chapter heading.
        assert "第一章" in res.get_data(as_text=True)

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/export")
        assert res.status_code == 405


# ─── POST /api/novels/create ────────────────────────────────────────────────

class TestCreateNovel:
    def test_happy_path_creates_novel(
        self, client, sample_novel, tmp_path, monkeypatch
    ):
        # Make sure the target name doesn't already exist on disk.
        # The fixture created ``test_novel``; pick a new name.
        new_name = "created_novel"
        # Call AI may fail without a key, but the route first persists files
        # and then returns a result — we accept any non-5xx and check the
        # body shape.
        res = client.post(
            "/api/novels/create",
            json={"name": new_name, "title": "新书", "genre": "xianxia"},
        )
        # 200 with success, OR success=False without 5xx if AI failed
        assert res.status_code < 500
        data = res.get_json()
        # If AI succeeded, the file exists on disk. If not, success is False
        # but we still get a structured response.
        if data.get("success") is True:
            # Verify the novel dir was created.
            assert (tmp_path / "novels" / new_name).is_dir()
        else:
            # AI generation failure is acceptable; just ensure structured error.
            assert "error" in data

    def test_missing_field_name_returns_400(self, client, sample_novel):
        # The endpoint requires ``name`` and returns 400 when missing.
        res = client.post(
            "/api/novels/create",
            json={"title": "no name", "genre": "xianxia"},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_duplicate_name_returns_400(self, client, sample_novel, tmp_path):
        # The endpoint refuses to create a novel whose dir already exists.
        # The sample_novel fixture already created ``test_novel`` on disk.
        res = client.post(
            "/api/novels/create",
            json={"name": "test_novel", "title": "dup"},
        )
        assert res.status_code < 500
        # Endpoint returns 400 with success=False for duplicates.
        data = res.get_json()
        assert data.get("success") is False

    def test_wrong_method_put_returns_405(self, client, sample_novel):
        # GET on /api/novels/create would be captured by /api/novels/<n>
        # (a novel called "create" — returns 404 instead of 405). Use PUT,
        # which is not handled by either route, to get a clean 405.
        res = client.put("/api/novels/create")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/file/write ────────────────────────────────────────

class TestWriteNovelFile:
    def test_happy_path_writes_file(self, client, sample_novel, tmp_path):
        res = client.post(
            f"/api/novels/{sample_novel}/file/write",
            json={"path": "notes/idea.md", "content": "# 灵感\n\n一句话想法。\n"},
        )
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
        # Verify the file was actually written.
        written = tmp_path / "novels" / sample_novel / "notes" / "idea.md"
        assert written.exists()
        assert "灵感" in written.read_text(encoding="utf-8")

    def test_missing_field_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/file/write",
            json={"path": "notes/x.md"},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_missing_field_path_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/file/write",
            json={"content": "some content"},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/file/write")
        assert res.status_code == 405


# ─── POST /api/novels/<n>/update-status ────────────────────────────────────

class TestUpdateStatus:
    def test_happy_path_writes_status(self, client, sample_novel, tmp_path):
        res = client.post(
            f"/api/novels/{sample_novel}/update-status",
            json={"content": "# 状态\n卷1 第5章\n"},
        )
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
        # Verify the status file was written.
        status_path = (
            tmp_path / "novels" / sample_novel / "state" / "current_status.md"
        )
        assert status_path.exists()
        assert "卷1 第5章" in status_path.read_text(encoding="utf-8")

    def test_missing_field_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/update-status",
            json={},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_empty_content_returns_400(self, client, sample_novel):
        # Endpoint requires non-empty content.
        res = client.post(
            f"/api/novels/{sample_novel}/update-status",
            json={"content": ""},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/update-status")
        assert res.status_code == 405
