"""Regression tests for harness plan item [6] — wire ``logging_config``
into ``portal/app.py``.

Verifies that:
- ``portal/app.py`` imports the structured logger helpers from
  ``portal/logging_config.py``.
- The module-level ``_app_log`` instance is a usable ``StructuredLogger``.
- The ``with_logging`` decorator adds timing data and preserves the
  function ``__name__`` (so Flask's ``@app.route`` still registers
  the endpoint correctly).
- The ``@with_logging`` decorator applied to a route handler does not
  break Flask's URL routing.
"""
import json
import logging as _stdlib_logging

import pytest

# Ensure portal/ is on sys.path so we can import ``app`` and
# ``logging_config`` directly. This is the same pattern as
# tests/functional/test_error_handlers.py and is also what
# tests/functional/conftest.py does, so we duplicate the lines here
# so this file is self-contained when run in isolation.
from pathlib import Path
import sys

_PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(_PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(_PORTAL_DIR))

from logging_config import StructuredLogger, with_logging  # noqa: E402


class TestStructuredLoggerAPI:
    """The structured logger is the API the rest of the harness uses."""

    def test_structured_logger_can_be_instantiated(self):
        """``StructuredLogger(name)`` must return an object with the
        standard log methods (``info``, ``warning``, ``error``, ...)."""
        sl = StructuredLogger("test-structured-logger")
        for attr in ("debug", "info", "warning", "error", "exception"):
            assert hasattr(sl, attr), f"StructuredLogger missing {attr!r}"

    def test_structured_logger_emits_json(self, capsys):
        """``StructuredLogger.warning(msg, **kwargs)`` must emit a JSON
        payload containing the message and any extra kwargs."""
        sl = StructuredLogger("test-structured-logger-json")
        sl.warning("something happened", novel="x", error="boom")

        # The handler writes to stderr (see logging_config.py line ~36).
        captured = capsys.readouterr()
        assert captured.err, "StructuredLogger wrote nothing to stderr"
        # The last non-empty line is the JSON record.
        last_line = [ln for ln in captured.err.splitlines() if ln.strip()][-1]
        record = json.loads(last_line)
        assert record["message"] == "something happened"
        assert record["level"] == "WARNING"
        assert record["logger"] == "test-structured-logger-json"
        assert record["novel"] == "x"
        assert record["error"] == "boom"
        assert "timestamp" in record


class TestWithLoggingDecorator:
    """``with_logging`` wraps a function with request_id + timing."""

    def test_preserves_function_name(self):
        """Flask's @app.route registers routes by the function's
        ``__name__``; ``@with_logging`` must use ``@wraps`` so the
        endpoint name survives the wrapping."""

        @with_logging
        def my_handler():
            return 42

        assert my_handler.__name__ == "my_handler"

    def test_passes_through_return_value(self):
        """The wrapped function must return the original function's
        return value unchanged."""

        @with_logging
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_logs_timing_info_on_success(self, caplog):
        """A successful call must log an INFO record containing the
        function name, a request_id, and an ``elapsed_seconds`` field."""

        @with_logging
        def ping():
            return "pong"

        with caplog.at_level(_stdlib_logging.INFO):
            result = ping()
        assert result == "pong"

        # The structured logger serialises a JSON record into the
        # message field of the stdlib LogRecord; pull it out and
        # confirm the structured fields exist.
        records = [r for r in caplog.records if r.name == "novel-agent"]
        assert records, "with_logging did not emit any structured records"
        last = records[-1]
        payload = json.loads(last.getMessage())
        assert payload["operation"] == "ping"
        assert payload["success"] is True
        assert "request_id" in payload
        assert "elapsed_seconds" in payload

    def test_reraises_exceptions(self):
        """If the wrapped function raises, the exception must still
        propagate (so Flask's error handlers can convert it to a
        proper HTTP response). The decorator must not swallow it."""

        @with_logging
        def boom():
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError, match="nope"):
            boom()


class TestAppWiresLoggingConfig:
    """The app module must actually import and expose the structured
    logger — otherwise the migration in this commit is dead code."""

    def test_app_module_imports_structured_logger(self):
        import app as _app_mod
        # The harness [6] change adds a module-level ``_app_log``
        # bound to ``StructuredLogger("novel-agent.app")`` so call
        # sites can use it without re-instantiating per request.
        assert hasattr(_app_mod, "_app_log"), (
            "portal/app.py did not expose a module-level _app_log"
        )
        assert isinstance(_app_mod._app_log, StructuredLogger)
        assert _app_mod._app_log.name == "novel-agent.app"

    def test_app_module_imports_with_logging_decorator(self):
        """The with_logging decorator must be in scope so we can stack
        it on Flask route handlers."""
        import app as _app_mod
        assert hasattr(_app_mod, "with_logging")
        assert _app_mod.with_logging is with_logging

    def test_app_module_imports_health_tracker(self):
        """The health tracker singleton must also be reachable from
        the app module so the future /health endpoint can read it."""
        import app as _app_mod
        assert hasattr(_app_mod, "health_tracker")

    def test_app_log_warning_does_not_raise(self, caplog):
        """A migrated call site (``_app_log.warning(msg, error=...)``)
        must run without raising — guards against accidental API
        regressions in future refactors."""
        import app as _app_mod
        with caplog.at_level(_stdlib_logging.WARNING):
            _app_mod._app_log.warning(
                "[test] smoke", error="simulated", context="unit-test"
            )
        # No exception, and at least one record was emitted.
        assert any(
            r.name == "novel-agent.app" for r in caplog.records
        ), "_app_log.warning did not emit a structured record"


class TestRouteHandlerDecorated:
    """The ``@with_logging`` decorator applied to a Flask route must
    not break URL routing. We test on a clean throwaway Flask app to
    avoid coupling to the real route table."""

    def test_with_logging_on_flask_route_still_routes(self):
        from flask import Flask
        app = Flask(__name__)

        @app.route("/__test_with_logging__", methods=["GET"])
        @with_logging
        def decorated_route():
            return "ok", 200

        client = app.test_client()
        res = client.get("/__test_with_logging__")
        assert res.status_code == 200
        assert res.data == b"ok"
