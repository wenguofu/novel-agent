"""Tests for scripts/inventory_endpoints.py — uses fixture mini_app.py for unit tests,
then a single integration test against the real portal/app.py."""
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "mini_app.py"
REAL_APP = Path(__file__).parent.parent / "portal" / "app.py"

def test_scan_flask_routes_returns_5_from_fixture():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    assert len(endpoints) == 5

def test_scan_flask_routes_extracts_route_path():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    routes = {ep.route for ep in endpoints}
    assert "/" in routes
    assert "/api/novels" in routes
    assert "/api/novels/<name>" in routes
    assert "/api/novels/<name>/chapters/<path:ref>" in routes

def test_scan_flask_routes_extracts_methods():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    by_route = {ep.route: ep.methods for ep in endpoints}
    assert by_route["/"] == ["GET"]
    assert by_route["/api/novels"] == ["GET", "POST"]
    assert by_route["/api/novels/<name>"] == ["GET"]
    assert by_route["/api/novels/<name>/chapters/<path:ref>"] == ["DELETE"]

def test_scan_flask_routes_extracts_func_name_and_line():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    delete_ep = next(ep for ep in endpoints if "chapters" in ep.route)
    assert delete_ep.func_name == "api_delete_chapter"
    assert isinstance(delete_ep.line_no, int) and delete_ep.line_no > 0

def test_scan_flask_routes_extracts_docstring_first_line():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    root_ep = next(ep for ep in endpoints if ep.route == "/")
    assert root_ep.docstring == "Root index — serves the SPA shell."

def test_inventory_real_portal_app_has_83_endpoints():
    """Integration: scan the real portal/app.py and verify count matches design doc."""
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(REAL_APP)
    # Real count from manual grep on 2026-06-03. Update only if endpoints are added/removed.
    assert len(endpoints) == 83, f"expected 83 endpoints, got {len(endpoints)} — portal/app.py changed"
