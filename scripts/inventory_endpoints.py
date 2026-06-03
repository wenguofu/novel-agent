#!/usr/bin/env python3
"""AST scanner for Flask routes in portal/app.py.

Emits docs/auto-inventory.json with one entry per (route, methods) tuple.
Uses only stdlib — jinja2 is only required by the renderer (render_spec.py).
"""
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict


@dataclass
class Endpoint:
    key: str           # e.g. "GET,POST_/api/novels"
    route: str
    methods: List[str]
    func_name: str
    line_no: int
    docstring: str
    repo_calls: List[str]      # e.g. ["list_novels", "get_chapter"]
    db_calls: List[str]        # e.g. ["add", "commit", "execute"]
    tables_read: List[str]     # filled in Task 3 via repo signature index
    tables_written: List[str]  # same


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


def _route_from_decorator(decorator: ast.expr) -> Optional[str]:
    """Return the route string from an @app.route("...") decorator, or None."""
    if not isinstance(decorator, ast.Call):
        return None
    if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "route":
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            return decorator.args[0].value
    return None


def _extract_body_calls(func_node) -> tuple:
    """Walk a function body and collect:
      - repo.<method>() calls (owner is a Name node with id in {"repo", "r"})
      - db/session.<method>() calls (owner is a Name node with id in {"db", "session"})
    Returns (repo_calls, db_calls, []) — tables list is left empty; Task 3 fills it
    via the repository method-name heuristic.

    Known limitation (documented): the walker only inspects calls directly in the
    endpoint body. Calls 1+ level of indirection deep (e.g. a wrapper class
    method `self._repo.list_novels()` invoked from a regular function endpoint
    via `handler.foo()`) are NOT detected. The real `portal/app.py` uses such
    wrapper classes for `/api/wizard/step` and a few others; those endpoints will
    show `repo_calls=[]` even though they read/write data. This is acceptable
    for M2 — Manual Notes (Task 8) cover the high-value endpoints.
    """
    repo_calls: List[str] = []
    db_calls: List[str] = []
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
    return repo_calls, db_calls, []


def _extract_bare_function_calls(func_node, known_names: set) -> List[str]:
    """Walk a function body and collect calls to bare function names that match
    `known_names` (e.g. a set of method names from the repository index).

    Pattern: `list_novels()` → ast.Call(func=ast.Name('list_novels')).
    Ignores method calls (Attribute), constructor calls (ClassName()), and
    unknown names.
    """
    matches: List[str] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in known_names:
            if node.func.id not in matches:
                matches.append(node.func.id)
    return matches


def _method_name_to_tables(method_name: str) -> List[str]:
    """Heuristic: get_novel → [novels], list_chapters → [chapters], upsert_outline → [outlines].

    Strips a small set of common prefixes/suffixes and pluralizes crudely.
    Falls back to the raw stem so the spec still shows the call even when no
    table is identifiable (e.g. 'commit' → ['commits']).
    """
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


def scan_repository_methods(source: Path) -> Dict[str, dict]:
    """Parse a Python file containing a Repository class and return an index:
        {method_name: {"params": [...], "defaults": [...], "docstring": str, "tables": [...]}}

    Skips methods starting with '_' (private helpers) and methods on classes
    not named 'Repository' or 'Repo'.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    index: Dict[str, dict] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in ("Repository", "Repo"):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_"):
                continue
            args = item.args
            all_args = args.args + args.kwonlyargs
            param_names = [a.arg for a in all_args]
            # Count defaults: positional defaults + kwonly defaults (None = no default)
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


def scan_flask_routes(source: Path, repo_index: Dict[str, dict] = None) -> List[Endpoint]:
    """Parse `source` (a .py file) and return one Endpoint per Flask route.

    Walks every FunctionDef in the module, inspects its @app.route / @app.<method>
    decorators, and emits one Endpoint per route decorator (with all its methods).
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
            key_parts = ",".join(methods) + "_" + route
            repo_calls_attr, db_calls, tables = _extract_body_calls(node)
            # Add bare function calls if a repo index is provided
            if repo_index:
                known = set(repo_index.keys())
                bare = _extract_bare_function_calls(node, known)
                for name in bare:
                    if name not in repo_calls_attr:
                        repo_calls_attr.append(name)
            endpoints.append(Endpoint(
                key=key_parts,
                route=route,
                methods=methods,
                func_name=node.name,
                line_no=decorator.lineno,
                docstring=docstring,
                repo_calls=repo_calls_attr,
                db_calls=db_calls,
                tables_read=tables,
                tables_written=[],
            ))
    return endpoints


def build_manifest(
    source: Path,
    repo_source: Path = None,
) -> dict:
    """Build the full inventory manifest.

    If `repo_source` (default: portal/repository.py) exists, build the method
    index and use it to (a) detect bare function calls in endpoint bodies and
    (b) compute `tables_read` per endpoint from the method-name heuristic.
    """
    if repo_source is None:
        repo_source = Path("portal/repository.py")
    repo_index = scan_repository_methods(repo_source) if repo_source.exists() else {}
    endpoints = scan_flask_routes(source, repo_index=repo_index if repo_index else None)
    # Serialize + back-fill tables_read
    serialized = []
    for ep in endpoints:
        d = ep.__dict__
        tables: List[str] = []
        for call in d["repo_calls"]:
            if call in repo_index:
                for t in repo_index[call]["tables"]:
                    if t not in tables:
                        tables.append(t)
        d["tables_read"] = tables
        serialized.append(d)
    return {
        "generated_at": "",
        "source": str(source),
        "repository_index_size": len(repo_index),
        "endpoint_count": len(serialized),
        "endpoints": serialized,
        "repository_index": repo_index,
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
