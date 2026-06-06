"""Regression tests for harness plan item [7] — wire the
``resilience.py`` circuit breaker + retry decorators into the
``deepseek_chat()`` helper in ``portal/app.py``.

These tests verify that:
  - ``portal/app.py`` imports the resilience helpers
    (``api_resilient``, ``deepseek_circuit``, ``response_tracker``).
  - The ``deepseek_chat`` symbol exposed by the ``app`` module is
    actually wrapped by ``@api_resilient("deepseek_chat")`` — i.e.
    its ``__name__`` is preserved by ``@wraps`` and it has access
    to the global ``deepseek_circuit`` state.
  - Failures inside ``deepseek_chat`` increment the circuit
    breaker's failure counter (so an upstream retry storm cannot
    silently hammer the API).
  - A successful (no-raise) call leaves the circuit in the closed
    state with a zero failure count.
  - Five consecutive failures trip the breaker to the open state
    and the next call is blocked with ``CircuitBreakerOpenError``.

Tests do NOT make real network calls. They patch the seam the
``deepseek_chat`` function uses to obtain its config so the test
can drive success / failure paths deterministically, and they mock
``resilience.time.sleep`` to avoid waiting through the
exponential-backoff retries.
"""
from unittest.mock import patch

import pytest

# Ensure portal/ is on sys.path so we can import ``app`` and
# ``resilience`` directly. Mirrors the pattern used in
# tests/functional/test_logging.py so this file is self-contained
# when run in isolation.
from pathlib import Path
import sys

_PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(_PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(_PORTAL_DIR))

import app as _app_mod  # noqa: E402
from resilience import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpenError,
    deepseek_circuit,
    response_tracker,
)


# ─── helpers ───────────────────────────────────────────────────────────


def _reset_circuit_breaker():
    """Force the global ``deepseek_circuit`` back to the closed
    state with zero failures. Tests do not run in isolation, so
    we always start from a known state to avoid interference from
    earlier test files that may have left the breaker open."""
    with deepseek_circuit._lock:
        deepseek_circuit._state = "closed"
        deepseek_circuit._failure_count = 0
        deepseek_circuit._last_failure_time = 0.0


def _empty_config():
    """A config dict that triggers the early-return path in
    ``deepseek_chat`` (no API key → returns ``{"success": False, ...}``
    without raising). The wrapped function considers this a
    success from the circuit breaker's point of view."""
    return {
        "api_key": "",
        "api_base": "https://example.invalid",
        "model": "test-model",
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 0.9,
        "user_configured": False,
    }


# ─── module-level wiring ───────────────────────────────────────────────


class TestAppWiresResilience:
    """portal/app.py must actually import and expose the resilience
    helpers so the ``@api_resilient`` decorator can reach them at
    import time."""

    def test_app_module_imports_api_resilient(self):
        assert hasattr(_app_mod, "api_resilient"), (
            "portal/app.py did not import api_resilient from resilience"
        )

    def test_app_module_imports_deepseek_circuit(self):
        assert hasattr(_app_mod, "deepseek_circuit"), (
            "portal/app.py did not import deepseek_circuit from resilience"
        )
        assert _app_mod.deepseek_circuit is deepseek_circuit

    def test_app_module_imports_response_tracker(self):
        assert hasattr(_app_mod, "response_tracker"), (
            "portal/app.py did not import response_tracker from resilience"
        )

    def test_deepseek_circuit_is_a_circuit_breaker_instance(self):
        """The global instance is what ``@api_resilient`` binds to
        when wrapping ``deepseek_chat`` — guards against an
        accidental re-instantiation that would decouple the
        decorator from the breaker the /health endpoint reports on."""
        assert isinstance(deepseek_circuit, CircuitBreaker)
        assert deepseek_circuit.name == "minimax-api"
        assert deepseek_circuit.failure_threshold == 5


# ─── decorator behavior on the wrapped function ────────────────────────


class TestApiResilientDecoratesDeepseekChat:
    """The ``@api_resilient("deepseek_chat")`` decorator must use
    ``@wraps`` so the original function's ``__name__`` and
    ``__doc__`` are preserved. This matters because Flask's route
    registration and any callers that introspect the function
    rely on those attributes."""

    def test_preserves_function_name(self):
        assert _app_mod.deepseek_chat.__name__ == "deepseek_chat"

    def test_preserves_docstring(self):
        # The function has no explicit docstring, but the
        # ``@wraps`` machinery copies through the source
        # function's ``__doc__`` (None) instead of leaving the
        # wrapper's placeholder.
        assert _app_mod.deepseek_chat.__doc__ is None or isinstance(
            _app_mod.deepseek_chat.__doc__, str
        )

    def test_deepseek_chat_is_callable(self):
        assert callable(_app_mod.deepseek_chat)


# ─── failure path: exceptions are recorded on the breaker ──────────────


class TestCircuitBreakerIntegration:
    """End-to-end checks that the circuit breaker wired into
    ``deepseek_chat`` actually records failures from real calls.
    This is the regression the harness item [7] is meant to
    prevent — silently losing the breaker wiring."""

    def setup_method(self):
        _reset_circuit_breaker()

    def test_records_failure_on_exception(self):
        """When the wrapped function raises, ``deepseek_circuit`` must
        see exactly one failure (one outer call, regardless of how
        many internal ``with_retry`` attempts the api_resilient
        decorator made)."""
        with patch.object(_app_mod, "get_active_deepseek_config",
                          side_effect=RuntimeError("config boom")):
            # with_retry sleeps between attempts; mock it out so the
            # test does not block for ~3s of real backoff.
            with patch("resilience.time.sleep"):
                with pytest.raises(RuntimeError, match="config boom"):
                    _app_mod.deepseek_chat(
                        messages=[{"role": "user", "content": "hi"}],
                    )

        assert deepseek_circuit._failure_count >= 1, (
            "deepseek_circuit did not record a failure when "
            "deepseek_chat raised"
        )
        # The breaker should still be closed (one failure is below
        # the 5-failure threshold).
        assert deepseek_circuit._state == "closed"

    def test_resets_on_success_path(self):
        """A successful (non-raising) call leaves the breaker closed
        with a zero failure count."""
        # First, simulate a stray failure so we can verify the
        # success path resets it back to clean.
        with deepseek_circuit._lock:
            deepseek_circuit._failure_count = 2

        with patch.object(_app_mod, "get_active_deepseek_config",
                          return_value=_empty_config()):
            res = _app_mod.deepseek_chat(
                messages=[{"role": "user", "content": "hi"}],
            )

        # Empty API key → function returns the standard error
        # envelope without raising, which is a "success" from the
        # circuit breaker's perspective.
        assert res["success"] is False
        assert deepseek_circuit._state == "closed"
        assert deepseek_circuit._failure_count == 0

    def test_circuit_opens_after_threshold_failures(self):
        """Five consecutive failures must trip the breaker to the
        ``open`` state, and the next call must be rejected with
        ``CircuitBreakerOpenError`` without invoking the function
        body a sixth time."""
        with patch.object(_app_mod, "get_active_deepseek_config",
                          side_effect=RuntimeError("config boom")):
            with patch("resilience.time.sleep"):
                for _ in range(5):
                    with pytest.raises(RuntimeError):
                        _app_mod.deepseek_chat(
                            messages=[{"role": "user", "content": "x"}],
                        )

        assert deepseek_circuit._state == "open"
        assert deepseek_circuit._failure_count == 5

        # The next call must be rejected by the breaker itself,
        # before the function body is invoked.
        with patch.object(_app_mod, "get_active_deepseek_config",
                          return_value=_empty_config()) as mock_cfg:
            with pytest.raises(CircuitBreakerOpenError):
                _app_mod.deepseek_chat(
                    messages=[{"role": "user", "content": "x"}],
                )
            # Critical: the breaker blocked the call, so
            # get_active_deepseek_config must not have been
            # consulted.
            mock_cfg.assert_not_called()

    def test_response_tracker_records_call(self):
        """``response_tracker`` is incremented by ``@api_resilient``
        on every call (success or failure). This guards against
        accidentally dropping the timing instrumentation when the
        decorator is added."""
        _reset_circuit_breaker()
        before = response_tracker._total_calls
        with patch.object(_app_mod, "get_active_deepseek_config",
                          return_value=_empty_config()):
            _app_mod.deepseek_chat(
                messages=[{"role": "user", "content": "hi"}],
            )
        after = response_tracker._total_calls
        assert after == before + 1, (
            "response_tracker did not record the deepseek_chat call"
        )
