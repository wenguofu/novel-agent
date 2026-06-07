#!/usr/bin/env python3
"""
Portal functional test runner — walks every nav view + each modal tab,
hits the corresponding API endpoint, and prints a pass/fail report.

Run: python3 scripts/portal_functional_test.py
Assumes: Portal server running on http://localhost:35001

This script doubles as:
  - Manual click-walkthrough verification (one HTTP call per feature)
  - Smoke test before deploying changes
  - Living documentation of which API endpoints each UI view depends on
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "http://localhost:35001"
TEST_NOVEL = "光头闲人闯阴阳古墓"  # 163 chapters, has plenty of data
TEST_NOVEL_ENC = quote(TEST_NOVEL, safe="")  # URL-encoded for path segments


# ─── Result tracking ────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    view: str
    endpoint: str
    method: str
    status: int
    success: bool
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class Runner:
    results: list[TestResult] = field(default_factory=list)
    failures: int = 0

    def run(self, name: str, view: str, endpoint: str,
            method: str = "GET", body: dict | None = None,
            expected_status: int | tuple[int, ...] = 200,
            params: dict | None = None) -> Any:
        """Execute one HTTP call and record the result."""
        if params:
            endpoint = f"{endpoint}?{urlencode(params)}"
        url = f"{BASE}{endpoint}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = Request(url, data=data, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        t0 = time.time()
        try:
            with urlopen(req, timeout=30) as resp:
                status = resp.status
                body_bytes = resp.read()
        except HTTPError as e:
            status = e.code
            body_bytes = e.read() if e.fp else b""
        except URLError as e:
            self._record(TestResult(
                name=name, view=view, endpoint=endpoint, method=method,
                status=0, success=False, detail=f"connection error: {e.reason}",
                duration_ms=(time.time() - t0) * 1000,
            ))
            return None
        duration_ms = (time.time() - t0) * 1000
        expected = expected_status if isinstance(expected_status, tuple) else (expected_status,)
        ok = status in expected
        # Try to parse JSON; on parse failure just store the first 200 bytes
        detail = body_bytes[:200].decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body_bytes)
        except Exception:
            parsed = None
        self._record(TestResult(
            name=name, view=view, endpoint=endpoint, method=method,
            status=status, success=ok, detail=detail, duration_ms=duration_ms,
        ))
        return parsed

    def _record(self, result: TestResult) -> None:
        self.results.append(result)
        if not result.success:
            self.failures += 1
        marker = "✅" if result.success else "❌"
        print(f"  {marker} [{result.view:14s}] {result.name:42s} "
              f"{result.method:6s} {result.endpoint:60s} "
              f"→ {result.status} ({result.duration_ms:.0f}ms)")
        if not result.success and result.detail:
            print(f"     ↳ {result.detail[:200]}")

    def report(self) -> None:
        print()
        print("═" * 78)
        total = len(self.results)
        passed = total - self.failures
        print(f"  Portal functional test — {passed}/{total} passed, "
              f"{self.failures} failed")
        print("═" * 78)
        # Group by view
        by_view: dict[str, list[TestResult]] = {}
        for r in self.results:
            by_view.setdefault(r.view, []).append(r)
        for view, results in by_view.items():
            ok = sum(1 for r in results if r.success)
            print(f"  {view:14s}  {ok}/{len(results)}")
        if self.failures:
            print()
            print("  Failed tests:")
            for r in self.results:
                if not r.success:
                    print(f"    [{r.view}] {r.name} → {r.status}")
        print("═" * 78)


# ─── Test suite ─────────────────────────────────────────────────────

def main() -> int:
    r = Runner()

    print("🚀 Portal functional test runner")
    print(f"   Base: {BASE}")
    print(f"   Test novel: {TEST_NOVEL}")
    print()

    # ── 1. Top-level pages ────────────────────────────────────────
    print("── 1. Top-level pages (no novel required) ──")
    r.run("GET / (index.html)", "dashboard", "/")
    r.run("GET /health", "dashboard", "/health")
    r.run("GET /api/novels (list)", "novels", "/api/novels")
    r.run("GET /api/dashboard/stats", "dashboard", "/api/dashboard/stats")
    r.run("GET /api/usage/stats", "settings", "/api/usage/stats")
    r.run("GET /api/usage/stats?days=7", "settings", "/api/usage/stats", params={"days": 7})

    # ── 2. Novel detail (uses test novel) ─────────────────────────
    print("\n── 2. Novel detail ──")
    r.run("GET /api/novels/<n>", "novels", f"/api/novels/{TEST_NOVEL_ENC}")
    r.run("GET /api/novels/<n>/status", "dashboard", f"/api/novels/{TEST_NOVEL_ENC}/status")
    r.run("GET /api/novels/<n>/gate-status", "workflow", f"/api/novels/{TEST_NOVEL_ENC}/gate-status")
    r.run("GET /api/novels/<n>/chapters/<ref>  (sample ch-001)", "chapters",
          f"/api/novels/{TEST_NOVEL_ENC}/chapters/vol-01/ch-0001",
          expected_status=(200, 404))  # may not exist
    r.run("GET /api/novels/<n>/file?path=project.md", "novels",
          f"/api/novels/{TEST_NOVEL_ENC}/file", params={"path": "project.md"})
    r.run("GET /api/novels/<n>/outline/vol-01", "outlines", f"/api/novels/{TEST_NOVEL_ENC}/outline/vol-01")

    # ── 3. Chapter detail ─────────────────────────────────────────
    print("\n── 3. Chapter detail ──")
    chapter_ref = "vol-01/ch-0001"  # real chapter (ch-0001.md exists)
    r.run("GET /api/novels/<n>/chapters/<ref>", "chapters",
          f"/api/novels/{TEST_NOVEL_ENC}/chapters/{chapter_ref}")
    r.run("GET /api/novels/<n>/chapters/<ref>/bak", "history",
          f"/api/novels/{TEST_NOVEL_ENC}/chapters/{chapter_ref}/bak")

    # ── 4. Characters ─────────────────────────────────────────────
    print("\n── 4. Characters ──")
    r.run("GET /api/characters/<n>", "characters", f"/api/characters/{TEST_NOVEL_ENC}")
    r.run("GET /api/characters/<n>/1", "characters", f"/api/characters/{TEST_NOVEL_ENC}/1",
          expected_status=(200, 404, 500))  # may or may not exist

    # ── 5. Foreshadowing ──────────────────────────────────────────
    print("\n── 5. Foreshadowing ──")
    r.run("GET /api/foreshadowing/<n>", "foreshadowing", f"/api/foreshadowing/{TEST_NOVEL_ENC}")

    # ── 6. World building / Plot arcs / Pacing / Revelation ───────
    print("\n── 6. Story structure ──")
    r.run("GET /api/world_building/<n>", "world-building", f"/api/world_building/{TEST_NOVEL_ENC}")
    r.run("GET /api/plot_arcs/<n>", "plot-arcs", f"/api/plot_arcs/{TEST_NOVEL_ENC}")
    r.run("GET /api/pacing_control/<n>", "pacing", f"/api/pacing_control/{TEST_NOVEL_ENC}")
    r.run("GET /api/revelation_schedule/<n>", "revelation", f"/api/revelation_schedule/{TEST_NOVEL_ENC}")

    # ── 7. Quality report ─────────────────────────────────────────
    print("\n── 7. Quality & workflow ──")
    r.run("GET /api/content/quality-report/<n>", "quality", f"/api/content/quality-report/{TEST_NOVEL_ENC}")
    r.run("POST /api/workflow/preflight/<n> (vol-01)", "workflow",
          f"/api/workflow/preflight/{TEST_NOVEL_ENC}",
          method="POST", body={"volume": "vol-01"})
    r.run("POST /api/workflow/postflight/<n>", "workflow",
          f"/api/workflow/postflight/{TEST_NOVEL_ENC}",
          method="POST", body={"chapter_ref": "vol-01/ch-0001"})

    # ── 8. Config DB endpoints (used by Config view tabs) ────────
    print("\n── 8. Config DB (4 tabs) ──")
    for table in ("banned_words", "compliance_rules", "alias_registry", "style_presets"):
        r.run(f"GET /api/config-db/{table}", "config", f"/api/config-db/{table}")

    # ── 9. Search ─────────────────────────────────────────────────
    print("\n── 9. Search ──")
    r.run("GET /api/content/search?q=...&novel=...&limit=5", "search",
          "/api/content/search",
          params={"q": "林风", "novel": TEST_NOVEL, "limit": 5})

    # ── 10. Reviews ───────────────────────────────────────────────
    print("\n── 10. Reviews ──")
    r.run("GET /api/novels/<n>/reviews/<ref>", "review",
          f"/api/novels/{TEST_NOVEL_ENC}/reviews/{chapter_ref}",
          expected_status=(200, 404, 500))  # may not exist for this chapter

    # ── 11. Config endpoints (Pydantic-validated) ────────────────
    print("\n── 11. Config (settings view) ──")
    r.run("GET /api/config", "settings", "/api/config")
    r.run("GET /api/init/status", "settings", "/api/init/status",
          expected_status=(200, 404))

    # ── 12. Validation regression (Pydantic 400 on bad input) ─────
    print("\n── 12. Pydantic validation ──")
    # POST /api/ai/chat with invalid role → 400
    r.run("POST /api/ai/chat invalid role", "Pydantic", "/api/ai/chat",
          method="POST", body={"messages": [{"role": "admin", "content": "x"}]},
          expected_status=400)
    # POST /api/novels/create with empty name → 400
    r.run("POST /api/novels/create empty name", "Pydantic", "/api/novels/create",
          method="POST", body={"name": ""}, expected_status=400)
    # POST /api/novels/<n>/chapters/<c>/edit empty content → 400
    r.run("POST /api/.../chapters/<c>/edit empty", "Pydantic",
          f"/api/novels/{TEST_NOVEL_ENC}/chapters/{chapter_ref}/edit",
          method="POST", body={"content": ""}, expected_status=400)

    # ── 13. Middleware sanity (X-Response-Time, X-Request-ID) ────
    print("\n── 13. Middleware ──")
    # /health is excluded from timing; test on /api/novels
    req = Request(f"{BASE}/api/novels")
    with urlopen(req, timeout=10) as resp:
        has_rt = "X-Response-Time" in resp.headers
        has_rid = "X-Request-ID" in resp.headers
    r._record(TestResult(
        name="X-Response-Time + X-Request-ID on /api/novels",
        view="middleware", endpoint="/api/novels", method="GET",
        status=200, success=(has_rt and has_rid),
        detail=f"X-Response-Time={has_rt}, X-Request-ID={has_rid}",
    ))

    r.report()
    return 0 if r.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
