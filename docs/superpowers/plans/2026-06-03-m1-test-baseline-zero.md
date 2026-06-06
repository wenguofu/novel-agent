# M1 — Test Baseline to Zero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Get `pytest tests/ -q` from 22 failed + 15 errors (37 nodeids total) to 0 failed + 0 errors, with every failure explicitly classified F1-F4 and recorded in `tests/audit/baseline_after.json`.

**Architecture:** Use a data-driven audit tool to read the real pytest output, group 37 failures into F1-F4 buckets, fix or skip each one, and produce a reproducible before/after JSON pair. No fix is accepted without an `audit/failures.json` row and a verification commit.

**Tech Stack:** pytest 7+, Python 3.9, json (stdlib), existing SQLite-backed portal.

**Source spec:** `docs/superpowers/specs/2026-06-03-tdd-system-func-spec-design.md` §M1

**Baseline (locked from `pytest tests/ -q --tb=no` on 2026-06-03):** 119 tests, 82 passed, **22 failed + 15 errors = 37 broken nodeids**.

**Failure distribution by file (verified):**
| File | FAILED | ERROR | Total |
|------|--------|-------|-------|
| tests/test_schema.py | 15 | 0 | 15 |
| tests/test_init.py | 0 | 8 | 8 |
| tests/test_incremental.py | 0 | 5 | 5 |
| tests/test_reviews_schema.py | 2 | 0 | 2 |
| tests/test_generate_context.py | 2 | 0 | 2 |
| tests/test_sidebar.py | 0 | 2 | 2 |
| tests/test_token_truncation.py | 1 | 0 | 1 |
| tests/test_memory_layer.py | 1 | 0 | 1 |
| tests/test_context_builder.py | 1 | 0 | 1 |
| **Total** | **22** | **15** | **37** |

---

## File Structure

**Create:**
- `scripts/audit_test_failures.py` — parses `pytest --tb=line` output, emits failures.json + REPORT.md
- `tests/audit/baseline_before.json` — frozen list of 37 broken nodeids
- `tests/audit/baseline_after.json` — final disposition per nodeid
- `tests/audit/failures.json` — current per-test detail (re-generated on each run)
- `tests/audit/REPORT.md` — human-readable classification report
- `tests/audit/fix_log.md` — running log of fixes (one line per fix, append-only)

**Modify (only if F1/F2 classification requires it):**
- `portal/db.py` — possibly add missing columns to `ensure_unified_schema`
- `portal/repository.py` — possibly add missing CRUD methods
- `tests/test_*.py` — possibly fix test bugs (F2) or xfail them (F3)
- `tests/audit/` — no modifications to `baseline_before.json` after creation

---

## Task 1: Create audit tool

**Files:**
- Create: `scripts/audit_test_failures.py`
- Create: `tests/audit/.gitkeep`

- [x] **Step 1: Create `tests/audit/` directory placeholder**

```bash
mkdir -p tests/audit
touch tests/audit/.gitkeep
```

- [x] **Step 2: Write the audit tool**

Create `scripts/audit_test_failures.py`:

```python
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
```

- [x] **Step 3: Run the audit tool**

```bash
python3 scripts/audit_test_failures.py
```

Expected output: `Wrote failures.json (37 rows) + REPORT.md` and `Totals: passed=82 failed=22 error=15`.

- [x] **Step 4: Verify outputs**

```bash
ls -la tests/audit/
python3 -c "import json; d=json.load(open('tests/audit/failures.json')); print(len(d), 'rows; first:', d[0]['nodeid'])"
```

Expected: 37 rows; first nodeid matches one of the 37 from the baseline.

- [x] **Step 5: Commit**

```bash
git add scripts/audit_test_failures.py tests/audit/.gitkeep tests/audit/failures.json tests/audit/REPORT.md
git commit -m "feat(M1): audit tool — parse pytest failures to JSON + REPORT"
```

---

## Task 2: Freeze baseline_before.json

**Files:**
- Create: `tests/audit/baseline_before.json`

- [x] **Step 1: Generate baseline_before.json from current failures.json**

```bash
python3 -c "
import json
from pathlib import Path
d = json.load(open('tests/audit/failures.json'))
baseline = [{'nodeid': r['nodeid'], 'status': r['status']} for r in d]
Path('tests/audit/baseline_before.json').write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
print('Wrote', len(baseline), 'nodeids')
"
```

Expected: `Wrote 37 nodeids`.

- [x] **Step 2: Verify baseline_before.json is committed-and-frozen**

```bash
git add tests/audit/baseline_before.json
git commit -m "chore(M1): freeze baseline_before.json — 37 broken tests"
```

After this commit, `baseline_before.json` is the source of truth. It MUST NOT be modified in later tasks.

---

## Task 3: Initialize baseline_after.json skeleton

**Files:**
- Create: `tests/audit/baseline_after.json`

- [x] **Step 1: Seed baseline_after.json with 37 placeholder rows**

```bash
python3 -c "
import json
before = json.load(open('tests/audit/baseline_before.json'))
after = [
    {'nodeid': r['nodeid'], 'original_status': r['status'],
     'final_status': 'PENDING', 'category': None, 'note': ''}
    for r in before
]
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Seeded', len(after), 'PENDING rows')
"
```

- [x] **Step 2: Commit skeleton**

```bash
git add tests/audit/baseline_after.json
git commit -m "chore(M1): seed baseline_after.json with 37 PENDING rows"
```

---

## Task 4: Fix the 15 test_schema.py failures (F1 — missing schema)

**Files:**
- Modify: `portal/db.py` (add missing columns to `ensure_unified_schema`)
- Test: `tests/test_schema.py` (existing — should pass after fix)

These 15 failures are all `TestNewTables::*` (table/column existence) + `TestCRUD::*` (CRUD smoke). Root cause: `ensure_unified_schema` is missing some columns. Read each failure, find the missing column, add a `try ADD COLUMN` in `ensure_unified_schema`.

- [x] **Step 1: Get the precise missing-column list**

```bash
python3 -m pytest tests/test_schema.py -q --tb=short 2>&1 | grep -E "OperationalError|assert" | head -30
```

- [x] **Step 2: Read `portal/db.py` find `ensure_unified_schema`**

```bash
grep -n "def ensure_unified_schema" portal/db.py
```

- [x] **Step 3: For each missing column/table, add migration block**

In `ensure_unified_schema`, after the table creation, add idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` for every missing column. (MySQL note: MySQL 8 doesn't have `IF NOT EXISTS` for `ADD COLUMN` — use `try/except` block.)

- [x] **Step 4: Run test_schema.py**

```bash
python3 -m pytest tests/test_schema.py -q
```

Expected: 0 failed, 0 errors in test_schema.py.

- [x] **Step 5: Update baseline_after.json for 15 schema tests (category F1)**

```bash
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_schema.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'
    r['note'] = 'Added missing column to ensure_unified_schema'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 6: Commit**

```bash
git add portal/db.py tests/audit/baseline_after.json
git commit -m "fix(M1): add missing schema columns — 15 test_schema.py tests pass (F1)"
```

---

## Task 5: Fix the 8 test_init.py errors (F1 — broken init functions)

**Files:**
- Modify: `portal/repository.py` (or `portal/init_unified_db.py`)
- Test: `tests/test_init.py`

- [x] **Step 1: Get error details**

```bash
python3 -m pytest tests/test_init.py -q --tb=short 2>&1 | grep -E "Error|sqlite" | head -20
```

- [x] **Step 2: Run test_init.py to see fresh tracebacks**

```bash
python3 -m pytest tests/test_init.py::TestWorldBuildingInit::test_wb_init_creates_entries -x --tb=long 2>&1 | tail -40
```

- [x] **Step 3: Fix the broken init functions one by one**

For each erroring init test, follow the traceback into the corresponding init function, fix the SQL or column reference. Run the test after each fix.

- [x] **Step 4: Verify all 8 pass**

```bash
python3 -m pytest tests/test_init.py -q
```

Expected: 0 failed, 0 errors.

- [x] **Step 5: Update baseline_after.json (8 rows, F1)**

```bash
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_init.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'
    r['note'] = 'Fixed init function SQL/column reference'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 6: Commit**

```bash
git add portal/repository.py portal/init_unified_db.py tests/audit/baseline_after.json
git commit -m "fix(M1): fix 8 init function errors (F1)"
```

---

## Task 6: Fix the 5 test_incremental.py errors (F1 — broken update methods)

**Files:**
- Modify: `portal/repository.py`
- Test: `tests/test_incremental.py`

- [x] **Step 1: Get error details**

```bash
python3 -m pytest tests/test_incremental.py -q --tb=line 2>&1 | tail -20
```

- [x] **Step 2: Fix each broken update method**

For each erroring test, run individually with `--tb=long`, trace into `repository.py`, fix the SQL.

- [x] **Step 3: Verify**

```bash
python3 -m pytest tests/test_incremental.py -q
```

Expected: 0 failed, 0 errors.

- [x] **Step 4: Update baseline_after.json (5 rows, F1)**

```bash
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_incremental.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'
    r['note'] = 'Fixed repository update method'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 5: Commit**

```bash
git add portal/repository.py tests/audit/baseline_after.json
git commit -m "fix(M1): fix 5 incremental update method errors (F1)"
```

---

## Task 7: Fix the 2 test_reviews_schema.py failures

**Files:**
- Modify: `portal/db.py` (likely add missing `reviews` columns)
- Test: `tests/test_reviews_schema.py`

- [x] **Step 1: Get details**

```bash
python3 -m pytest tests/test_reviews_schema.py -q --tb=short 2>&1 | tail -15
```

- [x] **Step 2: Fix**

Add missing columns to `reviews` table in `ensure_unified_schema`. Re-run.

- [x] **Step 3: Verify + update baseline_after.json (F1)**

```bash
python3 -m pytest tests/test_reviews_schema.py -q
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_reviews_schema.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'
    r['note'] = 'Added missing reviews column'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 4: Commit**

```bash
git add portal/db.py tests/audit/baseline_after.json
git commit -m "fix(M1): add missing reviews schema columns (F1)"
```

---

## Task 8: Fix the 2 test_generate_context.py failures

**Files:**
- Modify: `portal/ctx_v2.py` or `portal/context_builder.py`
- Test: `tests/test_generate_context.py`

- [x] **Step 1: Get details**

```bash
python3 -m pytest tests/test_generate_context.py -q --tb=short 2>&1 | tail -20
```

- [x] **Step 2: Fix the build_context fallback / pacing loading**

Trace the failure into ctx_v2.py, fix the load order or the key name.

- [x] **Step 3: Verify + update baseline_after.json (F1)**

```bash
python3 -m pytest tests/test_generate_context.py -q
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_generate_context.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'
    r['note'] = 'Fixed ctx_v2 build_context'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 4: Commit**

```bash
git add portal/ctx_v2.py tests/audit/baseline_after.json
git commit -m "fix(M1): fix generate_context build_context (F1)"
```

---

## Task 9: Fix the 2 test_sidebar.py errors (F1 — wrong API shape)

**Files:**
- Modify: `portal/app.py` or `portal/repository.py`
- Test: `tests/test_sidebar.py`

- [x] **Step 1: Get details**

```bash
python3 -m pytest tests/test_sidebar.py -q --tb=short 2>&1 | tail -15
```

- [x] **Step 2: Fix the API shape**

Adjust the endpoint to match the test expectation (or vice versa — verify which side is the spec).

- [x] **Step 3: Verify + update baseline_after.json (F1 or F2)**

```bash
python3 -m pytest tests/test_sidebar.py -q
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
fixed = [r for r in after if r['nodeid'].startswith('tests/test_sidebar.py::')]
for r in fixed:
    r['final_status'] = 'PASSED'
    r['category'] = 'F1'  # or F2 if test was wrong
    r['note'] = 'Fixed sidebar API shape'
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated', len(fixed), 'rows')
"
```

- [x] **Step 4: Commit**

```bash
git add portal/app.py tests/audit/baseline_after.json
git commit -m "fix(M1): fix sidebar API shape (F1)"
```

---

## Task 10: Fix the 3 remaining single-test failures

**Files:**
- Modify: per-failure (1 each)
- Test: `tests/test_token_truncation.py` / `tests/test_memory_layer.py` / `tests/test_context_builder.py`

- [x] **Step 1: Get details for all 3**

```bash
python3 -m pytest tests/test_token_truncation.py::TestTokenTruncation::test_truncation_respects_budget_with_large_content tests/test_memory_layer.py::TestMemoryIntegration::test_fallback_state_context tests/test_context_builder.py::TestContextStats::test_context_stats_structure -q --tb=short 2>&1 | tail -30
```

- [x] **Step 2: Fix each**

For each, follow the traceback and fix. `test_context_stats_structure` is documented in spec as pre-existing — if it's a "novel-not-found returns wrong shape" issue, classify as F1 (fix the endpoint to return the spec's `{"error": ...}` shape consistently) or F2 (fix the test to match actual behavior).

- [x] **Step 3: Verify all 3 pass + update baseline_after.json (1 each)**

```bash
python3 -m pytest tests/test_token_truncation.py::TestTokenTruncation::test_truncation_respects_budget_with_large_content tests/test_memory_layer.py::TestMemoryIntegration::test_fallback_state_context tests/test_context_builder.py::TestContextStats::test_context_stats_structure -v
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
for needle, note in [
    ('tests/test_token_truncation.py', 'Fixed truncation logic'),
    ('tests/test_memory_layer.py', 'Fixed memory layer fallback'),
    ('tests/test_context_builder.py', 'Fixed context stats shape (per spec)'),
]:
    fixed = [r for r in after if r['nodeid'].startswith(needle)]
    for r in fixed:
        if r['final_status'] == 'PENDING':
            r['final_status'] = 'PASSED'
            r['category'] = 'F1'
            r['note'] = note
json.dump(after, open('tests/audit/baseline_after.json', 'w'), indent=2, ensure_ascii=False)
print('Updated remaining PENDING rows')
"
```

- [x] **Step 4: Commit**

```bash
git add -A
git commit -m "fix(M1): fix last 3 single-test failures (F1)"
```

---

## Task 11: Final verification

- [x] **Step 1: Run full suite**

```bash
python3 -m pytest tests/ -q
```

Expected: `0 failed, X passed, 0 errors` where X ≥ 119.

- [x] **Step 2: Re-run audit tool to confirm**

```bash
python3 scripts/audit_test_failures.py
cat tests/audit/failures.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)),'rows (expected 0)')"
```

Expected: `0 rows (expected 0)`.

- [x] **Step 3: Verify baseline_after.json — all 37 rows have non-PENDING final_status**

```bash
python3 -c "
import json
after = json.load(open('tests/audit/baseline_after.json'))
pending = [r for r in after if r['final_status'] == 'PENDING']
print(f'Pending: {len(pending)} of {len(after)}')
assert len(pending) == 0, f'Still PENDING: {pending}'
buckets = {}
for r in after:
    buckets[r['category']] = buckets.get(r['category'], 0) + 1
print('By category:', buckets)
"
```

Expected: `Pending: 0 of 37` + a bucket breakdown showing F1 / F2 / F3 / F4 distribution.

- [x] **Step 4: Update README "TDD" section (small)**

Add a section to README.md after the 12-layer table:

```markdown
## TDD 流程

`portal/` 改动必须同时改 `tests/`。物理门见 `.pre-commit-config.yaml` (`tdd-required-test` hook)。
豁免: commit 标题含 `hotfix`。
基线: `pytest tests/ -q` 当前 0 failed / 0 errors (维护自 2026-06-03, 见 `tests/audit/baseline_after.json`)。
```

- [x] **Step 5: Commit final state**

```bash
git add tests/audit/baseline_after.json README.md
git commit -m "chore(M1): M1 complete — 0 failed, 0 errors, baseline frozen"
```

---

## Self-Review

**1. Spec coverage:**
- F1-F4 严格 4 档分类 → Task 4-10 each use F1, with the option to use F2/F3/F4 in Step notes
- 不删实现硬约束 → preserved (all fixes are F1 = fix the implementation)
- 不引入新依赖 → only stdlib `json`, `re`, `subprocess`, `pathlib`
- 审计数据可复现 → `baseline_before.json` never modified, `baseline_after.json` carries dispositions
- 验收: `pytest tests/ -q` 0 failed + 0 errors → Task 11 Step 1

**2. Placeholder scan:** No "TBD"/"TODO"/"implement later" found. Each step has concrete code/commands.

**3. Type consistency:**
- `failures.json` schema: `{status, nodeid, summary}` defined in Task 1, used in Task 2-3
- `baseline_before.json` schema: `[{nodeid, status}]` defined in Task 2, consumed in Task 3
- `baseline_after.json` schema: `[{nodeid, original_status, final_status, category, note}]` defined in Task 3, updated in Task 4-10, verified in Task 11
- All consistent ✅

**4. Ambiguity check:** 
- "Add missing columns" in Task 4 is intentionally generic — actual columns must be read from each test's traceback. Acceptable: plan is bite-sized, not exhaustive.
- "Fix the broken init function" Task 5 — same pattern. The point is the workflow (read → fix → re-run → record), not the specific column.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-03-m1-test-baseline-zero.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

---

## Implementation Pointer

> **Status:** All 11 tasks + self-review items were already implemented across commits `fc23bb3`, `5ec6276`, `1acdcfb`, `56931a1`, `1d78d9e`, `12c76d6`, `958c329`, `85de1e9`, and `4878db3` between 2026-06-03 and 2026-06-03 — landing the same day the plan was written.
>
> **Verified 2026-06-06:** 1031/1031 tests pass (0 failed, 0 errors). No code changes needed; this is a checkbox backfill + plan close-out.
>
> **Note:** The work was executed close to the plan's envisioned sequence: audit tool → freeze baseline → seed baseline_after → schema fix (Task 4) → which transitively fixed 20 more rows (1d78d9e) → final 2 real failures fixed (12c76d6) → small refactor (958c329) → final commit (85de1e9) → audit-trail notes cleanup (4878db3). Test count has since grown from 119 → 1031 across M2/M3 work, but the M1 baseline of 0 failed / 0 errors is preserved.
