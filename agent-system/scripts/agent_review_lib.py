"""6-dim Agent Code Review — static analysis implementation (M3.1).

Each dimension is a check_<dim>(diff, files_changed) function returning
a list of findings (strings). The orchestrator runs all 6 in sequence
and renders a markdown report.

Note: The original spec called for invoking LLM subagents via
`claude --agent=...` or `subagent-cli`. Neither CLI exists in this
environment, and the post-commit hook is a bash script, not a Claude
session. This module implements the same 6 dimensions using
deterministic static analysis (regex/grep-style checks), so the
output is real and actionable rather than a placeholder.
"""
import re
import subprocess
import sys
from pathlib import Path


# ─── Diff / file helpers ─────────────────────────────────────────────

def _get_diff(commit_sha):
    """Return `git show <sha>` output (the diff)."""
    out = subprocess.run(
        ["git", "show", commit_sha],
        capture_output=True, text=True, check=True,
    ).stdout
    return out


def _get_files_changed(commit_sha):
    """Return list of files changed in the commit."""
    out = subprocess.run(
        ["git", "show", "--name-only", "--format=", commit_sha],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        return []
    return out.split("\n")


def _read_file(path):
    """Read a file, return content (or '' if unreadable)."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line_for(content, offset):
    """1-based line number for an offset into content."""
    return content[:offset].count("\n") + 1


def _added_lines(diff):
    """Yield (file, line_no, line_text) for added diff lines."""
    current_file = None
    new_line = 0
    for raw in diff.split("\n"):
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
        elif raw.startswith("@@"):
            # Parse hunk header: @@ -a,b +c,d @@
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if m:
                new_line = int(m.group(1))
        elif raw.startswith("+") and not raw.startswith("+++") and current_file:
            yield current_file, new_line, raw[1:]
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            # removed line: doesn't advance new_line
            continue
        else:
            # context line: advance new_line
            if not raw.startswith("\\"):
                new_line += 1


# ─── Dimension 1: Correctness ────────────────────────────────────────

def check_correctness(diff, files):
    """Find common Python correctness pitfalls in changed files."""
    findings = []
    py_files = [f for f in files if f.endswith(".py")]
    for f in py_files:
        content = _read_file(f)
        if not content:
            continue
        for m in re.finditer(r"==\s*None\b", content):
            line = _line_for(content, m.start())
            findings.append("`{0}:{1}` — `== None` should be `is None`".format(f, line))
        for m in re.finditer(r"!=\s*None\b", content):
            line = _line_for(content, m.start())
            findings.append("`{0}:{1}` — `!= None` should be `is not None`".format(f, line))
        for m in re.finditer(r"^\s*except\s*:\s*$", content, re.MULTILINE):
            line = _line_for(content, m.start())
            findings.append("`{0}:{1}` — bare `except:` swallows all errors".format(f, line))
        # Mutable default argument: `def f(x=[])` or `def f(x={})`
        for m in re.finditer(r"def\s+\w+\s*\([^)]*=\s*[\[\{]", content):
            line = _line_for(content, m.start())
            findings.append("`{0}:{1}` — possible mutable default argument".format(f, line))
    return findings


# ─── Dimension 2: Security ───────────────────────────────────────────

def check_security(diff, files):
    """Find common security issues in changed files."""
    findings = []
    py_files = [f for f in files if f.endswith(".py")]
    patterns = [
        (r"\beval\s*\(", "eval() — arbitrary code execution risk"),
        (r"\bexec\s*\(", "exec() — arbitrary code execution risk"),
        (r"os\.system\s*\(", "os.system() — shell injection risk"),
        (r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True", "subprocess with shell=True — injection risk"),
        (r"sk-[A-Za-z0-9]{20,}", "possible hardcoded API key (sk-...)"),
        (r"AKIA[0-9A-Z]{16}", "possible hardcoded AWS access key"),
        (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded password literal"),
        (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "hardcoded api_key literal"),
        (r"\.format\([^)]*\{[^}]*\}", "str.format with user input — possible injection"),
    ]
    for f in py_files:
        content = _read_file(f)
        if not content:
            continue
        for pattern, msg in patterns:
            for m in re.finditer(pattern, content):
                line = _line_for(content, m.start())
                findings.append("`{0}:{1}` — {2}".format(f, line, msg))
    return findings


# ─── Dimension 3: Performance ────────────────────────────────────────

def check_performance(diff, files):
    """Find common performance issues (N+1, nested loops)."""
    findings = []
    py_files = [f for f in files if f.endswith(".py")]
    for f in py_files:
        content = _read_file(f)
        if not content:
            continue
        # Detect `for ... in ...:` followed by execute() within 30 lines
        for m in re.finditer(r"for\s+(\w+)\s+in\s+([^:]+):", content):
            start = m.end()
            window = content[start:start + 3000]
            # Look for execute() in the loop body (heuristic: before next dedent)
            loop_lines = window.split("\n")
            execute_seen = False
            for ln in loop_lines:
                if not ln.startswith((" ", "\t")) and ln.strip() and not ln.lstrip().startswith(("#", "else", "elif")):
                    break
                if "cursor.execute" in ln or "session.execute" in ln or ".execute(" in ln:
                    execute_seen = True
                    break
            if execute_seen:
                line = _line_for(content, m.start())
                findings.append(
                    "`{0}:{1}` — possible N+1: loop body calls execute()".format(f, line)
                )
        # Detect `time.sleep` in request paths (very rough)
        for m in re.finditer(r"\btime\.sleep\s*\(", content):
            line = _line_for(content, m.start())
            findings.append(
                "`{0}:{1}` — time.sleep() in code path; consider async/await".format(f, line)
            )
    return findings


# ─── Dimension 4: Tests ──────────────────────────────────────────────

def check_tests(diff, files):
    """Find new functions without corresponding test coverage."""
    findings = []
    # Collect added `def name(` from non-test files
    new_functions = []  # (file, name, line)
    for f, line_no, text in _added_lines(diff):
        if "/tests/" in f or "/test_" in f or f.startswith("tests/"):
            continue
        if not f.endswith(".py"):
            continue
        m = re.match(r"\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", text)
        if m and not m.group(1).startswith("_"):
            new_functions.append((f, m.group(1), line_no))

    if not new_functions:
        return findings

    # Collect references to these names in added lines of test files
    test_lines = []
    for f, line_no, text in _added_lines(diff):
        if "/tests/" in f or "/test_" in f or f.startswith("tests/"):
            test_lines.append(text)

    test_blob = "\n".join(test_lines)
    seen = set()
    for f, name, line_no in new_functions:
        if name in seen:
            continue
        if name not in test_blob:
            findings.append(
                "new function `{0}()` at `{1}:{2}` has no test reference in diff".format(
                    name, f, line_no
                )
            )
            seen.add(name)

    # Also check for new skip/xfail/pytest.mark.skip without reason
    for f, line_no, text in _added_lines(diff):
        if not f.endswith(".py"):
            continue
        if "pytest.mark.skip" in text or "@pytest.mark.xfail" in text:
            if "reason=" not in text:
                findings.append(
                    "`{0}:{1}` — pytest skip/xfail missing `reason=`".format(f, line_no)
                )

    return findings[:20]  # cap


# ─── Dimension 5: Style ──────────────────────────────────────────────

def check_style(diff, files):
    """Find simple PEP 8 style violations in changed files."""
    findings = []
    py_files = [f for f in files if f.endswith(".py")]
    seen_keys = set()
    for f in py_files:
        content = _read_file(f)
        if not content:
            continue
        for i, line in enumerate(content.split("\n"), 1):
            if len(line) > 120:
                key = (f, i)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                findings.append(
                    "`{0}:{1}` — line length {2} > 120".format(f, i, len(line))
                )
                if len(findings) > 20:
                    return findings
    return findings


# ─── Dimension 6: Docs ───────────────────────────────────────────────

def _find_signature_end(content, paren_open_pos):
    """Return the offset of the `)` that closes the `(` at ``paren_open_pos``.

    Walks forward tracking paren depth, skipping over string literals and
    comments so that `(` characters inside defaults (e.g. ``f(x=[1,2])``)
    or docstrings (e.g. ``def foo(x: ")" = 1)``) don't fool the depth
    counter. Returns ``-1`` if no matching ``)`` is found within a
    reasonable distance.
    """
    depth = 0
    i = paren_open_pos
    n = len(content)
    while i < n:
        c = content[i]
        if c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth -= 1
            i += 1
            if depth == 0:
                return i - 1
        elif c == "#":
            # Skip to end of line (comment can't contain parens)
            while i < n and content[i] != "\n":
                i += 1
        elif c in ('"', "'"):
            # Skip the string literal (handle triple-quoted)
            if content[i:i + 3] in ('"""', "'''"):
                quote = content[i:i + 3]
                j = i + 3
                while j < n and content[j:j + 3] != quote:
                    j += 1
                i = j + 3 if j < n else n
            else:
                quote = c
                j = i + 1
                while j < n and content[j] != quote and content[j] != "\n":
                    if content[j] == "\\" and j + 1 < n:
                        j += 2
                    else:
                        j += 1
                i = j + 1
        else:
            i += 1
    return -1


def check_docs(diff, files):
    """Find public functions missing docstrings in changed files."""
    findings = []
    py_files = [f for f in files if f.endswith(".py")]
    seen_keys = set()
    for f in py_files:
        content = _read_file(f)
        if not content:
            continue
        for m in re.finditer(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content, re.MULTILINE):
            name = m.group(1)
            if name.startswith("_"):
                continue
            key = (f, name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            # Find the matching ')' for the '(' at m.end() - 1.
            # (The regex ends with `\(` so m.end() points at the char
            # right after `(`; the `(` itself is at m.end() - 1.)
            paren_open = m.end() - 1
            close_paren = _find_signature_end(content, paren_open)
            if close_paren < 0:
                # Couldn't find the matching ')' — skip to avoid false
                # positives on malformed snippets. This is a defensive
                # fallback; well-formed Python always has a matching ')'.
                continue
            # Advance past the rest of the def line (the `):` and any
            # trailing content) to get to the function body.
            newline_after = content.find("\n", close_paren)
            if newline_after < 0:
                # Single-line function: `def foo(): pass`
                body_start = len(content)
            else:
                body_start = newline_after + 1
            after = content[body_start:body_start + 500]
            next_lines = [l for l in after.split("\n") if l.strip()][:1]
            if next_lines and not next_lines[0].lstrip().startswith(('"""', "'''")):
                line = _line_for(content, m.start())
                findings.append(
                    "`{0}:{1}` — public function `{2}()` missing docstring".format(f, line, name)
                )
                if len(findings) > 20:
                    return findings
    return findings


# ─── Orchestrator ────────────────────────────────────────────────────

DIMENSIONS = [
    ("Correctness", check_correctness),
    ("Security", check_security),
    ("Performance", check_performance),
    ("Tests", check_tests),
    ("Style", check_style),
    ("Docs", check_docs),
]


def run_review(commit_sha):
    """Run all 6 dim checks on a commit and return findings as a dict."""
    diff = _get_diff(commit_sha)
    files = _get_files_changed(commit_sha)
    results = {}
    for name, check_fn in DIMENSIONS:
        try:
            results[name] = check_fn(diff, files)
        except Exception as e:  # noqa: BLE001
            results[name] = ["(check failed: {0})".format(e)]
    return {"results": results, "files": files, "diff": diff}


def render_report(commit_sha, results):
    """Render the findings as a markdown report body (no date/diff footer)."""
    short_sha = commit_sha[:7]
    findings_total = sum(len(v) for v in results["results"].values())
    files = sorted(set(f for f in results["files"] if f))
    lines = [
        "# Agent Code Review — {0}".format(short_sha),
        "",
        "**Commit:** `{0}`".format(commit_sha),
        "**Date:** __DATE_PLACEHOLDER__",
        "**Reviewer:** post_commit_review.sh (full mode, 6-dim static analysis)",
        "",
        "## Summary",
        "",
        "- Total findings: **{0}**".format(findings_total),
        "- Files reviewed: **{0}**".format(len(files)),
        "- Dimensions: 6 (Correctness, Security, Performance, Tests, Style, Docs)",
        "",
        "## Dimensions",
        "",
    ]
    for name, _ in DIMENSIONS:
        findings = results["results"].get(name, [])
        status = "clean" if not findings else "{0} finding(s)".format(len(findings))
        marker = "PASS" if not findings else "WARN"
        lines.append("### {0} — [{1}] {2}".format(name, marker, status))
        lines.append("")
        if findings:
            for f in findings:
                lines.append("- {0}".format(f))
        else:
            lines.append("_No issues found._")
        lines.append("")
    lines.extend([
        "## ISSUES FOUND",
        "",
    ])
    if findings_total == 0:
        lines.append("No issues found across all 6 dimensions.")
    else:
        lines.append("**{0} issue(s) found** — see per-dimension sections above.".format(findings_total))
    lines.extend([
        "",
        "## VERDICT",
        "",
        "PASS" if findings_total == 0 else "REVIEW ({0} finding(s))".format(findings_total),
        "",
        "---",
        "",
        "<details><summary>Diff (for reference)</summary>",
        "",
        "```diff",
        "__DIFF_PLACEHOLDER__",
        "```",
        "",
        "</details>",
    ])
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("usage: agent_review_lib.py <commit-sha> [date] [diff-file]", file=sys.stderr)
        sys.exit(2)
    commit_sha = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 else ""
    diff_path = sys.argv[3] if len(sys.argv) > 3 else ""
    try:
        results = run_review(commit_sha)
    except subprocess.CalledProcessError as e:
        print("git error: {0}".format(e), file=sys.stderr)
        sys.exit(1)
    report = render_report(commit_sha, results)
    if date_str:
        report = report.replace("__DATE_PLACEHOLDER__", date_str)
    if diff_path:
        try:
            with open(diff_path, "r", encoding="utf-8", errors="ignore") as fh:
                diff_text = fh.read().rstrip("\n")
        except OSError as e:
            print("diff read error: {0}".format(e), file=sys.stderr)
            diff_text = "(diff unavailable)"
        report = report.replace("__DIFF_PLACEHOLDER__", diff_text)
    sys.stdout.write(report)
    sys.exit(0)


if __name__ == "__main__":
    main()
