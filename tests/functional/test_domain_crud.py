"""Functional tests for domain-CRUD endpoints (M3 Task 7).

Endpoint coverage (30 distinct endpoints across 7+ tables):
  characters         (7): list, get, add, manage, event, init, ai-profile
  foreshadowing      (6): list, unresolved, add, manage, resolve, init
  world_building     (3): list, add, manage
  plot_arcs          (3): list, add, manage
  pacing_control     (3): list, add, manage
  revelation_schedule(3): list, add, manage
  genre_rules        (1): list
  alias_names        (1): list
  story_volumes      (1): list
  volume_plans       (1): list
  project_meta       (1): list

Notes on path conventions (accumulated across Tasks 4 + 5 + 6 + 7):
  - All routes use a default string converter for ``<novel_name>``; do not
    use slashes. Plain novel names (e.g. ``test_novel``) match.
  - ``/api/characters/<n>/<int:cid>``, ``/api/characters/<n>/<int:cid>/event``,
    ``/api/characters/<n>/<int:cid>/ai-profile``,
    ``/api/foreshadowing/<n>/<int:fid>``,
    ``/api/foreshadowing/<n>/resolve/<int:fid>``,
    and the four ``<table>/<n>/<int:row_id>`` PUT/DELETE routes all use
    ``<int:...>`` converters. Only integers match.
  - All DB-backed endpoints call ``content_db.get_db()`` (raw sqlite3
    against module-level ``DB_PATH``). They do NOT see the SQLAlchemy
    ``DATABASE_URL`` from the ``tmp_db`` fixture, so we reuse
    ``_point_content_db_at_tmp`` to redirect ``DB_PATH`` at the tmp DB
    and seed the ``test_novel`` row.
  - Add payloads are HANDLER-SPECIFIC (see portal/app.py). The plan's
    guessed schemas do NOT match the real handlers; this file uses the
    actual fields. The most notable cases:
      * ``characters`` add requires ``name``; ``role`` defaults to "配角".
      * ``foreshadowing`` add expects ``name`` + ``description`` (NOT
        ``title``/``content`` as the plan suggested).
      * ``world_building`` add expects ``domain`` + ``name`` + ``content``
        (NOT ``title``/``category``).
      * ``plot_arcs`` add expects ``name`` + ``type`` (NOT ``title``/
        ``arc_type``).
      * ``pacing_control`` add expects ``volume`` + ``chapter_start`` +
        ``chapter_end`` + ``pace_type``.
      * ``revelation_schedule`` add expects ``name`` + ``reveal_volume`` +
        ``reveal_chapter`` (NOT ``title``/``reveal_vol``).
  - ``/api/characters/<n>/<int:cid>/ai-profile`` calls DeepSeek — we do
    NOT exercise that path in the happy-path test (it requires network
    + a configured API key). The route exists; we just leave it off the
    list of "exercised endpoints" and treat it as covered by the
    route-existence test below.
"""
import sqlite3

import pytest

# Reuse the helper from test_outline_api.py (same module pattern; we
# inline a copy here so the test file remains self-contained if that
# other file's import surface changes).
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


# Per-handler POST payloads — verified against portal/app.py.
# (url, payload, row_id_response_key_or_None)
TABLES = [
    ("characters",          "/api/characters/{novel}",          {"name": "李闲", "role": "主角"}),
    ("foreshadowing",       "/api/foreshadowing/{novel}",       {"name": "伏笔A", "description": "古剑来历"}),
    ("world_building",      "/api/world_building/{novel}",      {"domain": "地理", "name": "玄天城", "content": "北境主城"}),
    ("plot_arcs",           "/api/plot_arcs/{novel}",           {"name": "主线", "type": "main"}),
    ("pacing_control",      "/api/pacing_control/{novel}",      {"volume": 1, "chapter_start": 1, "chapter_end": 5, "pace_type": "fast"}),
    ("revelation_schedule", "/api/revelation_schedule/{novel}", {"name": "揭晓1", "reveal_volume": 2, "reveal_chapter": 3}),
]


# ─── Read-only list endpoints (genre_rules, alias_names, story_volumes,
# ───  volume_plans, project_meta) — 5 endpoints ────────────────────────

class TestReadOnlyListEndpoints:
    URLS = [
        "/api/genre_rules/{novel}",
        "/api/alias_names/{novel}",
        "/api/story_volumes/{novel}",
        "/api/volume_plans/{novel}",
        "/api/project_meta/{novel}",
    ]

    @pytest.mark.parametrize("url", URLS, ids=lambda u: u.split("/")[2])
    def test_happy_path(self, client, sample_novel, tmp_db, monkeypatch, url):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(url.format(novel=sample_novel))
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "items" in data
        assert "total" in data


# ─── List + Add for the 6 mutable tables ─────────────────────────────

class TestListEndpoints:
    @pytest.mark.parametrize("name,list_url,_payload", TABLES, ids=[t[0] for t in TABLES])
    def test_list_happy_path(self, client, sample_novel, tmp_db, monkeypatch,
                             name, list_url, _payload):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(list_url.format(novel=sample_novel))
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "items" in data
        assert isinstance(data["items"], list)


class TestAddEndpoints:
    @pytest.mark.parametrize("name,create_url,payload", TABLES, ids=[t[0] for t in TABLES])
    def test_add_happy_path(self, client, sample_novel, tmp_db, monkeypatch,
                            name, create_url, payload):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(create_url.format(novel=sample_novel), json=payload)
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
        assert "id" in data
        assert isinstance(data["id"], int)


# ─── Manage endpoints (PUT update + DELETE) for the 4 inline-managed
# ─── tables — world_building, plot_arcs, pacing_control, revelation_schedule.
# ─── characters and foreshadowing are tested in their own classes below. ─

MANAGE_TABLES = [
    ("world_building",      "/api/world_building/{novel}",      {"domain": "更新域", "name": "改名后", "content": "新内容"}),
    ("plot_arcs",           "/api/plot_arcs/{novel}",           {"name": "改名后", "status": "completed"}),
    ("pacing_control",      "/api/pacing_control/{novel}",      {"pace_type": "slow", "intensity": 3}),
    ("revelation_schedule", "/api/revelation_schedule/{novel}", {"name": "改后", "priority": "high"}),
]


class TestManageEndpointsPut:
    @pytest.mark.parametrize("name,create_url,put_payload", MANAGE_TABLES,
                             ids=[t[0] for t in TABLES if t[0] in
                                  {m[0] for m in MANAGE_TABLES}] or [m[0] for m in MANAGE_TABLES])
    def test_put_updates_row(self, client, sample_novel, tmp_db, monkeypatch,
                             name, create_url, put_payload):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # Create a row first
        add_payload = next(t[2] for t in TABLES if t[0] == name)
        create_res = client.post(create_url.format(novel=sample_novel), json=add_payload)
        assert create_res.status_code in (200, 201)
        row_id = create_res.get_json()["id"]
        # PUT update
        res = client.put(
            create_url.format(novel=sample_novel) + f"/{row_id}",
            json=put_payload,
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True


class TestManageEndpointsDelete:
    @pytest.mark.parametrize("name,create_url,_payload", MANAGE_TABLES,
                             ids=[m[0] for m in MANAGE_TABLES])
    def test_delete_removes_row(self, client, sample_novel, tmp_db, monkeypatch,
                                name, create_url, _payload):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        add_payload = next(t[2] for t in TABLES if t[0] == name)
        create_res = client.post(create_url.format(novel=sample_novel), json=add_payload)
        row_id = create_res.get_json()["id"]
        res = client.delete(
            create_url.format(novel=sample_novel) + f"/{row_id}",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True


# ─── characters: full lifecycle (7 endpoints) ─────────────────────────

class TestCharactersFull:
    def _create(self, client, sample_novel):
        res = client.post(
            f"/api/characters/{sample_novel}",
            json={"name": "李闲", "role": "主角", "background": "出身寒门"},
        )
        assert res.status_code in (200, 201), res.get_json()
        return res.get_json()["id"]

    def test_list(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/characters/{sample_novel}")
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_get_one(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        cid = self._create(client, sample_novel)
        res = client.get(f"/api/characters/{sample_novel}/{cid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["character"]["name"] == "李闲"
        assert "events" in data

    def test_add(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        cid = self._create(client, sample_novel)
        assert isinstance(cid, int)

    def test_manage_put_and_delete(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        cid = self._create(client, sample_novel)
        # PUT update
        put_res = client.put(
            f"/api/characters/{sample_novel}/{cid}",
            json={"personality": "坚毅", "background": "更新后"},
        )
        assert put_res.status_code == 200
        assert put_res.get_json()["success"] is True
        # DELETE
        del_res = client.delete(f"/api/characters/{sample_novel}/{cid}")
        assert del_res.status_code == 200
        assert del_res.get_json()["success"] is True

    def test_event(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        cid = self._create(client, sample_novel)
        res = client.post(
            f"/api/characters/{sample_novel}/{cid}/event",
            json={
                "description": "突破境界",
                "event_type": "状态变更",
                "vol": 1,
                "ch": 1,
            },
        )
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
        assert "id" in data

    def test_init(self, client, sample_novel, tmp_db, monkeypatch, tmp_path):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # The init handler scans on-disk character markdown. It returns
        # success even when the optional source file is missing, so this
        # is a safe smoke test of the route.
        res = client.post(f"/api/characters/{sample_novel}/init")
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True

    def test_ai_profile_route_exists(self, client, sample_novel, tmp_db, monkeypatch):
        """The /ai-profile route calls DeepSeek. We only assert that the
        route is registered and rejects the call cleanly (either 404
        because the character doesn't exist, or 500/502 with a
        well-formed error envelope). We do NOT exercise a real
        network call here.
        """
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.post(f"/api/characters/{sample_novel}/9999/ai-profile")
        # Acceptable outcomes: 404 (character not found) or 5xx with
        # success=False (real network call failed in sandbox).
        assert res.status_code >= 400
        assert res.get_json().get("success") is False


# ─── foreshadowing: full lifecycle (6 endpoints) ──────────────────────

class TestForeshadowingFull:
    def _create(self, client, sample_novel):
        res = client.post(
            f"/api/foreshadowing/{sample_novel}",
            json={"name": "古剑", "description": "主角佩剑的来历", "category": "剧情"},
        )
        assert res.status_code in (200, 201), res.get_json()
        return res.get_json()["id"]

    def test_list(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/foreshadowing/{sample_novel}")
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_unresolved(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        res = client.get(f"/api/foreshadowing/{sample_novel}/unresolved")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "items" in data

    def test_add(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        fid = self._create(client, sample_novel)
        assert isinstance(fid, int)

    def test_manage_put_and_delete(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        fid = self._create(client, sample_novel)
        put_res = client.put(
            f"/api/foreshadowing/{sample_novel}/{fid}",
            json={"description": "更新后", "priority": "high"},
        )
        assert put_res.status_code == 200
        assert put_res.get_json()["success"] is True
        del_res = client.delete(f"/api/foreshadowing/{sample_novel}/{fid}")
        assert del_res.status_code == 200
        assert del_res.get_json()["success"] is True

    def test_resolve(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        fid = self._create(client, sample_novel)
        res = client.post(
            f"/api/foreshadowing/{sample_novel}/resolve/{fid}",
            json={"vol": 1, "ch": 3, "note": "揭晓"},
        )
        assert res.status_code in (200, 201)
        assert res.get_json()["success"] is True

    def test_init(self, client, sample_novel, tmp_db, monkeypatch):
        _point_content_db_at_tmp(monkeypatch, tmp_db)
        # init_foreshadowing_from_outline returns a structured result;
        # the route wraps it in {"success": True, ...}.
        res = client.post(f"/api/foreshadowing/{sample_novel}/init")
        assert res.status_code in (200, 201)
        data = res.get_json()
        assert data["success"] is True
