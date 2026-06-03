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
    # Stub scanner: monkeypatch inventory_endpoints.scan_flask_routes
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


def test_check_2_fails_on_mismatch(tmp_path):
    from verify_spec import check_manifest_section_count_match
    manifest = tmp_path / "inv.json"
    manifest.write_text(json.dumps({"endpoint_count": 3, "endpoints": [{}, {}, {}]}))
    spec = tmp_path / "spec.md"
    spec.write_text("#### Endpoint: foo\n#### Endpoint: bar\n")  # only 2 sections
    assert check_manifest_section_count_match(manifest, spec) is False


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
    """The real auto-inventory.json should be valid JSON with required fields."""
    from verify_spec import check_manifest_json_valid
    from pathlib import Path
    assert check_manifest_json_valid(Path("docs/auto-inventory.json")) is True


def test_check_5_core_endpoints_have_manual_notes(tmp_path):
    from verify_spec import check_core_endpoints_have_manual_notes, CORE_ENDPOINTS
    # CORE_ENDPOINTS is a module-level constant; pick a small subset for the test
    test_keys = CORE_ENDPOINTS[:3]
    spec = tmp_path / "spec.md"
    body = "".join(
        f"<!-- MANUAL: {k} -->\nReal content for {k}\n<!-- /MANUAL -->\n" for k in test_keys
    )
    spec.write_text(body)
    assert check_core_endpoints_have_manual_notes(spec, test_keys) is True


def test_check_5_fails_when_core_endpoint_missing_notes(tmp_path):
    from verify_spec import check_core_endpoints_have_manual_notes
    test_keys = ["POST_/api/context/build", "POST_/api/ai/stream"]
    spec = tmp_path / "spec.md"
    spec.write_text(
        "<!-- MANUAL: POST_/api/context/build -->\nContent\n<!-- /MANUAL -->\n"
    )  # only 1 of 2 has notes
    assert check_core_endpoints_have_manual_notes(spec, test_keys) is False


def test_check_5_fails_on_empty_placeholder(tmp_path):
    """A block whose body is the auto-generated empty placeholder must
    NOT count as having Manual Notes."""
    from verify_spec import check_core_endpoints_have_manual_notes
    test_keys = ["POST_/api/context/build"]
    spec = tmp_path / "spec.md"
    spec.write_text(
        "<!-- MANUAL: POST_/api/context/build -->\n"
        "<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->\n"
        "<!-- /MANUAL -->\n"
    )
    assert check_core_endpoints_have_manual_notes(spec, test_keys) is False


def test_main_runs_5_checks(capsys):
    """The CLI prints one line per check and a summary line. Run it against
    the real repo — Checks 1-4 should print OK, Check 5 should print FAIL
    (no Manual Notes written yet — that's Task 8). Exit code should be 1."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "scripts/verify_spec.py"],
        capture_output=True, text=True, cwd="/Users/wgfu/Desktop/novel-agent",
    )
    assert result.returncode == 1, f"expected exit 1, got {result.returncode}; stdout={result.stdout}"
    output = result.stdout + result.stderr
    # All 5 checks should appear
    for n in range(1, 6):
        assert f"Check {n}" in output, f"Check {n} not in output:\n{output}"
    # Check 5 must FAIL (no Manual Notes yet)
    assert "[FAIL] Check 5" in output, f"expected Check 5 FAIL, output:\n{output}"
    # At least one of Checks 1-4 should be OK
    assert "[OK] Check 1" in output, f"expected Check 1 OK, output:\n{output}"
