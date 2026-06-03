"""Tests for scripts/inventory_endpoints.py — uses fixture mini_app.py for unit tests,
then a single integration test against the real portal/app.py."""
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "mini_app.py"
REAL_APP = Path(__file__).parent.parent / "portal" / "app.py"

def test_scan_flask_routes_returns_8_from_fixture():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    # Fixture: 5 originals + <int:cid> PUT/DELETE + 4-method CRUD + async def.
    # The bare `async def _helper` outside any decorator must be ignored.
    assert len(endpoints) == 8

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


def test_scan_handles_int_converter_in_route():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    by_route = {ep.route: ep.methods for ep in endpoints}
    assert by_route["/api/characters/<name>/<int:cid>"] == ["PUT", "DELETE"]


def test_scan_handles_four_method_list():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    by_route = {ep.route: ep.methods for ep in endpoints}
    assert by_route["/api/crud/<int:row_id>"] == ["GET", "POST", "PUT", "DELETE"]


def test_scan_handles_async_function_def():
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    async_ep = next(ep for ep in endpoints if ep.route == "/api/async/<name>")
    assert async_ep.func_name == "api_async"


def test_scan_ignores_undecorated_async_helper():
    """The bare `async def _helper()` in the fixture has no @app.route
    decorator and must be ignored."""
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(FIXTURE)
    names = {ep.func_name for ep in endpoints}
    assert "_helper" not in names


def test_scan_extracts_repo_calls_from_function_body():
    """Synthetic source with `repo.list_novels()` should produce endpoint with
    repo_calls=['list_novels']."""
    from inventory_endpoints import scan_flask_routes
    src = '''
from flask import Flask
app = Flask(__name__)

@app.route("/api/x")
def api_x():
    repo = get_repo()
    return repo.list_novels()
'''
    fixture = Path("/tmp/_mini_with_repo.py")
    fixture.write_text(src)
    try:
        eps = scan_flask_routes(fixture)
        assert eps[0].repo_calls == ["list_novels"]
    finally:
        fixture.unlink()


def test_scan_extracts_db_calls_from_function_body():
    """Synthetic source with `session.add(...)` and `db.execute(...)` should
    produce endpoint with db_calls=['add', 'commit', 'execute']."""
    from inventory_endpoints import scan_flask_routes
    src = '''
from flask import Flask
app = Flask(__name__)

@app.route("/api/x")
def api_x():
    session.add(Novel(name="x"))
    session.commit()
    rows = db.execute("SELECT 1").fetchall()
    return rows
'''
    fixture = Path("/tmp/_mini_with_db.py")
    fixture.write_text(src)
    try:
        eps = scan_flask_routes(fixture)
        assert "add" in eps[0].db_calls
        assert "commit" in eps[0].db_calls
        assert "execute" in eps[0].db_calls
    finally:
        fixture.unlink()


def test_endpoint_with_no_repo_or_db_calls_yields_empty_lists():
    """The fixture mini_app.py has inert function bodies — no repo/db calls."""
    from inventory_endpoints import scan_flask_routes
    eps = scan_flask_routes(FIXTURE)
    root_ep = next(ep for ep in eps if ep.route == "/")
    assert root_ep.repo_calls == []
    assert root_ep.db_calls == []
