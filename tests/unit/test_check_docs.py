"""Unit tests for agent-system/scripts/agent_review_lib.py::check_docs.

The Docs-dimension detector was raising false-positive "missing docstring"
findings for functions with multi-line signatures, because the original
implementation only inspected the line immediately after the opening `(`,
not after the matching `):`. These tests pin the correct behavior.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LIB_PATH = REPO_ROOT / "agent-system" / "scripts" / "agent_review_lib.py"


@pytest.fixture
def review_lib():
    """Import agent_review_lib from its non-standard path."""
    spec = importlib.util.spec_from_file_location("agent_review_lib", LIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent_review_lib"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Multi-line signature (the bug) ──────────────────────────────────


def test_multiline_signature_with_docstring_is_not_flagged(review_lib, tmp_path):
    """A function with a multi-line parameter list and a real docstring
    must NOT be reported as missing a docstring.

    Regression test for the M3.2 unblock: the detector was inspecting
    the line right after `(` and saw a parameter-continuation line, not
    the docstring, producing a false-positive.
    """
    f = tmp_path / "module.py"
    f.write_text(
        'def public_function_with_multiline_sig(\n'
        '    a, b, c, d,\n'
        '    e, f,\n'
        '):\n'
        '    """Real docstring on the line after the closing `):`."""\n'
        '    return a + b\n'
    )
    findings = review_lib.check_docs(diff="", files=[str(f)])
    assert findings == [], (
        "Multi-line signature with docstring was falsely flagged: "
        f"{findings}"
    )


def test_multiline_signature_without_docstring_is_flagged(review_lib, tmp_path):
    """A function with a multi-line signature and NO docstring should
    still be reported (regression guard for the other direction).
    """
    f = tmp_path / "module.py"
    f.write_text(
        'def public_function_with_multiline_sig(\n'
        '    a, b, c,\n'
        '):\n'
        '    return a + b\n'
    )
    findings = review_lib.check_docs(diff="", files=[str(f)])
    assert len(findings) == 1
    assert "public_function_with_multiline_sig" in findings[0]
    assert "missing docstring" in findings[0]


# ── Single-line signature (regression guard) ─────────────────────────


def test_single_line_signature_with_docstring_is_not_flagged(review_lib, tmp_path):
    """Plain single-line signatures must still be detected correctly."""
    f = tmp_path / "module.py"
    f.write_text(
        'def short(a, b):\n'
        '    """Has a docstring."""\n'
        '    return a + b\n'
    )
    findings = review_lib.check_docs(diff="", files=[str(f)])
    assert findings == []


def test_single_line_signature_without_docstring_is_flagged(review_lib, tmp_path):
    """Plain single-line signatures without a docstring should still flag."""
    f = tmp_path / "module.py"
    f.write_text(
        'def short(a, b):\n'
        '    return a + b\n'
    )
    findings = review_lib.check_docs(diff="", files=[str(f)])
    assert len(findings) == 1
    assert "short" in findings[0]
    assert "missing docstring" in findings[0]


# ── Private / leading-underscore names are ignored ──────────────────


def test_private_multiline_function_is_ignored(review_lib, tmp_path):
    """Leading-underscore names are private — should not be flagged even
    with multi-line signatures and no docstring.
    """
    f = tmp_path / "module.py"
    f.write_text(
        'def _private_helper(\n'
        '    a, b,\n'
        '):\n'
        '    return a\n'
    )
    findings = review_lib.check_docs(diff="", files=[str(f)])
    assert findings == []
