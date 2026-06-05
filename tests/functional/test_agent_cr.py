"""Integration test for the 6-dim Agent Code Review (M3.1 W4).

Verifies that post_commit_review.sh writes a report with the expected
structure when invoked on a real commit. Covers both modes:
  - AGENT_CR_MODE=full (default): produces 6-dim static analysis report
  - AGENT_CR_MODE=stub: produces placeholder report
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "agent-system" / "scripts" / "post_commit_review.sh"
REPORT_DIR = REPO_ROOT / ".code-reviews"


def _pick_recent_commit():
    """Pick a recent non-merge, non-hotfix commit on main."""
    out = subprocess.run(
        ["git", "log", "--no-merges", "--pretty=%H|%s", "-20"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    ).stdout
    for line in out.strip().split("\n"):
        if "|" not in line:
            continue
        sha, subject = line.split("|", 1)
        if "hotfix" in subject.lower():
            continue
        if subject.startswith("Merge"):
            continue
        return sha
    raise RuntimeError("no suitable commit found")


def _backup_report(short_sha, tmp_path):
    """Move existing report to tmp_path (if any), return path to backup or None."""
    existing = REPORT_DIR / f"{short_sha}.md"
    if existing.exists():
        bak = tmp_path / f"{short_sha}.md.bak"
        shutil.copy(existing, bak)
        existing.unlink()
        return bak
    return None


def _restore_report(short_sha, bak):
    """Restore report from backup if it existed."""
    if bak and bak.exists():
        existing = REPORT_DIR / f"{short_sha}.md"
        shutil.copy(bak, existing)


def test_full_mode_writes_six_dim_sections(tmp_path):
    """Full mode produces a report with 6 dim sections + summary."""
    sha = _pick_recent_commit()
    short_sha = sha[:7]
    bak = _backup_report(short_sha, tmp_path)
    try:
        env = os.environ.copy()
        env["AGENT_CR_MODE"] = "full"
        result = subprocess.run(
            ["bash", str(SCRIPT), sha],
            capture_output=True, text=True,
            cwd=REPO_ROOT, env=env,
        )
        assert result.returncode == 0, (
            f"script failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        report = REPORT_DIR / f"{short_sha}.md"
        assert report.exists(), f"report not written: {report}"
        body = report.read_text(encoding="utf-8")
        # 6 dim sections
        for dim in ("Correctness", "Security", "Performance", "Tests", "Style", "Docs"):
            assert f"### {dim}" in body, f"missing dim section: {dim}"
        # Summary header
        assert "## Summary" in body, "missing Summary header"
        # ISSUES FOUND section
        assert "## ISSUES FOUND" in body, "missing ISSUES FOUND section"
        # VERDICT
        assert "## VERDICT" in body, "missing VERDICT"
        # Reviewer line
        assert "full mode" in body, "missing 'full mode' reviewer label"
        # Each dim has either findings list or "No issues found"
        for dim in ("Correctness", "Security", "Performance", "Tests", "Style", "Docs"):
            dim_header = f"### {dim} "
            header_line_idx = None
            lines = body.split("\n")
            for i, ln in enumerate(lines):
                if ln.startswith(dim_header):
                    header_line_idx = i
                    break
            assert header_line_idx is not None, f"dim header not on its own line: {dim}"
            # Find next "### " or "## " header (must be at line start)
            next_header_idx = None
            for j in range(header_line_idx + 1, len(lines)):
                ln = lines[j]
                if ln.startswith("### ") or ln.startswith("## "):
                    next_header_idx = j
                    break
            if next_header_idx is None:
                next_header_idx = len(lines)
            section_lines = lines[header_line_idx:next_header_idx]
            section_body = "\n".join(section_lines)
            assert ("- `" in section_body) or ("No issues" in section_body), (
                f"dim {dim} has no findings and no 'No issues' marker; "
                f"section_body={section_body!r}"
            )
    finally:
        _restore_report(short_sha, bak)


def test_stub_mode_writes_placeholder(tmp_path):
    """Stub mode (AGENT_CR_MODE=stub) writes a placeholder report."""
    sha = _pick_recent_commit()
    short_sha = sha[:7]
    bak = _backup_report(short_sha, tmp_path)
    try:
        env = os.environ.copy()
        env["AGENT_CR_MODE"] = "stub"
        result = subprocess.run(
            ["bash", str(SCRIPT), sha],
            capture_output=True, text=True,
            cwd=REPO_ROOT, env=env,
        )
        assert result.returncode == 0, (
            f"script failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        report = REPORT_DIR / f"{short_sha}.md"
        assert report.exists()
        body = report.read_text(encoding="utf-8")
        assert "stub mode" in body.lower(), "missing 'stub mode' label"
        # All 6 dim sections present
        for dim in ("Correctness", "Security", "Performance", "Tests", "Style", "Docs"):
            assert dim in body, f"missing dim: {dim}"
    finally:
        _restore_report(short_sha, bak)


def test_python_orchestrator_importable():
    """The Python helper module imports cleanly and exposes expected API."""
    import importlib.util
    lib_path = REPO_ROOT / "agent-system" / "scripts" / "agent_review_lib.py"
    spec = importlib.util.spec_from_file_location("agent_review_lib", str(lib_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Orchestrator pieces
    assert callable(getattr(mod, "run_review", None))
    assert callable(getattr(mod, "render_report", None))
    # 6 dim check functions
    for dim in ("correctness", "security", "performance", "tests", "style", "docs"):
        fn = getattr(mod, "check_" + dim, None)
        assert callable(fn), f"missing check_{dim}"
    # DIMENSIONS registry has 6 entries
    assert len(mod.DIMENSIONS) == 6
