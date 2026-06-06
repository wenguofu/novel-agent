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
