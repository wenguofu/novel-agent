"""Regression tests for harness plan item [3] — Pydantic request
validation in ``portal/app.py``.

The ``@validate_json_request(Model)`` decorator parses
``request.json`` against the supplied Pydantic model and:

  1. Attaches the validated model to ``flask.g.validated_request``
     for the route handler to consume.
  2. On validation failure, short-circuits with a 400 response and
     a structured ``validation_errors`` list (the route body never
     runs).

This file pins the contract for the 4 routes that have been
migrated to Pydantic in this commit:

  - ``/api/ai/chat``           (ChatRequest)
  - ``/api/ai/stream``         (StreamRequest)
  - ``/api/novels/create``     (CreateNovelRequest)
  - ``/api/novels/<n>/chapters/<c>/edit``  (EditChapterRequest)
  - ``/api/novels/<n>/outline/<v>/edit``   (EditOutlineRequest)
"""
import pytest


# ─── /api/ai/chat ──────────────────────────────────────────────────────

class TestAIChatValidation:
    def test_valid_messages_accepted(self, client, monkeypatch):
        """A well-formed messages list reaches the route handler."""
        from app import _app_log  # noqa
        # Stub deepseek_chat so we don't hit the real API
        import app as _app_mod
        monkeypatch.setattr(
            _app_mod, "deepseek_chat",
            lambda **kw: {"success": True, "text": "stubbed"},
        )
        res = client.post("/api/ai/chat", json={
            "messages": [{"role": "user", "content": "hello"}],
            "system": "be helpful",
        })
        assert res.status_code == 200, (
            f"expected 200, got {res.status_code}: {res.data!r}"
        )
        data = res.get_json()
        assert data["success"] is True

    def test_invalid_role_rejected(self, client):
        """ChatMessage.role has pattern^(system|user|assistant)$."""
        res = client.post("/api/ai/chat", json={
            "messages": [{"role": "admin", "content": "hi"}],
        })
        assert res.status_code == 400, (
            f"expected 400, got {res.status_code}: {res.data!r}"
        )
        data = res.get_json()
        assert data["success"] is False
        assert "validation_errors" in data
        # The error must mention the messages.0.role field
        assert any("role" in e for e in data["validation_errors"]), (
            f"expected role error in {data['validation_errors']!r}"
        )

    def test_empty_content_rejected(self, client):
        """ChatMessage.content has min_length=1."""
        res = client.post("/api/ai/chat", json={
            "messages": [{"role": "user", "content": ""}],
        })
        assert res.status_code == 400
        data = res.get_json()
        assert any("content" in e for e in data["validation_errors"])

    def test_temperature_out_of_range_rejected(self, client):
        """ChatRequest.temperature has ge=0.0, le=2.0."""
        res = client.post("/api/ai/chat", json={
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 5.0,
        })
        assert res.status_code == 400
        data = res.get_json()
        assert any("temperature" in e for e in data["validation_errors"])


# ─── /api/ai/stream ────────────────────────────────────────────────────

class TestAIStreamValidation:
    def test_valid_payload_accepted(self, client, monkeypatch):
        import app as _app_mod
        # Stub the deepseek config getter
        monkeypatch.setattr(
            _app_mod, "get_active_deepseek_config",
            lambda: {
                "api_key": "fake-key", "api_base": "https://api.example.com",
                "model": "test", "temperature": 0.7, "max_tokens": 100, "top_p": 0.9,
            },
        )
        res = client.post("/api/ai/stream", json={
            "messages": [{"role": "user", "content": "hi"}],
        })
        # Will probably fail to actually stream from a fake API,
        # but it must NOT be a 400 (validation must pass)
        assert res.status_code != 400, (
            f"validation should have passed; got 400: {res.data!r}"
        )

    def test_invalid_role_rejected(self, client):
        res = client.post("/api/ai/stream", json={
            "messages": [{"role": "tool", "content": "x"}],
        })
        assert res.status_code == 400
        data = res.get_json()
        assert any("role" in e for e in data["validation_errors"])


# ─── /api/novels/create ────────────────────────────────────────────────

class TestCreateNovelValidation:
    def test_valid_payload_passes_validation(self, client, monkeypatch, tmp_path):
        """A well-formed payload must NOT be 400-validated out.
        We don't drive the full handler (it makes real AI calls) —
        this test pins the contract that Pydantic accepts valid
        input. The downstream handler behavior is covered by the
        existing tests/functional/test_novel_management.py."""
        import app as _app_mod
        # Stub get_novels_dir to a temp dir so the file-exists check
        # doesn't trip on a stale state.
        monkeypatch.setattr(_app_mod, "get_novels_dir", lambda: str(tmp_path))
        res = client.post("/api/novels/create", json={
            "name": "pydantic-validation-test-novel",
        })
        # The validation must pass — failure would return 400 with
        # validation_errors. A non-400 (e.g. 200/500 from downstream
        # AI) is acceptable for this contract test.
        if res.status_code == 400:
            data = res.get_json()
            assert "validation_errors" not in data, (
                f"validation should have passed: {data!r}"
            )

    def test_empty_name_rejected(self, client):
        """CreateNovelRequest.name has min_length=1."""
        res = client.post("/api/novels/create", json={
            "name": "",
        })
        assert res.status_code == 400
        data = res.get_json()
        assert any("name" in e for e in data["validation_errors"])

    def test_missing_name_rejected(self, client):
        res = client.post("/api/novels/create", json={
            "genre": "玄幻",
        })
        assert res.status_code == 400
        data = res.get_json()
        assert any("name" in e for e in data["validation_errors"])


# ─── /api/novels/<n>/chapters/<c>/edit ─────────────────────────────────

class TestEditChapterValidation:
    def test_valid_content_accepted(self, client, sample_novel, tmp_path, monkeypatch):
        """EditChapterRequest.content has min_length=1. A 1-char
        content is technically valid by the schema (the route layer
        doesn't add a higher min). The actual write goes to disk,
        so we point the novels dir at tmp_path."""
        import app as _app_mod
        monkeypatch.setattr(_app_mod, "get_novels_dir", lambda: str(tmp_path))
        # The novel dir must exist
        novel_dir = tmp_path / sample_novel
        novel_dir.mkdir()
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit",
            json={"content": "x"},
        )
        # Should NOT be a 400
        assert res.status_code != 400, (
            f"validation should pass for non-empty content; got 400: {res.data!r}"
        )

    def test_empty_content_rejected(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit",
            json={"content": ""},
        )
        assert res.status_code == 400
        data = res.get_json()
        assert any("content" in e for e in data["validation_errors"])

    def test_missing_content_rejected(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit",
            json={},
        )
        assert res.status_code == 400
        data = res.get_json()
        assert any("content" in e for e in data["validation_errors"])


# ─── /api/novels/<n>/outline/<v>/edit ──────────────────────────────────

class TestEditOutlineValidation:
    def test_valid_content_accepted(self, client, sample_novel, tmp_path, monkeypatch):
        import app as _app_mod
        monkeypatch.setattr(_app_mod, "get_novels_dir", lambda: str(tmp_path))
        novel_dir = tmp_path / sample_novel / "outline"
        novel_dir.mkdir(parents=True)
        res = client.post(
            f"/api/novels/{sample_novel}/outline/vol-01/edit",
            json={"content": "chapters:\n  - number: 1\n    title: 测试\n"},
        )
        assert res.status_code != 400, (
            f"validation should pass; got 400: {res.data!r}"
        )

    def test_empty_content_rejected(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/outline/vol-01/edit",
            json={"content": ""},
        )
        assert res.status_code == 400
        data = res.get_json()
        assert any("content" in e for e in data["validation_errors"])


# ─── Static guards ─────────────────────────────────────────────────────

class TestPydanticWiring:
    """Static guards: the 5 migrated routes must use the
    ``@validate_json_request(...)`` decorator, and a generic
    smoke test for the decorator itself."""

    def test_decorator_attaches_validated_request_to_g(self):
        """Unit test for the decorator in isolation — confirms
        g.validated_request is the validated Pydantic model."""
        from flask import Flask, g, jsonify, request
        from models import validate_json_request, ChatRequest

        app = Flask(__name__)
        seen = {}

        @app.route("/__test_validate__", methods=["POST"])
        @validate_json_request(ChatRequest)
        def handler():
            seen["req"] = g.validated_request
            return jsonify({"messages": len(g.validated_request.messages)})

        client = app.test_client()
        res = client.post("/__test_validate__", json={
            "messages": [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ],
        })
        assert res.status_code == 200
        assert isinstance(seen["req"], ChatRequest)
        assert len(seen["req"].messages) == 2

    def test_decorator_returns_400_on_validation_error(self):
        from flask import Flask, jsonify
        from models import validate_json_request, ChatRequest

        app = Flask(__name__)

        @app.route("/__test_validate_400__", methods=["POST"])
        @validate_json_request(ChatRequest)
        def handler():
            return jsonify({"unreachable": True})

        client = app.test_client()
        res = client.post("/__test_validate_400__", json={
            "messages": [{"role": "admin", "content": "x"}],
        })
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "validation_errors" in data
        # The handler must NOT have been called
        assert "unreachable" not in data

    def test_routes_use_decorator(self):
        """The 5 migrated routes must be wrapped with
        ``@validate_json_request(...)`` in source."""
        from pathlib import Path
        app_path = Path(__file__).resolve().parent.parent.parent / "portal" / "app.py"
        text = app_path.read_text(encoding="utf-8")

        expected = {
            "/api/ai/chat": "ChatRequest",
            "/api/ai/stream": "StreamRequest",
            "/api/novels/create": "CreateNovelRequest",
            "/api/novels/<novel_name>/chapters/<path:ch_ref>/edit": "EditChapterRequest",
            "/api/novels/<novel_name>/outline/<vol_ref>/edit": "EditOutlineRequest",
        }
        for route, model in expected.items():
            # The route declaration must be immediately followed by
            # @validate_json_request(<Model>) on the next line
            import re
            pattern = re.compile(
                r'@app\.route\("' + re.escape(route) + r'".*?\)\s*\n'
                r'@validate_json_request\(' + re.escape(model) + r'\)',
                re.DOTALL,
            )
            assert pattern.search(text), (
                f"route {route!r} is not wrapped with "
                f"@validate_json_request({model}) in portal/app.py"
            )
