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

def test_inventory_real_portal_app_has_82_endpoints():
    """Integration: scan the real portal/app.py and verify count matches design doc."""
    from inventory_endpoints import scan_flask_routes
    endpoints = scan_flask_routes(REAL_APP)
    # Real count from manual grep on 2026-06-04 (post-dedupe: was 83, now 82).
    # The 83 came from two `@app.route("/")` decorators on the `index` function
    # in mutually exclusive if/else branches (React build vs Jinja template);
    # refactored into a single conditional index() — see commit history.
    # Updated 2026-06-06 (harness item [9]): added /health endpoint, now 83.
    # Updated 2026-06-07 (arch 4.1): added /api/dashboard/stats, now 84.
    # Updated 2026-06-07 (arch 1.1): added 4 chapter .bak history endpoints, now 88.
    assert len(endpoints) == 88, f"expected 88 endpoints, got {len(endpoints)} — portal/app.py changed"


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


REPO_FIXTURE = Path(__file__).parent / "fixtures" / "mini_repo.py"


def test_scan_repository_returns_index_of_methods():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    assert "get_novel" in index
    assert "list_chapters" in index
    assert "upsert_outline" in index
    assert index["get_novel"]["docstring"] == "Look up a novel by name."


def test_scan_repository_extracts_param_names_and_defaults():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    assert "novel_name" in index["get_novel"]["params"]
    assert "volume" in index["upsert_outline"]["params"]
    assert "content" in index["upsert_outline"]["params"]
    assert "word_count" in index["upsert_outline"]["params"]
    # word_count has default = 0, so it appears in 'defaults' too
    assert "word_count" in index["upsert_outline"]["defaults"]


def test_scan_repository_infers_table_from_method_name():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    assert index["get_novel"]["tables"] == ["novels"]
    assert index["list_chapters"]["tables"] == ["chapters"]
    assert index["upsert_outline"]["tables"] == ["outlines"]
