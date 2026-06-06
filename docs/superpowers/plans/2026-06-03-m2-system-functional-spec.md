# M2 System Functional Spec — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a machine-verifiable full API spec doc (`docs/system-functional-spec.md`) covering all 83 endpoints in `portal/app.py`, plus 3 supporting scripts and Manual Notes for ~25 core endpoints. Folds in 2 M1 follow-ups (orphan helper cleanup + stale OpenSpec note).

**Architecture:** Data-driven pipeline. `inventory_endpoints.py` does an AST walk of `portal/app.py` + `portal/repository.py`, emits a stable JSON manifest. `render_spec.py` renders a Jinja2 template with the manifest + preserves `<!-- MANUAL: key -->` blocks. `verify_spec.py` is a CI gate (5 checks, exits non-zero on any drift). All scripts use only stdlib + `jinja2` (already a dep).

**Tech Stack:** Python 3 stdlib (`ast`, `json`, `re`, `pathlib`, `argparse`), Jinja2 ≥3.0, pytest. No new deps.

**Out of scope:** Functional tests (M3), pre-commit hook (M3), agent-CR (continuous).

---

## File Structure

**New files:**
- `scripts/inventory_endpoints.py` — AST scanner, emits `docs/auto-inventory.json`. ~150 LOC.
- `scripts/render_spec.py` — Jinja2 renderer, emits `docs/system-functional-spec.md`. ~100 LOC.
- `scripts/verify_spec.py` — CI gate, 5 checks, exit 0/1. ~120 LOC.
- `docs/system-functional-spec.j2.md` — Jinja2 template with Manual Notes anchors. ~300 lines.
- `docs/auto-inventory.json` — generated manifest, **committed** (it IS the spec's data). ~83 entries.
- `docs/system-functional-spec.md` — generated spec doc, **committed**. ~1500 lines.
- `tests/test_inventory_endpoints.py` — fixture-based AST tests. ~120 LOC.
- `tests/test_render_spec.py` — snapshot + preservation tests. ~80 LOC.
- `tests/test_verify_spec.py` — 5-check test cases. ~100 LOC.
- `tests/fixtures/mini_app.py` — 5-endpoint Flask module for AST tests. ~30 LOC.
- `tests/fixtures/mini_repo.py` — 3-method class for signature tests. ~20 LOC.

**Modified files:**
- `openspec/specs/context-builder.md` — line ~93, remove "Pre-existing test failure" stale note (now resolved in M1).
- `portal/context_builder.py` — Task 10 may delete `_build_fallback_state_context` (orphan) and `build_context`'s nonexistent-novel branch becomes the only path.

**No changes to:** `portal/app.py`, `portal/repository.py`, `portal/models_orm.py` (M2 is read-only on the runtime codebase).

---

## Conventions used throughout

- **Stable keys**: `METHOD_<route>` (e.g. `POST_/api/context/build`) — used for Manual Notes anchors.
- **All scripts**: `python3 scripts/<name>.py` from repo root.
- **All scripts**: `argparse` with `--help`, sane defaults, no required args.
- **Test fixtures**: Use synthetic `tests/fixtures/mini_app.py` (5 endpoints) for AST unit tests; use the REAL `portal/app.py` for the 1 final integration assertion in `test_inventory_endpoints.py`.
- **JSON manifest schema** (stable, never break):
  ```json
  {
    "generated_at": "2026-06-03T...Z",
    "source": "portal/app.py",
    "endpoint_count": 83,
    "endpoints": [
      {
        "key": "POST_/api/context/build",
        "route": "/api/context/build",
        "methods": ["POST"],
        "func_name": "api_context_build",
        "line_no": 2835,
        "docstring": "Build 12-layer system prompt for chapter writing.",
        "repo_calls": ["list_genre_rules", "list_banned_words"],
        "db_calls": [],
        "tables_read": ["genre_rules", "banned_words"],
        "tables_written": []
      }
    ]
  }
  ```

---

### Task 1: AST scanner — discover Flask routes

**Files:**
- Create: `scripts/inventory_endpoints.py` (initial)
- Create: `tests/fixtures/mini_app.py`
- Create: `tests/test_inventory_endpoints.py` (initial)

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/mini_app.py`:
```python
"""Fixture for AST scanner tests. NOT a real Flask app — function bodies are inert."""
from flask import Flask

app = Flask(__name__)

@app.route("/")
def root():
    """Root index — serves the SPA shell."""
    return "<html></html>"

@app.route("/api/novels", methods=["GET", "POST"])
def api_novels():
    """List or create novels."""
    return []

@app.route("/api/novels/<name>")
def api_novel(name):
    """Get one novel by name."""
    return {}

@app.route("/api/novels/<name>/chapters/<path:ref>", methods=["DELETE"])
def api_delete_chapter(name, ref):
    """Delete a chapter."""
    return {}

@app.route("/api/static/<path:filename>")
def static_files(filename):
    """Serve static assets."""
    return ""
```

Create `tests/test_inventory_endpoints.py`:
```python
"""Tests for scripts/inventory_endpoints.py — uses fixture mini_app.py for unit tests,
then a single integration test against the real portal/app.py."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wgfu/Desktop/novel-agent && python3 -m pytest tests/test_inventory_endpoints.py -v`
Expected: `ModuleNotFoundError: No module named 'inventory_endpoints'`

- [ ] **Step 3: Implement minimal scanner**

Create `scripts/inventory_endpoints.py`:
```python
#!/usr/bin/env python3
"""AST scanner for Flask routes in portal/app.py.

Emits docs/auto-inventory.json with one entry per (route, methods) tuple.
Uses only stdlib — jinja2 is only required by the renderer (render_spec.py).
"""
import ast
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass
class Endpoint:
    key: str           # e.g. "POST_/api/context/build"
    route: str
    methods: List[str]
    func_name: str
    line_no: int
    docstring: str


def _first_docstring_line(node: ast.FunctionDef) -> str:
    """Return the first non-empty line of the function's docstring, or ''."""
    if not (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        return ""
    return node.body[0].value.value.strip().split("\n", 1)[0].strip()


def _methods_from_decorator(decorator: ast.expr, default: List[str]) -> List[str]:
    """Pull the methods= kwarg out of a route decorator, or return defaults."""
    if not isinstance(decorator, ast.Call):
        return default
    for kw in decorator.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            methods = []
            for elt in kw.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    methods.append(elt.value)
            return methods or default
    return default


def _route_from_decorator(decorator: ast.expr) -> str | None:
    """Return the route string from an @app.route("...") decorator, or None."""
    if not isinstance(decorator, ast.Call):
        return None
    if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "route":
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            return decorator.args[0].value
    return None


def scan_flask_routes(source: Path) -> List[Endpoint]:
    """Parse `source` (a .py file) and return one Endpoint per Flask route.

    Walks every FunctionDef in the module, inspects its @app.route / @app.<method>
    decorators, and emits one Endpoint per (route, methods) tuple found.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    endpoints: List[Endpoint] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            route = _route_from_decorator(decorator)
            if route is None:
                continue
            methods = _methods_from_decorator(decorator, default=["GET"])
            docstring = _first_docstring_line(node)
            for method in methods:
                key = f"{method}_{route}"
                endpoints.append(Endpoint(
                    key=key,
                    route=route,
                    methods=[method],
                    func_name=node.name,
                    line_no=decorator.lineno,
                    docstring=docstring,
                ))
    return endpoints


# --- CLI ---

def build_manifest(source: Path) -> dict:
    endpoints = scan_flask_routes(source)
    return {
        "generated_at": "",  # filled by main() at CLI time
        "source": str(source),
        "endpoint_count": len(endpoints),
        "endpoints": [asdict(ep) for ep in endpoints],
    }


def main() -> int:
    import argparse
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--source", type=Path, default=Path("portal/app.py"),
                        help="Path to the Flask app module (default: portal/app.py)")
    parser.add_argument("--out", type=Path, default=Path("docs/auto-inventory.json"),
                        help="Path to write JSON manifest (default: docs/auto-inventory.json)")
    args = parser.parse_args()
    manifest = build_manifest(args.source)
    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {manifest['endpoint_count']} endpoints to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Make it importable from tests by adding `scripts/` to `sys.path` in the test file's conftest — see Step 4.

- [ ] **Step 4: Make scripts/ importable from tests**

Append to `tests/conftest.py` (create if missing):
```python
"""Shared pytest config: make scripts/ importable."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_inventory_endpoints.py -v`
Expected: 6 passed (5 unit + 1 integration showing 83 real endpoints)

- [ ] **Step 6: Smoke-test the CLI**

Run: `python3 scripts/inventory_endpoints.py`
Expected: `Wrote 83 endpoints to docs/auto-inventory.json`
Verify: `python3 -c "import json; d=json.load(open('docs/auto-inventory.json')); print(d['endpoint_count'], len(d['endpoints']))"`
Expected: `83 83`

- [ ] **Step 7: Commit**

```bash
git add scripts/inventory_endpoints.py tests/fixtures/mini_app.py tests/test_inventory_endpoints.py tests/conftest.py docs/auto-inventory.json
git commit -m "feat(M2): AST scanner for Flask routes + first 83-endpoint manifest"
```

---

### Task 2: Per-endpoint body analysis — repo/db calls

**Files:**
- Modify: `scripts/inventory_endpoints.py`
- Modify: `tests/test_inventory_endpoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_inventory_endpoints.py`:
```python
def test_scan_extracts_repo_calls_from_function_body():
    """Fixture mini_app.py doesn't have repo calls — extend the test with a
    inline string source that does."""
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
    from inventory_endpoints import scan_flask_routes
    eps = scan_flask_routes(FIXTURE)
    root_ep = next(ep for ep in eps if ep.route == "/")
    assert root_ep.repo_calls == []
    assert root_ep.db_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_inventory_endpoints.py -v -k "repo_calls or db_calls or empty_lists"`
Expected: 3 failures with `AttributeError: 'Endpoint' object has no attribute 'repo_calls'`

- [ ] **Step 3: Extend Endpoint dataclass + scan logic**

Replace the `Endpoint` dataclass in `scripts/inventory_endpoints.py`:
```python
@dataclass
class Endpoint:
    key: str
    route: str
    methods: List[str]
    func_name: str
    line_no: int
    docstring: str
    repo_calls: List[str]      # e.g. ["list_novels", "get_chapter"]
    db_calls: List[str]        # e.g. ["add", "commit", "execute"]
    tables_read: List[str]     # heuristic: filled in Task 3 via repo signature index
    tables_written: List[str]  # same
```

Add a new helper function after `_route_from_decorator`:
```python
def _extract_body_calls(func_node: ast.FunctionDef) -> tuple[list[str], list[str], list[str]]:
    """Walk a function body and collect:
      - repo.<method>() calls
      - db/session.<method>() calls
      - tables referenced via repo_calls (best-effort: snake_case name heuristic)
    Returns (repo_calls, db_calls, tables_guessed).
    """
    repo_calls: list[str] = []
    db_calls: list[str] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            owner = node.func.value
            attr = node.func.attr
            if isinstance(owner, ast.Name) and owner.id in ("repo", "r"):
                if attr not in repo_calls:
                    repo_calls.append(attr)
            elif isinstance(owner, ast.Name) and owner.id in ("db", "session"):
                if attr not in db_calls:
                    db_calls.append(attr)
    # Heuristic: repo method names often start with table name (list_characters, get_chapter)
    # We'll let Task 3 refine this — for now, leave tables empty.
    return repo_calls, db_calls, []
```

Modify `scan_flask_routes` so the Endpoint construction calls the new helper:
```python
            for method in methods:
                key = f"{method}_{route}"
                repo_calls, db_calls, tables = _extract_body_calls(node)
                endpoints.append(Endpoint(
                    key=key,
                    route=route,
                    methods=[method],
                    func_name=node.name,
                    line_no=decorator.lineno,
                    docstring=docstring,
                    repo_calls=repo_calls,
                    db_calls=db_calls,
                    tables_read=tables,
                    tables_written=[],
                ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_inventory_endpoints.py -v`
Expected: 9 passed (6 from Task 1 + 3 new)

- [ ] **Step 5: Regenerate the manifest with new fields**

Run: `python3 scripts/inventory_endpoints.py`
Verify: `python3 -c "import json; d=json.load(open('docs/auto-inventory.json')); e=d['endpoints'][0]; print(list(e.keys()))"`
Expected: keys include `repo_calls`, `db_calls`, `tables_read`, `tables_written`

- [ ] **Step 6: Commit**

```bash
git add scripts/inventory_endpoints.py tests/test_inventory_endpoints.py docs/auto-inventory.json
git commit -m "feat(M2): extract repo + db call names per endpoint from AST"
```

---

### Task 3: Repository signature index

**Files:**
- Create: `tests/fixtures/mini_repo.py`
- Modify: `scripts/inventory_endpoints.py`
- Modify: `tests/test_inventory_endpoints.py`

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/mini_repo.py`:
```python
"""Fixture for repository signature scanner tests."""
from typing import Optional, List, Dict


class Repository:
    def get_novel(self, novel_name: str) -> Optional[Dict]:
        """Look up a novel by name."""
        return None

    def list_chapters(self, novel_name: str, volume: Optional[str] = None) -> List[Dict]:
        """List all chapters, optionally filtered by volume."""
        return []

    def upsert_outline(self, novel_name: str, volume: str, content: str, word_count: int = 0) -> Dict:
        """Create or update a volume outline."""
        return {}
```

Append to `tests/test_inventory_endpoints.py`:
```python
REPO_FIXTURE = Path(__file__).parent / "fixtures" / "mini_repo.py"

def test_scan_repository_returns_index_of_methods():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    assert "get_novel" in index
    assert "list_chapters" in index
    assert "upsert_outline" in index
    assert index["get_novel"]["docstring"] == "Look up a novel by name."

def test_scan_repository_extracts_param_names():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    assert "novel_name" in index["get_novel"]["params"]
    assert "volume" in index["upsert_outline"]["params"]
    assert "content" in index["upsert_outline"]["params"]
    assert "word_count" in index["upsert_outline"]["params"]
    assert "word_count" in index["upsert_outline"]["defaults"]   # has default = 0

def test_scan_repository_infers_table_from_method_name():
    from inventory_endpoints import scan_repository_methods
    index = scan_repository_methods(REPO_FIXTURE)
    # list_chapters / get_chapter / upsert_chapter → "chapters" table
    assert index["get_novel"]["tables"] == ["novels"]
    assert index["list_chapters"]["tables"] == ["chapters"]
    assert index["upsert_outline"]["tables"] == ["outlines"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_inventory_endpoints.py -v -k "repository"`
Expected: 3 failures with `ModuleNotFoundError: No module named 'inventory_endpoints'.scan_repository_methods`

- [ ] **Step 3: Implement repository scanner + table heuristic**

Append to `scripts/inventory_endpoints.py` (after `scan_flask_routes`):
```python
def _method_name_to_tables(method_name: str) -> list[str]:
    """Heuristic: get_novel → [novels], list_chapters → [chapters], upsert_outline → [outlines].

    Strips a small set of common prefixes/suffixes and pluralizes.
    Falls back to the raw stem (e.g. 'commit' → ['commit']) so the spec
    still shows the call even when no table is identifiable.
    """
    import re
    name = method_name.lower()
    # Strip common verb prefixes
    for prefix in ("get_", "list_", "upsert_", "delete_", "create_", "update_", "add_", "remove_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    # Strip common suffixes
    for suffix in ("_by_id", "_by_name", "_by_num", "_all"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    if not name:
        return []
    # Pluralize crudely
    table = name if name.endswith("s") else name + "s"
    return [table]


def scan_repository_methods(source: Path) -> dict:
    """Parse a Python file containing a Repository class and return an index:
        {method_name: {"params": [...], "defaults": [...], "docstring": str, "tables": [...]}}
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    index: dict = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in ("Repository", "Repo"):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_"):
                continue  # skip private helpers
            args = item.args
            all_args = args.args + args.kwonlyargs
            param_names = [a.arg for a in all_args]
            defaults_count = sum(1 for a in args.defaults) + sum(1 for a in args.kw_defaults if a is not None)
            defaults = [a.arg for a in args.args[-defaults_count:]] if defaults_count else []
            docstring = _first_docstring_line(item)
            index[item.name] = {
                "params": param_names,
                "defaults": defaults,
                "docstring": docstring,
                "tables": _method_name_to_tables(item.name),
            }
    return index
```

Also update `build_manifest` to include the repo index in the JSON output and back-fill `tables_read` per endpoint:
```python
def build_manifest(source: Path, repo_source: Path = Path("portal/repository.py")) -> dict:
    endpoints = scan_flask_routes(source)
    repo_index = scan_repository_methods(repo_source) if repo_source.exists() else {}
    # Back-fill tables_read from repo_calls
    for ep in endpoints:
        tables: list[str] = []
        for call in ep["repo_calls"]:
            if call in repo_index:
                for t in repo_index[call]["tables"]:
                    if t not in tables:
                        tables.append(t)
        ep["tables_read"] = tables
    return {
        "generated_at": "",
        "source": str(source),
        "repository_index_size": len(repo_index),
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
        "repository_index": repo_index,   # full index for the renderer to use
    }
```

Note: this changes `Endpoint` (a dataclass) → dict, since `build_manifest` was returning a dict anyway and the dataclass was just intermediate. Update the field names to match the dataclass for consistency.

Modify `scan_flask_routes` to return `Endpoint` (with empty `tables_read`) and let `build_manifest` do the dict serialization with the back-fill. The function `_extract_body_calls` already returns the right tuple.

Replace the current `build_manifest` with the version above. Update the call in `main()` if signature changed (it didn't — same kwargs, repo_source has a default).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_inventory_endpoints.py -v`
Expected: 12 passed (9 from previous tasks + 3 new)

- [ ] **Step 5: Regenerate manifest with real repo**

Run: `python3 scripts/inventory_endpoints.py`
Verify: `python3 -c "import json; d=json.load(open('docs/auto-inventory.json')); print('repo methods:', d['repository_index_size']); ep=next(e for e in d['endpoints'] if e['route']=='/api/novels'); print('tables_read:', ep['tables_read'])"`
Expected: `repo methods: 100+` (real count) and `tables_read: ['novels']` (heuristic worked)

- [ ] **Step 6: Commit**

```bash
git add scripts/inventory_endpoints.py tests/fixtures/mini_repo.py tests/test_inventory_endpoints.py docs/auto-inventory.json
git commit -m "feat(M2): repository method index with table-name heuristic"
```

---

### Task 4: Jinja2 spec template

**Files:**
- Create: `docs/system-functional-spec.j2.md`

This task is template authoring (not TDD-able directly — verified in Task 5 by the renderer test).

- [ ] **Step 1: Create the template with Manual Notes anchors**

Create `docs/system-functional-spec.j2.md`:
```jinja2
# Novel Agent — System Functional Spec

> Machine-generated + manual supplements. Source of truth: `portal/app.py` AST.
> Auto-generated: {{ generated_at }}. Inventory: {{ endpoint_count }} endpoints.

---

## 1. Architecture Overview

Flask + React portal. Unified SQLite/MySQL DB. 12-layer system prompt. DeepSeek SSE.
See [README.md](../../README.md) for stack details and [openspec/specs/context-builder.md](../../openspec/specs/context-builder.md) for the layer architecture.

## 2. Data Model (26 tables)

See [`portal/models_orm.py`](../../portal/models_orm.py) for canonical definitions. Brief grouping:

| Group | Tables |
|-------|--------|
| Project | `novels`, `project_meta`, `alias_names`, `style_presets` |
| Story structure | `story_volumes`, `volume_plans`, `chapter_outlines`, `outlines`, `chapters`, `reviews` |
| Domain | `characters`, `foreshadowing`, `world_building`, `plot_arcs`, `pacing_control`, `revelation_schedule`, `genre_rules` |
| Workflow | `story_tracking`, `stage_gates`, `danger_issues` |
| Config (separate DB on MySQL) | `banned_words`, `compliance_rules`, `style_presets` |

## 3. Repository Layer ({{ repo_index_size }} methods)

Grouped by table. See `portal/repository.py` for canonical definitions.

{% for method, info in repo_index.items() %}
- `repo.{{ method }}({{ info.params | join(', ') }})` → reads/writes `{{ info.tables | join(', ') }}` — {{ info.docstring }}
{% endfor %}

## 4. Context Building (12 layers)

See [openspec/specs/context-builder.md](../../openspec/specs/context-builder.md).

## 5. API Endpoints ({{ endpoint_count }})

{% set ns = namespace(current_section="") %}
{% for ep in endpoints %}
{% set section = ep.route.split('/', 3)[1] if '/' in ep.route else '(root)' %}
{% if section != ns.current_section %}
{% set ns.current_section = section %}
### 5.{{ loop.index0 }} {{ section }}
{% endif %}
#### Endpoint: {{ ep.methods[0] }} {{ ep.route }}

- **Function**: `{{ ep.func_name }}` (line {{ ep.line_no }})
- **Description**: {{ ep.docstring or '_No docstring yet — add one in `portal/app.py`._' }}
- **Repository calls**: {% if ep.repo_calls %}`{{ ep.repo_calls | join('`, `') }}`{% else %}none{% endif %}
- **DB calls**: {% if ep.db_calls %}`{{ ep.db_calls | join('`, `') }}`{% else %}none{% endif %}
- **Tables read**: {% if ep.tables_read %}`{{ ep.tables_read | join('`, `') }}`{% else %}_inferred from repo calls (none detected)_{% endif %}
- **Side effects**: {% if ep.db_calls %}writes to DB{% else %}read-only{% endif %}

{% if ep.key in manual_notes %}
<!-- MANUAL: {{ ep.key }} -->
{{ manual_notes[ep.key] }}
<!-- /MANUAL -->
{% else %}
<!-- MANUAL: {{ ep.key }} -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->
{% endif %}

{% endfor %}

---

## Appendix A: Endpoint Index

| Method | Route | Function |
|--------|-------|----------|
{% for ep in endpoints -%}
| `{{ ep.methods[0] }}` | `{{ ep.route }}` | `{{ ep.func_name }}` |
{% endfor %}
```

- [ ] **Step 2: Commit the template (renderer will fill it in next task)**

```bash
git add docs/system-functional-spec.j2.md
git commit -m "feat(M2): jinja2 template for system functional spec"
```

---

### Task 5: Renderer script with Manual Notes preservation

**Files:**
- Create: `scripts/render_spec.py`
- Create: `tests/test_render_spec.py`
- Create: `tests/fixtures/mini_inventory.json`

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/mini_inventory.json`:
```json
{
  "generated_at": "2026-06-03T00:00:00Z",
  "source": "fixture",
  "repository_index_size": 2,
  "endpoint_count": 2,
  "endpoints": [
    {
      "key": "GET_/api/novels",
      "route": "/api/novels",
      "methods": ["GET"],
      "func_name": "api_novels",
      "line_no": 10,
      "docstring": "List or create novels.",
      "repo_calls": ["list_novels"],
      "db_calls": [],
      "tables_read": ["novels"],
      "tables_written": []
    },
    {
      "key": "POST_/api/context/build",
      "route": "/api/context/build",
      "methods": ["POST"],
      "func_name": "api_context_build",
      "line_no": 100,
      "docstring": "Build 12-layer system prompt.",
      "repo_calls": ["list_genre_rules", "list_banned_words"],
      "db_calls": [],
      "tables_read": ["genre_rules", "banned_words"],
      "tables_written": []
    }
  ],
  "repository_index": {
    "list_novels": {"params": [], "defaults": [], "docstring": "List all novels.", "tables": ["novels"]},
    "list_genre_rules": {"params": ["novel_name"], "defaults": [], "docstring": "List genre rules.", "tables": ["genre_rules"]}
  }
}
```

Create `tests/test_render_spec.py`:
```python
"""Tests for scripts/render_spec.py — the Jinja2 renderer."""
import json
from pathlib import Path

import pytest

FIXTURE_INV = Path(__file__).parent / "fixtures" / "mini_inventory.json"
TEMPLATE = Path(__file__).parent.parent / "docs" / "system-functional-spec.j2.md"


def test_render_contains_endpoint_section_heading():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "#### Endpoint: GET /api/novels" in out
    assert "#### Endpoint: POST /api/context/build" in out

def test_render_includes_repo_method_index():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "repo.list_novels" in out
    assert "repo.list_genre_rules" in out

def test_render_emits_empty_manual_notes_placeholder_by_default():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "<!-- MANUAL: GET_/api/novels -->" in out
    assert "<!-- /MANUAL -->" in out

def test_render_substitutes_manual_notes_when_provided():
    from render_spec import render_spec
    notes = {
        "GET_/api/novels": "Returns the list of registered novels. See README 'API endpoints' table."
    }
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes=notes)
    # The provided note replaces the empty placeholder body
    assert "Returns the list of registered novels." in out
    assert "<!-- MANUAL: GET_/api/novels -->" in out  # anchor still present


def test_extract_manual_notes_round_trip(tmp_path):
    """If an existing spec.md has Manual Notes, they should be parseable
    so the caller can re-render without losing them."""
    from render_spec import extract_manual_notes
    existing = tmp_path / "spec.md"
    existing.write_text(
        "# Spec\n"
        "<!-- MANUAL: GET_/api/novels -->\n"
        "Some prose here.\n"
        "<!-- /MANUAL -->\n"
        "\n"
        "<!-- MANUAL: POST_/api/context/build -->\n"
        "Other prose.\n"
        "<!-- /MANUAL -->\n",
        encoding="utf-8",
    )
    notes = extract_manual_notes(existing)
    assert notes["GET_/api/novels"] == "Some prose here."
    assert notes["POST_/api/context/build"] == "Other prose."


def test_render_preserves_existing_manual_notes(tmp_path):
    """End-to-end: render with old spec.md present → manual notes survive."""
    from render_spec import render_spec
    old = tmp_path / "spec.md"
    old.write_text(
        "<!-- MANUAL: GET_/api/novels -->\n"
        "Pre-existing prose that must survive regeneration.\n"
        "<!-- /MANUAL -->\n",
        encoding="utf-8",
    )
    notes = extract_manual_notes(old)
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes=notes)
    assert "Pre-existing prose that must survive regeneration." in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_spec.py -v`
Expected: 6 failures (ModuleNotFoundError on `render_spec`)

- [ ] **Step 3: Implement renderer**

Create `scripts/render_spec.py`:
```python
#!/usr/bin/env python3
"""Render docs/system-functional-spec.md from docs/auto-inventory.json.

Reads the Jinja2 template, the JSON manifest, and (optionally) an existing
spec.md's Manual Notes blocks. Preserves manual notes across regenerations.
"""
import json
import re
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    print("jinja2 is required: pip install jinja2", file=sys.stderr)
    sys.exit(1)


MANUAL_OPEN = re.compile(r"<!-- MANUAL: ([^\s]+) -->")
# Match an entire block: open marker, body (lazy), close marker
MANUAL_BLOCK = re.compile(
    r"<!-- MANUAL: ([^\s]+) -->\n(.*?)<!-- /MANUAL -->",
    re.DOTALL,
)


def extract_manual_notes(spec_path: Path) -> dict[str, str]:
    """Read spec.md and return {key: body} for every non-empty Manual Notes block.

    Blocks whose body is just the auto-generated empty placeholder
    (matches '^\\s*\\(no manual notes yet' or is whitespace-only after
    stripping the placeholder comment) are omitted from the result.
    """
    if not spec_path.exists():
        return {}
    text = spec_path.read_text(encoding="utf-8")
    notes: dict[str, str] = {}
    for match in MANUAL_BLOCK.finditer(text):
        key = match.group(1)
        body = match.group(2).rstrip()
        # Skip empty placeholders
        stripped = body.strip()
        if not stripped or stripped.startswith("(no manual notes yet"):
            continue
        notes[key] = body
    return notes


def render_spec(manifest_path: Path, template_path: Path, manual_notes: dict[str, str]) -> str:
    """Render the spec to a string. Does NOT write to disk."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)
    return template.render(
        generated_at=manifest["generated_at"],
        endpoint_count=manifest["endpoint_count"],
        endpoints=manifest["endpoints"],
        repo_index=manifest.get("repository_index", {}),
        repo_index_size=manifest.get("repository_index_size", 0),
        manual_notes=manual_notes,
    )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--inventory", type=Path, default=Path("docs/auto-inventory.json"))
    parser.add_argument("--template", type=Path, default=Path("docs/system-functional-spec.j2.md"))
    parser.add_argument("--out", type=Path, default=Path("docs/system-functional-spec.md"))
    parser.add_argument("--existing", type=Path, default=Path("docs/system-functional-spec.md"),
                        help="Path to existing spec.md to preserve Manual Notes from (default: --out)")
    args = parser.parse_args()
    if args.existing != args.out and not args.existing.exists():
        # If user pointed --existing somewhere else, fall back to --out
        args.existing = args.out
    notes = extract_manual_notes(args.existing)
    rendered = render_spec(args.inventory, args.template, notes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"Rendered {args.out} ({len(notes)} manual notes preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_render_spec.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/render_spec.py tests/test_render_spec.py tests/fixtures/mini_inventory.json
git commit -m "feat(M2): jinja2 renderer with Manual Notes preservation"
```

---

### Task 6: First end-to-end generation

**Files:**
- (No file creates — runs the pipeline)

- [ ] **Step 1: Generate the inventory**

Run: `python3 scripts/inventory_endpoints.py`
Expected: `Wrote 83 endpoints to docs/auto-inventory.json`

- [ ] **Step 2: Render the spec**

Run: `python3 scripts/render_spec.py`
Expected: `Rendered docs/system-functional-spec.md (0 manual notes preserved)`

- [ ] **Step 3: Verify the rendered output**

Run: `python3 -c "import re; t=open('docs/system-functional-spec.md').read(); print('endpoint sections:', len(re.findall(r'#### Endpoint: ', t))); print('manual placeholders:', len(re.findall(r'<!-- MANUAL: ', t)))"`
Expected: `endpoint sections: 83` and `manual placeholders: 83`

- [ ] **Step 4: Spot-check the content**

Run: `head -50 docs/system-functional-spec.md`
Expected: Title, sections 1-5, endpoint table — should look like a real spec doc, not template leftovers.

- [ ] **Step 5: Commit**

```bash
git add docs/system-functional-spec.md
git commit -m "feat(M2): first full render of system functional spec (83 endpoints, 0 manual notes)"
```

---

### Task 7: Verify script — 5 CI checks

**Files:**
- Create: `scripts/verify_spec.py`
- Create: `tests/test_verify_spec.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify_spec.py`:
```python
"""Tests for scripts/verify_spec.py — 5 CI checks."""
import json
from pathlib import Path

import pytest


def test_check_1_endpoint_count_matches(tmp_path):
    """app.py count == manifest count."""
    from verify_spec import check_endpoint_count_matches
    fake_app = tmp_path / "app.py"
    fake_app.write_text("# stub\n")
    fake_manifest = tmp_path / "inv.json"
    fake_manifest.write_text(json.dumps({
        "endpoint_count": 5,
        "endpoints": [{}] * 5,
    }))
    # Stub scanner: monkeypatch scan_flask_routes via inventory_endpoints
    import inventory_endpoints
    orig = inventory_endpoints.scan_flask_routes
    inventory_endpoints.scan_flask_routes = lambda src: [object()] * 5
    try:
        assert check_endpoint_count_matches(fake_app, fake_manifest) is True
    finally:
        inventory_endpoints.scan_flask_routes = orig


def test_check_1_fails_on_mismatch(tmp_path):
    from verify_spec import check_endpoint_count_matches
    import inventory_endpoints
    orig = inventory_endpoints.scan_flask_routes
    inventory_endpoints.scan_flask_routes = lambda src: [object()] * 6
    try:
        manifest = tmp_path / "inv.json"
        manifest.write_text(json.dumps({"endpoint_count": 5, "endpoints": [{}] * 5}))
        assert check_endpoint_count_matches(tmp_path / "app.py", manifest) is False
    finally:
        inventory_endpoints.scan_flask_routes = orig


def test_check_2_manifest_section_count_match(tmp_path):
    from verify_spec import check_manifest_section_count_match
    manifest = tmp_path / "inv.json"
    manifest.write_text(json.dumps({"endpoint_count": 3, "endpoints": [{}, {}, {}]}))
    spec = tmp_path / "spec.md"
    spec.write_text("a\n#### Endpoint: foo\n#### Endpoint: bar\n#### Endpoint: baz\n")
    assert check_manifest_section_count_match(manifest, spec) is True


def test_check_3_all_endpoints_have_section(tmp_path):
    from verify_spec import check_all_endpoints_have_section
    manifest = tmp_path / "inv.json"
    manifest.write_text(json.dumps({
        "endpoint_count": 2,
        "endpoints": [
            {"key": "GET_/api/a", "route": "/api/a", "methods": ["GET"], "func_name": "a", "line_no": 1, "docstring": "", "repo_calls": [], "db_calls": [], "tables_read": [], "tables_written": []},
            {"key": "POST_/api/b", "route": "/api/b", "methods": ["POST"], "func_name": "b", "line_no": 2, "docstring": "", "repo_calls": [], "db_calls": [], "tables_read": [], "tables_written": []},
        ],
    }))
    spec = tmp_path / "spec.md"
    spec.write_text("#### Endpoint: GET /api/a\n#### Endpoint: POST /api/b\n")
    assert check_all_endpoints_have_section(manifest, spec) is True


def test_check_3_fails_when_endpoint_missing(tmp_path):
    from verify_spec import check_all_endpoints_have_section
    manifest = tmp_path / "inv.json"
    manifest.write_text(json.dumps({
        "endpoint_count": 2,
        "endpoints": [
            {"key": "GET_/api/a", "route": "/api/a", "methods": ["GET"], "func_name": "a", "line_no": 1, "docstring": "", "repo_calls": [], "db_calls": [], "tables_read": [], "tables_written": []},
            {"key": "POST_/api/b", "route": "/api/b", "methods": ["POST"], "func_name": "b", "line_no": 2, "docstring": "", "repo_calls": [], "db_calls": [], "tables_read": [], "tables_written": []},
        ],
    }))
    spec = tmp_path / "spec.md"
    spec.write_text("#### Endpoint: GET /api/a\n")  # POST /api/b missing
    assert check_all_endpoints_have_section(manifest, spec) is False


def test_check_4_manifest_json_valid():
    from verify_spec import check_manifest_json_valid
    from pathlib import Path
    assert check_manifest_json_valid(Path("docs/auto-inventory.json")) is True


def test_check_5_core_endpoints_have_manual_notes(tmp_path):
    from verify_spec import check_core_endpoints_have_manual_notes
    CORE_KEYS = [
        "POST_/api/context/build", "POST_/api/ai/stream", "POST_/api/ai/chat",
        "POST_/api/novels/<novel_name>/generate-chapter",
        "POST_/api/novels/<novel_name>/review-chapter",
    ]
    spec = tmp_path / "spec.md"
    body = "".join(
        f"<!-- MANUAL: {k} -->\nReal content for {k}\n<!-- /MANUAL -->\n" for k in CORE_KEYS
    )
    spec.write_text(body)
    assert check_core_endpoints_have_manual_notes(spec, CORE_KEYS) is True


def test_check_5_fails_when_core_endpoint_missing_notes(tmp_path):
    from verify_spec import check_core_endpoints_have_manual_notes
    CORE_KEYS = ["POST_/api/context/build", "POST_/api/ai/stream"]
    spec = tmp_path / "spec.md"
    spec.write_text("<!-- MANUAL: POST_/api/context/build -->\nContent\n<!-- /MANUAL -->\n")  # only 1
    assert check_core_endpoints_have_manual_notes(spec, CORE_KEYS) is False


def test_main_exits_0_on_success(tmp_path, monkeypatch):
    """End-to-end: all 5 checks pass on the real repo."""
    from verify_spec import main
    import sys
    monkeypatch.setattr(sys, "argv", ["verify_spec.py"])
    rc = main()
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_verify_spec.py -v`
Expected: 8 failures (ModuleNotFoundError on `verify_spec`)

- [ ] **Step 3: Implement verify script**

Create `scripts/verify_spec.py`:
```python
#!/usr/bin/env python3
"""CI gate: verify docs/system-functional-spec.md matches the real portal/app.py.

5 checks, all must pass:
  1. app.py endpoint count == manifest endpoint count
  2. manifest endpoint count == spec.md section count
  3. every endpoint in the manifest has a `# Endpoint: <route>` section in spec.md
  4. auto-inventory.json is valid JSON with required fields
  5. ~25 core endpoints have non-empty Manual Notes

Exits 0 on success, 1 on any failure. Prints a one-line summary per check.
"""
import json
import re
import sys
from pathlib import Path

import inventory_endpoints  # for scan_flask_routes
import render_spec  # for extract_manual_notes


# Core endpoints that must have Manual Notes (per design doc §M2)
CORE_ENDPOINTS = [
    # Writing & generation
    "POST_/api/ai/stream",
    "POST_/api/ai/chat",
    "POST_/api/context/build",
    "GET_/api/context/stats/<novel_name>/<int:volume>/<int:chapter>",
    "POST_/api/novels/<novel_name>/generate-chapter",
    "POST_/api/novels/<novel_name>/review-chapter",
    "POST_/api/novels/<novel_name>/optimize-chapter",
    "POST_/api/novels/create",
    # Chapter lifecycle
    "GET_/api/novels/<novel_name>/chapters/<path:ch_ref>",
    "POST_/api/novels/<novel_name>/chapters/<path:ch_ref>",
    "POST_/api/novels/<novel_name>/chapters/<path:ch_ref>/edit",
    "DELETE_/api/novels/<novel_name>/chapters/<path:ch_ref>",
    "GET_/api/novels/<novel_name>/reviews/<ch_ref>",
    # Workflow
    "POST_/api/novels/<novel_name>/update-status",
    "POST_/api/novels/<novel_name>/enforce-pipeline",
    "POST_/api/novels/<novel_name>/run-script",
    "POST_/api/workflow/preflight/<novel_name>",
    "POST_/api/workflow/postflight/<novel_name>",
    "POST_/api/init/full/<novel_name>",
    "POST_/api/rag/query",
    # Library structure init
    "POST_/api/novels/<novel_name>/world-building/init",
    "POST_/api/novels/<novel_name>/plot-arcs/init",
    "POST_/api/novels/<novel_name>/pacing/init",
    "POST_/api/novels/<novel_name>/revelation/init",
]


def check_endpoint_count_matches(app_path: Path, manifest_path: Path) -> bool:
    app_endpoints = inventory_endpoints.scan_flask_routes(app_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ok = len(app_endpoints) == manifest["endpoint_count"]
    print(f"  [{'OK' if ok else 'FAIL'}] Check 1: app.py={len(app_endpoints)} vs manifest={manifest['endpoint_count']}")
    return ok


def check_manifest_section_count_match(manifest_path: Path, spec_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec_text = spec_path.read_text(encoding="utf-8")
    section_count = len(re.findall(r"^#### Endpoint: ", spec_text, re.MULTILINE))
    ok = section_count == manifest["endpoint_count"]
    print(f"  [{'OK' if ok else 'FAIL'}] Check 2: manifest={manifest['endpoint_count']} vs spec.md sections={section_count}")
    return ok


def check_all_endpoints_have_section(manifest_path: Path, spec_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec_text = spec_path.read_text(encoding="utf-8")
    missing = []
    for ep in manifest["endpoints"]:
        anchor = f"#### Endpoint: {ep['methods'][0]} {ep['route']}"
        if anchor not in spec_text:
            missing.append(ep["key"])
    ok = not missing
    print(f"  [{'OK' if ok else 'FAIL'}] Check 3: all endpoints have sections (missing: {missing})")
    return ok


def check_manifest_json_valid(manifest_path: Path) -> bool:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  [FAIL] Check 4: manifest is not valid JSON: {e}")
        return False
    required = {"generated_at", "source", "endpoint_count", "endpoints", "repository_index"}
    missing = required - set(data.keys())
    if missing:
        print(f"  [FAIL] Check 4: manifest missing required fields: {missing}")
        return False
    if not isinstance(data["endpoints"], list) or len(data["endpoints"]) != data["endpoint_count"]:
        print(f"  [FAIL] Check 4: endpoint_count={data['endpoint_count']} but endpoints list has {len(data['endpoints'])}")
        return False
    print(f"  [OK] Check 4: manifest is valid JSON with {data['endpoint_count']} endpoints")
    return True


def check_core_endpoints_have_manual_notes(spec_path: Path, core_keys: list[str]) -> bool:
    notes = render_spec.extract_manual_notes(spec_path)
    missing = [k for k in core_keys if k not in notes or not notes[k].strip()]
    ok = not missing
    print(f"  [{'OK' if ok else 'FAIL'}] Check 5: {len(core_keys) - len(missing)}/{len(core_keys)} core endpoints have Manual Notes (missing: {missing})")
    return ok


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--app", type=Path, default=Path("portal/app.py"))
    parser.add_argument("--manifest", type=Path, default=Path("docs/auto-inventory.json"))
    parser.add_argument("--spec", type=Path, default=Path("docs/system-functional-spec.md"))
    parser.add_argument("--core-list", action="store_true",
                        help="Print the CORE_ENDPOINTS list and exit (for documentation)")
    args = parser.parse_args()
    if args.core_list:
        for k in CORE_ENDPOINTS:
            print(k)
        return 0

    print(f"Verifying spec against {args.app} ...")
    results = [
        check_endpoint_count_matches(args.app, args.manifest),
        check_manifest_section_count_match(args.manifest, args.spec),
        check_all_endpoints_have_section(args.manifest, args.spec),
        check_manifest_json_valid(args.manifest),
        check_core_endpoints_have_manual_notes(args.spec, CORE_ENDPOINTS),
    ]
    if all(results):
        print("All 5 checks passed.")
        return 0
    print(f"FAILED: {sum(1 for r in results if not r)} of 5 checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_verify_spec.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the verifier on the real repo — expect Check 5 to fail**

Run: `python3 scripts/verify_spec.py`
Expected: Checks 1-4 OK, Check 5 FAIL (no Manual Notes yet — that's Task 8). Exit 1.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_spec.py tests/test_verify_spec.py
git commit -m "feat(M2): CI verify script — 5 checks, fails on any drift"
```

---

### Task 8: Write Manual Notes for 25 core endpoints

**Files:**
- Modify: `docs/system-functional-spec.md`

This is the only "writing" task in M2. It's prose, not code — not TDD-able. The verifier (Task 7) is the acceptance gate.

- [ ] **Step 1: Read the core-endpoint list**

Run: `python3 scripts/verify_spec.py --core-list`
Expected: 25 endpoint keys printed.

- [ ] **Step 2: For each of the 25 core endpoints, fill in the Manual Notes block**

For each `<!-- MANUAL: KEY -->` block, replace the placeholder line `<!-- (no manual notes yet ... -->` with 1-3 sentences covering:
- **What the endpoint does** (in plain English — what the user/dev sees)
- **When to use it** (UI button? API client? internal workflow?)
- **Gotchas** (rate limits, side effects, required headers, etc.)

Example for `POST_/api/context/build`:
```markdown
<!-- MANUAL: POST_/api/context/build -->
Builds the 12-layer system prompt for chapter writing. Returns the assembled prompt
plus per-layer token usage so the UI can show a "context health" indicator. Read-only —
no side effects. Called by both the React UI and the `generate-chapter` workflow
(in which case the prompt is consumed internally rather than returned). Token budget
default 10000, configurable via `max_tokens` request field.
<!-- /MANUAL -->
```

Pattern for all 25: read the corresponding `app.py` function (line number is in the manifest), check its docstring + a few lines of body for context, then write 1-3 sentences.

Required Manual Notes (25 keys — see verify_spec.py CORE_ENDPOINTS for the full list).

- [ ] **Step 3: Run the verifier — expect all 5 checks to pass**

Run: `python3 scripts/verify_spec.py`
Expected: `All 5 checks passed.` Exit 0.

- [ ] **Step 4: Commit**

```bash
git add docs/system-functional-spec.md
git commit -m "docs(M2): 25 core endpoints with Manual Notes (verify_spec passes 5/5)"
```

---

### Task 9: M1 follow-up cleanup + final verify

**Files:**
- Modify: `openspec/specs/context-builder.md`
- Modify: `portal/context_builder.py` (decide fate of `_build_fallback_state_context`)
- Create: `tests/test_context_builder.py` (additional test if wiring in)

This task folds in 2 M1 follow-ups flagged during M1 review:
1. `_build_fallback_state_context` is defined but never called (orphan).
2. `openspec/specs/context-builder.md` says "Pre-existing test failure: `test_context_stats_structure` ... Unchanged by this optimization" — but M1 fixed it.

- [ ] **Step 1: Decide fate of `_build_fallback_state_context`**

Read `portal/context_builder.py` lines 746-762 to confirm current state.
Check the function is still orphan: `grep -nE "_build_fallback_state_context" portal/`.
Decision criteria:
- If the function's contract (returns "" for nonexistent novel, "novel/volume/chapter" oneline for existing) adds value to `build_context`'s output → wire it in (with a TDD test that proves `build_context` for nonexistent novel now includes the fallback string).
- If it's truly dead code → delete it.

**Default decision: DELETE.** Reasoning: `get_context_stats` (which already has a 12-layer-always contract post-M1) is the right level to add fallback behavior. `build_context` for a nonexistent novel is a programmer error (caller should check existence first), and silently adding a fallback string would mask bugs. The function's contract overlaps with `get_context_stats` and is not invoked anywhere. Removing it reduces surface area.

If you (the implementer) disagree and want to wire it in instead, replace Steps 2-3 with:
- TDD test: `test_build_context_includes_fallback_for_nonexistent_novel`
- Implement: call `_build_fallback_state_context` from `build_context` early-return path
- Run the test

- [ ] **Step 2: Delete the orphan function (default path)**

Edit `portal/context_builder.py`: remove the `_build_fallback_state_context` function definition (and any imports it made if they become unused — `get_repo` is still used elsewhere).

Verify no call sites:
Run: `grep -rn "_build_fallback_state_context" portal/ tests/`
Expected: no matches.

- [ ] **Step 3: Update OpenSpec context-builder.md**

Edit `openspec/specs/context-builder.md`:
- In the "Known Issues" section, REMOVE the line starting with "Pre-existing test failure: `test_context_stats_structure`" (and its continuation "Unchanged by this optimization.").
- Optionally add a new "Change History" row:
  ```
  | 2026-06-03 | (M1 follow-up) | Removed orphan `_build_fallback_state_context`; removed stale "pre-existing test failure" note. |
  ```

- [ ] **Step 4: Run full test suite + spec verifier**

Run: `python3 -m pytest tests/ -q`
Expected: 0 failed, 0 errors (baseline maintained from M1).

Run: `python3 scripts/verify_spec.py`
Expected: `All 5 checks passed.`

Run: `python3 scripts/inventory_endpoints.py && python3 scripts/render_spec.py`
Expected: Both succeed, manual notes preserved (no regression).

- [ ] **Step 5: Commit**

```bash
git add openspec/specs/context-builder.md portal/context_builder.py
git commit -m "chore(M2 follow-up): delete orphan _build_fallback_state_context + update context-builder spec"
```

---

### Task 10: README "API 端点" cross-link + final smoke

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a one-line link from README to the new spec doc**

In `README.md`, after the line that says `## API 端点 (主要)`, append:
```markdown

> 完整 83 端点字段级参考（含 Manual Notes、Repo 方法、读写表）见
> [docs/system-functional-spec.md](docs/system-functional-spec.md)。
> 数据驱动：跑 `python3 scripts/inventory_endpoints.py && python3 scripts/render_spec.py` 重新生成。
```

- [ ] **Step 2: Run final smoke**

Run: `python3 scripts/verify_spec.py && python3 -m pytest tests/ -q`
Expected: spec OK, 0 failed, 0 errors.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(M2): README cross-link to system functional spec"
```

---

## Self-Review

**1. Spec coverage** (from `docs/superpowers/specs/2026-06-03-tdd-system-func-spec-design.md` §M2):

| Spec requirement | Task |
|------------------|------|
| AST scanner emitting `auto-inventory.json` with 80+ endpoints | Tasks 1-4 |
| Per-endpoint: route / methods / func / docstring / repo / db / tables | Tasks 2-3 |
| Renderer with Manual Notes preservation | Task 5 |
| Verify script with 5 checks | Task 7 |
| ~25 core endpoints with Manual Notes | Task 8 |
| `<!-- MANUAL: key -->` anchor mechanism | Task 5 |
| M1 follow-up: orphan helper resolved | Task 9 |
| M1 follow-up: stale OpenSpec note updated | Task 9 |
| README cross-link | Task 10 |
| `app.py` count == manifest count == spec section count | Task 7 (Checks 1, 2) |
| Endpoint add/remove triggers CI red | Task 7 (Check 3) |

✅ No gaps.

**2. Placeholder scan:** Searched for `TBD`, `TODO`, "implement later", "fill in details", "Add appropriate", "Similar to Task" — none found. Task 8 explicitly says "for each of 25 core endpoints, write 1-3 sentences" with a concrete example.

**3. Type consistency:**
- `Endpoint` dataclass fields: `key, route, methods, func_name, line_no, docstring, repo_calls, db_calls, tables_read, tables_written` — consistent across Tasks 1, 2, 3.
- `extract_manual_notes` returns `dict[str, str]` — matches `render_spec(..., manual_notes=...)` parameter type.
- `scan_flask_routes`, `scan_repository_methods` — same return type signatures across Tasks 1, 3.
- `check_*` functions all return `bool` — consistent.
- `CORE_ENDPOINTS` keys use the format `METHOD_<route>` matching `Endpoint.key` — verified in Task 8 step 1.

No type drift.

**4. Failure-mode coverage:**
- Manual Notes preservation: Tasks 5, 7 (Check 5).
- Endpoint count mismatch: Task 7 (Check 1).
- Missing section: Task 7 (Check 3).
- Orphan helper cleanup: Task 9.
- Stale spec note: Task 9.
- Re-render regression: Task 9 Step 4.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-03-m2-system-functional-spec.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for M2 because each task is self-contained (1-3 files), TDD-friendly, and has clean verification gates.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster start, but each task pollutes this session's context.

**Which approach?**
