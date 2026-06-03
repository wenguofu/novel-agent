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
from typing import List, Optional


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


def scan_flask_routes(source: Path) -> List[Endpoint]:
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
            repo_calls, db_calls, tables = _extract_body_calls(node)
            endpoints.append(Endpoint(
                key=key_parts,
                route=route,
                methods=methods,
                func_name=node.name,
                line_no=decorator.lineno,
                docstring=docstring,
                repo_calls=repo_calls,
                db_calls=db_calls,
                tables_read=tables,
                tables_written=[],
            ))
    return endpoints


def build_manifest(source: Path) -> dict:
    endpoints = scan_flask_routes(source)
    return {
        "generated_at": "",
        "source": str(source),
        "endpoint_count": len(endpoints),
        "endpoints": [ep.__dict__ for ep in endpoints],
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
