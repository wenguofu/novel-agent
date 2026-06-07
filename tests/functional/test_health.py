"""Health endpoint + response time middleware tests (harness plan item [9]).

Covers the four-dim contract for the new /health route and the
before_request/after_request middleware that adds X-Response-Time and
X-Request-ID headers to every response.
"""
import re


# ─── /health endpoint ──────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200_with_status(self, client):
        res = client.get("/health")
        assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.data!r}"
        data = res.get_json()
        assert data is not None, f"no JSON body: {res.data!r}"
        assert data.get("success") is True, f"expected success=True, got {data!r}"
        assert "health" in data, f"missing 'health' key: {data!r}"

    def test_health_payload_shape(self, client):
        res = client.get("/health")
        assert res.status_code in (200, 503), f"unexpected status: {res.status_code}"
        data = res.get_json()
        health = data["health"]
        # db status (ok | error)
        assert "db" in health, f"missing 'db' in health: {health!r}"
        assert health["db"] in ("ok", "error"), f"unexpected db status: {health['db']!r}"
        # response time avg in ms (int-friendly, allow float for fractional)
        assert "response_time_avg_ms" in health, \
            f"missing 'response_time_avg_ms': {health!r}"
        rt = health["response_time_avg_ms"]
        assert isinstance(rt, (int, float)), f"avg must be numeric, got {type(rt)}"
        assert rt >= 0, f"avg must be >=0, got {rt}"
        # circuit breaker state
        assert "circuit_breaker_state" in health, \
            f"missing 'circuit_breaker_state': {health!r}"
        assert health["circuit_breaker_state"] in ("closed", "open", "half-open"), \
            f"unexpected circuit state: {health['circuit_breaker_state']!r}"

    def test_health_does_not_set_response_time_header(self, client):
        # The /health endpoint must be excluded from response-time tracking
        # to avoid skewing stats and recursion in the after_request hook.
        res = client.get("/health")
        assert "X-Response-Time" not in res.headers, \
            f"/health should be excluded from timing, got {res.headers.get('X-Response-Time')!r}"


# ─── Response-time + request-id middleware ─────────────────────────────

class TestMiddleware:
    def test_response_time_header_set(self, client):
        # Use a route that does not require DB state — /api/novels is a
        # safe GET that always returns 200 with a JSON envelope.
        res = client.get("/api/novels")
        assert "X-Response-Time" in res.headers, \
            f"missing X-Response-Time header: {dict(res.headers)!r}"
        ms_value = res.headers["X-Response-Time"]
        # Should be a non-negative integer in milliseconds
        assert re.match(r"^\d+$", ms_value), \
            f"X-Response-Time should be integer ms, got {ms_value!r}"
        assert int(ms_value) >= 0, f"X-Response-Time must be >=0, got {ms_value}"

    def test_request_id_header_set(self, client):
        res = client.get("/api/novels")
        assert "X-Request-ID" in res.headers, \
            f"missing X-Request-ID header: {dict(res.headers)!r}"
        rid = res.headers["X-Request-ID"]
        # Should be a non-empty string (UUID or similar)
        assert isinstance(rid, str) and len(rid) > 0, \
            f"X-Request-ID should be a non-empty string, got {rid!r}"

    def test_response_time_header_on_existing_routes(self, client):
        # Verify the middleware is transparent across multiple routes
        for path in ("/api/novels", "/"):
            res = client.get(path)
            assert "X-Response-Time" in res.headers, \
                f"X-Response-Time missing on {path}: {dict(res.headers)!r}"
            assert "X-Request-ID" in res.headers, \
                f"X-Request-ID missing on {path}: {dict(res.headers)!r}"


# ─── Resilience: after_request hook must not break the response ──────

class TestAfterRequestResilience:
    """The ``_after_request_set_timing`` middleware calls
    ``health_tracker.record_request``. If that call raises (corrupt
    in-memory state, type error from a future refactor, etc.) the
    middleware must:

    1. NOT turn the request into a 500.
    2. Still set ``X-Response-Time`` and ``X-Request-ID``.
    3. Log the failure at DEBUG level so it's visible in dev logs.

    This is the regression test for harness plan item [5] (the
    last silent ``except Exception: pass`` in ``portal/app.py``).
    """

    def test_record_request_failure_does_not_500(self, client, monkeypatch, caplog):
        """If ``health_tracker.record_request`` raises, the response
        must still come back 200/200-ish with the timing header."""
        import logging
        import app as _app_mod
        from logging_config import health_tracker

        def boom(*a, **kw):
            raise RuntimeError("simulated tracker failure")
        monkeypatch.setattr(health_tracker, "record_request", boom)

        with caplog.at_level(logging.DEBUG, logger="novel-agent.app"):
            res = client.get("/api/novels")

        # Response must not be 500
        assert res.status_code < 500, (
            f"middleware raised, got {res.status_code}: {res.data!r}"
        )
        # X-Response-Time must still be set (the except block must not
        # have skipped the rest of the response setup)
        assert "X-Response-Time" in res.headers, (
            "X-Response-Time missing after tracker failure; "
            "the except block must not skip header assignment"
        )
        # X-Request-ID must still be set
        assert "X-Request-ID" in res.headers, (
            "X-Request-ID missing after tracker failure"
        )

    def test_record_request_failure_emits_debug_log(self, client, monkeypatch, caplog):
        """A failed ``record_request`` must produce a DEBUG record on
        the ``novel-agent.app`` logger — this is the contract that
        replaces the silent ``pass`` removed in this commit."""
        import logging
        from logging_config import health_tracker

        def boom(*a, **kw):
            raise RuntimeError("simulated tracker failure for logging test")
        monkeypatch.setattr(health_tracker, "record_request", boom)

        with caplog.at_level(logging.DEBUG, logger="novel-agent.app"):
            client.get("/api/novels")

        # Look for our specific message
        matching = [
            r for r in caplog.records
            if r.name == "novel-agent.app"
            and "health_tracker.record_request failed" in r.getMessage()
        ]
        assert matching, (
            f"no DEBUG log emitted for record_request failure; "
            f"got: {[r.getMessage() for r in caplog.records if r.name == 'novel-agent.app']}"
        )
        assert matching[0].levelno == logging.DEBUG

    def test_no_silent_pass_in_after_request(self):
        """Static guard: the after_request hook in portal/app.py must
        not contain ``except Exception:`` followed by a bare ``pass``.
        If this test fails, someone re-introduced a silent exception
        swallow in the timing middleware."""
        from pathlib import Path
        import re
        portal_dir = Path(__file__).resolve().parent.parent.parent / "portal"
        app_path = portal_dir / "app.py"
        text = app_path.read_text(encoding="utf-8")
        # Find every "except Exception:" and look at the next 3 lines
        # for a bare "pass". The fix in this commit changed the body
        # to "logging.getLogger(...).debug(...)".
        pattern = re.compile(
            r"except\s+Exception(?:\s+as\s+\w+)?\s*:\s*\n\s*pass\s*\n",
            re.MULTILINE,
        )
        matches = pattern.findall(text)
        assert not matches, (
            f"Found {len(matches)} silent except-pass patterns in "
            f"portal/app.py — see harness plan item [5]"
        )
