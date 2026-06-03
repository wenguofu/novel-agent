#!/usr/bin/env python3
"""
Audit pytest failures: parse `pytest --tb=line -q`, emit
tests/audit/failures.json (machine) + tests/audit/REPORT.md (human).

Usage:
  python3 scripts/audit_test_failures.py
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent.parent / "tests" / "audit"


def run_pytest() -> str:
    """Run pytest, return raw output."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line", "--no-header"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout + "\n" + result.stderr


def parse_nodeids(output: str) -> list[dict]:
    """Parse FAILED/ERROR lines into structured rows."""
    rows = []
    pattern = re.compile(
        r"^(FAILED|ERROR)\s+(tests/[^:]+::[^ ]+)(?:\s+-\s+(.+))?$", re.MULTILINE
    )
    for m in pattern.finditer(output):
        rows.append({
            "status": m.group(1),
            "nodeid": m.group(2),
            "summary": (m.group(3) or "").strip(),
        })
    return rows


def write_json(name: str, data) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def write_report(rows: list[dict], totals: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Test Failure Audit Report",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## Totals",
        f"- PASS: {totals.get('passed', 0)}",
        f"- FAILED: {totals.get('failed', 0)}",
        f"- ERROR: {totals.get('error', 0)}",
        "",
        "## Failures by File",
    ]
    by_file = defaultdict(list)
    for r in rows:
        file = r["nodeid"].split("::")[0]
        by_file[file].append(r)
    for file, items in sorted(by_file.items()):
        lines.append(f"\n### `{file}` ({len(items)})")
        for r in items:
            lines.append(f"- **{r['status']}** `{r['nodeid']}` — {r['summary']}")
    path = AUDIT_DIR / "REPORT.md"
    path.write_text("\n".join(lines))
    return path


def main() -> int:
    print("Running pytest…")
    output = run_pytest()
    rows = parse_nodeids(output)
    totals = {
        "passed": len(re.findall(r"^(\d+) passed", output, re.MULTILINE)) and 0 or 0,
        "failed": sum(1 for r in rows if r["status"] == "FAILED"),
        "error": sum(1 for r in rows if r["status"] == "ERROR"),
    }
    m = re.search(r"(\d+) passed", output)
    if m:
        totals["passed"] = int(m.group(1))
    write_json("failures.json", rows)
    write_report(rows, totals)
    print(f"Wrote failures.json ({len(rows)} rows) + REPORT.md")
    print(f"Totals: passed={totals['passed']} failed={totals['failed']} error={totals['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
