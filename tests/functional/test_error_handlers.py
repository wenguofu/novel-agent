"""Regression tests for harness plan item [5] — error handler wiring.

Verifies that the structured exception hierarchy and Flask error
handlers defined in ``portal/errors.py`` are actually registered on
the live Flask app, and that the 404 SPA fallback still returns a
structured ``success=False`` JSON envelope for ``/api/*`` paths.
"""
import pytest

from errors import (
    NovelAgentError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)


# Ensure the functional conftest puts ``portal/`` on sys.path so the
# imports below resolve to the same module instance the app uses.
pytest_plugins = []  # rely on the parent conftest


@pytest.fixture
def client(tmp_db):
    """Flask test client (matches the fixture in tests/functional/conftest.py)."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestErrorHandlersRegistered:
    """The errors.py handlers must be active on the live app."""

    def test_novel_agent_error_handler_registered(self, client):
        """Raising a custom exception class from a route must hit the
        ``NovelAgentError`` handler and return a structured payload."""
        from app import app

        @app.route("/__test_novel_agent_error__")
        def _raise_novel_agent_error():
            raise NotFoundError("测试资源不存在")

        res = client.get("/__test_novel_agent_error__")
        assert res.status_code == 404
        body = res.get_json()
        assert body is not None
        assert body.get("success") is False
        assert body.get("error_code") == "NOT_FOUND"
        assert "测试资源不存在" in body.get("error", "")

    def test_validation_error_handler_registered(self, client):
        """ValidationError must surface as a 400 with the expected envelope."""
        from app import app

        @app.route("/__test_validation_error__")
        def _raise_validation_error():
            raise ValidationError("参数校验失败")

        res = client.get("/__test_validation_error__")
        assert res.status_code == 400
        body = res.get_json()
        assert body is not None
        assert body.get("success") is False
        assert body.get("error_code") == "VALIDATION_ERROR"

    def test_register_error_handlers_is_idempotent(self):
        """Calling register_error_handlers twice must not raise and must
        leave a working handler set in place."""
        from flask import Flask
        from errors import NotFoundError as _NotFoundError

        app = Flask(__name__)
        register_error_handlers(app)
        # Second call exercises the re-registration path.
        register_error_handlers(app)

        @app.route("/__x__")
        def _x():
            raise _NotFoundError("dup")

        client = app.test_client()
        res = client.get("/__x__")
        assert res.status_code == 404
        assert res.get_json()["success"] is False


class TestAPINotFound:
    """Unknown /api/* paths must return a structured 404 envelope."""

    def test_unknown_api_path_returns_structured_404(self, client):
        res = client.get("/api/__definitely_does_not_exist__/abc")
        assert res.status_code == 404
        body = res.get_json()
        assert body is not None
        # The SPA fallback delegates to errors.NotFoundError, so the
        # envelope is the canonical one — this is the contract the
        # tests/functional/_helpers.py::assert_not_found helper pins.
        assert body.get("success") is False
        assert body.get("error_code") == "NOT_FOUND"


class TestMethodNotAllowed:
    """POSTing to a GET-only route must produce a structured 405."""

    def test_post_to_get_only_route_returns_405(self, client, tmp_db):
        # /api/content/stats/<novel> is GET-only per test_search.py.
        res = client.post("/api/content/stats/anything")
        assert res.status_code == 405
        body = res.get_json()
        assert body is not None
        assert body.get("success") is False
        assert body.get("error_code") == "METHOD_NOT_ALLOWED"
