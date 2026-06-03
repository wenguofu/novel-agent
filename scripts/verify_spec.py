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
from typing import List

import inventory_endpoints  # for scan_flask_routes
import render_spec  # for extract_manual_notes


# Core endpoints that must have Manual Notes (per design doc §M2).
# These are the 25 endpoints across 5 categories: writing/generation,
# chapter lifecycle, workflow, library init, plus a few high-value additions.
CORE_ENDPOINTS: List[str] = [
    # Writing & generation (8)
    "POST_/api/ai/stream",
    "POST_/api/ai/chat",
    "POST_/api/context/build",
    "GET_/api/context/stats/<novel_name>/<int:volume>/<int:chapter>",
    "POST_/api/novels/<novel_name>/generate-chapter",
    "POST_/api/novels/<novel_name>/review-chapter",
    "POST_/api/novels/<novel_name>/optimize-chapter",
    "POST_/api/novels/create",
    # Chapter lifecycle (5)
    "GET_/api/novels/<novel_name>/chapters/<path:ch_ref>",
    "POST_/api/novels/<novel_name>/chapters/<path:ch_ref>/edit",
    "DELETE_/api/novels/<novel_name>/chapters/<path:ch_ref>",
    "GET_/api/novels/<novel_name>/reviews/<ch_ref>",
    "POST_/api/novels/<novel_name>/update-status",
    # Workflow (6)
    "POST_/api/novels/<novel_name>/enforce-pipeline",
    "POST_/api/novels/<novel_name>/run-script",
    "POST_/api/workflow/preflight/<novel_name>",
    "POST_/api/workflow/postflight/<novel_name>",
    "POST_/api/init/full/<novel_name>",
    "POST_/api/rag/query",
    # Library structure init (4)
    "POST_/api/novels/<novel_name>/world-building/init",
    "POST_/api/novels/<novel_name>/plot-arcs/init",
    "POST_/api/novels/<novel_name>/pacing/init",
    "POST_/api/novels/<novel_name>/revelation/init",
    # Outline & file writing (2)
    "POST_/api/novels/<novel_name>/outline/<vol_ref>/edit",
    "POST_/api/novels/<novel_name>/file/write",
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


def check_core_endpoints_have_manual_notes(spec_path: Path, core_keys: List[str]) -> bool:
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
