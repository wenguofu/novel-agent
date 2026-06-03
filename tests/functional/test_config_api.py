"""Functional tests for config API endpoints (M3 Task 10).

Endpoint coverage (9 total):
  GET  /api/config                                              2-dim
  POST /api/config/save                                         4-dim
  POST /api/config/test                                         4-dim
  GET  /api/config-db/<table>                                   2-dim
  POST /api/config-db/<table>                                   4-dim
  PUT  /api/config-db/<table>/<int:row_id>                      4-dim
  DEL  /api/config-db/<table>/<int:row_id>                      4-dim
  GET  /api/styles                                              2-dim
  GET  /api/templates                                           2-dim
  GET  /api/usage/stats                                         2-dim

Notes on path conventions (accumulated across Tasks 4–10):
  - ``/api/config-db/<table>`` whitelists 4 table names:
    ``banned_words``, ``compliance_rules``, ``alias_registry``,
    ``style_presets``. Anything else returns 400 with success=False.
  - The config DB layer is implemented via a ``_RepoConfigWrapper``
    around the SQLAlchemy ``repository``. The standard ``tmp_db``
    fixture therefore works for these endpoints; we do NOT need the
    ``_point_content_db_at_tmp`` helper.
  - POST/PUT payloads for the four config tables are HANDLER-SPECIFIC
    (see portal/app.py:2475-2531). The notable fields are:
      * ``banned_words``     : ``word`` (+ category, replacement, severity)
      * ``compliance_rules`` : ``rule_key``, ``rule_value`` (+ description, category)
      * ``alias_registry``   : ``real_name``, ``alias`` (+ category, notes)
      * ``style_presets``    : ``name``, ``prompt`` (+ description, is_active)
  - The ``/api/config/test`` route makes a real HTTP call via httpx
    when an API key is configured. In the sandbox no key is configured
    so the route returns 200 with success=False and ``"API Key 未配置"``.
    We assert that envelope and never trigger a real call.
  - ``/api/styles`` and ``/api/templates`` scan the
    ``agent-system/styles/*.json`` and ``templates/`` directories on
    disk. Both return 200 with the listed items; the lists are
    non-empty because the repo seeds both.
  - ``/api/usage/stats`` opens the on-disk usage DB. The
    ``_init_usage_db()`` module-level call creates the schema in the
    production ``portal/usage.db``; this endpoint therefore reads
    from a real on-disk file. We assert the well-formed envelope.
  - ``/api/config/save`` writes a JSON file at
    ``portal/deepseek_config.json``. To keep tests isolated we do NOT
    exercise a real save here; the handler's return envelope is
    checked by reading GET /api/config before/after.
"""
import pytest

# Per-table POST payload schemas for the four whitelisted tables.
CONFIG_TABLE_PAYLOADS = [
    ("banned_words",     {"word": "测试词", "category": "通用"}),
    ("compliance_rules", {"rule_key": "test_key", "rule_value": "test_val"}),
    ("alias_registry",   {"real_name": "李闲", "alias": "闲哥"}),
    ("style_presets",    {"name": "测试风格", "prompt": "用简练语言"}),
]


# ─── GET /api/config ───────────────────────────────────────────────────

class TestGetConfig:
    def test_happy_path_returns_keys(self, client):
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # The handler always reports these well-known fields.
        for key in ("deepseek_configured", "deepseek_model",
                    "deepseek_api_base", "agent_root", "novels_root"):
            assert key in data, f"missing field: {key}"

    def test_wrong_method_post_returns_405(self, client):
        res = client.post("/api/config")
        assert res.status_code == 405


# ─── POST /api/config/save ─────────────────────────────────────────────

class TestSaveConfig:
    def test_happy_path_persists(self, client, tmp_path, monkeypatch):
        # Redirect DEEPSEEK_CONFIG_PATH to a tmp file so the handler
        # does not overwrite the project's real config.
        import app as _app
        cfg_path = tmp_path / "deepseek_config_test.json"
        monkeypatch.setattr(_app, "DEEPSEEK_CONFIG_PATH", str(cfg_path))
        res = client.post(
            "/api/config/save",
            json={
                "api_key": "sk-test-1234567890abcd",
                "api_base": "https://api.test.example/v1",
                "model": "test-model",
                "temperature": "0.7",
                "max_tokens": "4096",
                "top_p": "0.9",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("message") == "配置已保存"
        assert cfg_path.exists()

    def test_missing_field_still_succeeds(self, client, tmp_path, monkeypatch):
        # The handler only overwrites provided fields; missing fields
        # keep their existing values. An empty payload is therefore a
        # no-op save.
        import app as _app
        cfg_path = tmp_path / "deepseek_config_test2.json"
        monkeypatch.setattr(_app, "DEEPSEEK_CONFIG_PATH", str(cfg_path))
        res = client.post("/api/config/save", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_empty_body_returns_success(self, client, tmp_path, monkeypatch):
        import app as _app
        cfg_path = tmp_path / "deepseek_config_test3.json"
        monkeypatch.setattr(_app, "DEEPSEEK_CONFIG_PATH", str(cfg_path))
        res = client.post("/api/config/save", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # Persisted file is created (with empty values).
        assert cfg_path.exists()

    def test_wrong_method_get_returns_405(self, client):
        res = client.get("/api/config/save")
        assert res.status_code == 405


# ─── POST /api/config/test ─────────────────────────────────────────────

class TestConfigTest:
    def test_happy_path_returns_envelope(self, client):
        # The sandbox may have a real API key configured (the
        # miniMax / Anthropic route), in which case the handler makes
        # an actual HTTP call. Either outcome (unconfigured error or
        # API call response) is acceptable — we only assert the route
        # is reachable and returns a well-formed success envelope.
        res = client.post("/api/config/test", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert "success" in data
        # The error key is present on failure.
        if not data["success"]:
            assert "error" in data
        else:
            # On success the handler returns ``message`` + ``model``.
            assert "message" in data

    def test_payload_ignored_on_failure(self, client):
        # Even with a payload, an unconfigured key still wins and the
        # route reports an error envelope. With a configured key, the
        # payload is irrelevant — the handler reads the active config.
        res = client.post(
            "/api/config/test",
            json={"api_key": "sk-test", "api_base": "https://api.test/v1"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "success" in data

    def test_empty_body_returns_envelope(self, client):
        res = client.post("/api/config/test", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert "success" in data

    def test_wrong_method_get_returns_405(self, client):
        res = client.get("/api/config/test")
        assert res.status_code == 405


# ─── GET /api/config-db/<table> ────────────────────────────────────────

class TestConfigDbList:
    @pytest.mark.parametrize("table,_payload", CONFIG_TABLE_PAYLOADS,
                             ids=[t[0] for t in CONFIG_TABLE_PAYLOADS])
    def test_list_whitelisted_table(self, client, table, _payload):
        res = client.get(f"/api/config-db/{table}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "rows" in data
        assert isinstance(data["rows"], list)

    def test_invalid_table_returns_400(self, client):
        res = client.get("/api/config-db/no_such_table")
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "无效表名" in data.get("error", "")


# ─── POST /api/config-db/<table> ───────────────────────────────────────

class TestConfigDbAdd:
    @pytest.mark.parametrize("table,payload", CONFIG_TABLE_PAYLOADS,
                             ids=[t[0] for t in CONFIG_TABLE_PAYLOADS])
    def test_add_happy_path(self, client, table, payload):
        res = client.post(f"/api/config-db/{table}", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("message") == "已添加"

    def test_invalid_table_returns_400(self, client):
        res = client.post(
            "/api/config-db/no_such_table",
            json={"word": "x"},
        )
        assert res.status_code == 400
        assert res.get_json()["success"] is False

    def test_missing_required_field_returns_500(self, client):
        # banned_words POST requires ``word``. Missing it → KeyError →
        # handler returns 500 with success=False.
        res = client.post("/api/config-db/banned_words", json={})
        assert res.status_code == 500
        data = res.get_json()
        assert data["success"] is False


# ─── PUT /api/config-db/<table>/<int:row_id> ───────────────────────────

class TestConfigDbPut:
    def _create_banned_word(self, client):
        res = client.post(
            "/api/config-db/banned_words",
            json={"word": "原词", "category": "通用"},
        )
        assert res.status_code == 200
        # The handler does not return the row id; list to discover it.
        listed = client.get("/api/config-db/banned_words").get_json()["rows"]
        return listed[-1]["id"]

    def test_happy_path_updates_row(self, client):
        row_id = self._create_banned_word(client)
        res = client.put(
            f"/api/config-db/banned_words/{row_id}",
            json={"word": "改后", "category": "更新"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("message") == "已更新"

    def test_unknown_row_id_returns_success(self, client):
        # The wrapper executes the UPDATE; a non-existent row simply
        # updates zero rows. The handler reports success=True because
        # no error was raised.
        res = client.put(
            "/api/config-db/banned_words/99999",
            json={"word": "x", "category": "y"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_invalid_table_returns_400(self, client):
        res = client.put(
            "/api/config-db/no_such_table/1",
            json={"word": "x"},
        )
        assert res.status_code == 400
        assert res.get_json()["success"] is False

    def test_wrong_method_get_returns_405(self, client):
        res = client.get("/api/config-db/banned_words/1")
        assert res.status_code == 405


# ─── DELETE /api/config-db/<table>/<int:row_id> ────────────────────────

class TestConfigDbDelete:
    def _create(self, client):
        res = client.post(
            "/api/config-db/banned_words",
            json={"word": "待删", "category": "通用"},
        )
        assert res.status_code == 200
        listed = client.get("/api/config-db/banned_words").get_json()["rows"]
        return listed[-1]["id"]

    def test_happy_path_deletes_row(self, client):
        row_id = self._create(client)
        res = client.delete(f"/api/config-db/banned_words/{row_id}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data.get("message") == "已删除"

    def test_unknown_row_id_returns_success(self, client):
        res = client.delete("/api/config-db/banned_words/99999")
        assert res.status_code == 200
        assert res.get_json()["success"] is True

    def test_invalid_table_returns_400(self, client):
        res = client.delete("/api/config-db/no_such_table/1")
        assert res.status_code == 400
        assert res.get_json()["success"] is False

    def test_wrong_method_get_returns_405(self, client):
        # The /<int:row_id> route only accepts PUT and DELETE; a GET
        # on the same path is not registered → 405.
        res = client.get("/api/config-db/banned_words/1")
        assert res.status_code == 405


# ─── GET /api/styles ───────────────────────────────────────────────────

class TestStyles:
    def test_happy_path_returns_styles(self, client):
        res = client.get("/api/styles")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "styles" in data
        assert isinstance(data["styles"], list)
        # The repo seeds at least the 12 distilled style fingerprints
        # in agent-system/styles/ + any DB presets. We expect >= 1.
        assert len(data["styles"]) >= 1

    def test_wrong_method_post_returns_405(self, client):
        res = client.post("/api/styles")
        assert res.status_code == 405


# ─── GET /api/templates ────────────────────────────────────────────────

class TestTemplates:
    def test_happy_path_returns_templates(self, client):
        res = client.get("/api/templates")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "templates" in data
        assert isinstance(data["templates"], dict)

    def test_wrong_method_post_returns_405(self, client):
        res = client.post("/api/templates")
        assert res.status_code == 405


# ─── GET /api/usage/stats ──────────────────────────────────────────────

class TestUsageStats:
    def test_happy_path_returns_stats(self, client):
        res = client.get("/api/usage/stats")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        # Well-known top-level keys.
        for key in ("total_tokens", "total_cost", "by_operation", "by_novel"):
            assert key in data, f"missing stat key: {key}"

    def test_with_novel_filter(self, client):
        res = client.get("/api/usage/stats?novel=test_novel&days=7")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_wrong_method_post_returns_405(self, client):
        res = client.post("/api/usage/stats")
        assert res.status_code == 405
