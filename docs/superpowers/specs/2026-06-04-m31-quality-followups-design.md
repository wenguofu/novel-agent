# M3.1 Quality Follow-ups — Design Spec

> **Status:** Design approved (2026-06-04). Awaiting user spec review.
> **Replaces:** §"M3.1 follow-ups" in `docs/superpowers/plans/2026-06-04-m3-functional-tests-precommit.md`

## Purpose

M3.1 closes the 5 quality gaps left by the M3 milestone (commit `7f29808`, "chore(M3): final test inventory snapshot"). M3 shipped:

- 356 tests, 0 failures, 5/5 verify_spec checks
- 55% line coverage (gate is ≥ 90%, so gate fails)
- Stub-mode post-commit 6-dim agent code review
- 25 endpoints with 4-dim tests, 57 with 2-dim tests

M3.1 ships 5 follow-ups to close those gaps.

## Goals (Success Criteria)

| # | Goal | Metric |
|---|------|--------|
| G1 | Bug found in M3 is fixed | `api_content_stats` returns 404 (not 500) for unknown novel |
| G2 | Coverage gate is met | `bash scripts/measure_coverage.sh` reports ≥ 90% line coverage on `portal/` |
| G3 | All 82 endpoints have 4-dim tests | 82 × 4 = 328 functional tests pass |
| G4 | Post-commit review uses 6 specialized agents | `.code-reviews/<sha>.md` has 6 sections + summary |
| G5 | CI runs the gate on every push | `.github/workflows/ci.yml` green on a smoke commit |

## Non-Goals (Out of Scope for M3.1)

- Refactoring `portal/app.py` (4000+ line monolith) — separate M4 work
- Refactoring `init_config_db.py` (marked "已废弃" → `init_unified_db.py`) — M4
- Adding new endpoints
- Changing the M3 test infrastructure (`tmp_db`, `client`, `sample_novel` fixtures)
- Coverage of `agent-system/` (out of M3.1 scope; covered by separate scripts)
- Coverage of `tests/` (test files don't count toward coverage)

## Workstreams (Execution Order)

M3.1 ships in 5 sequential workstreams. Order is chosen so each workstream unblocks the next:

```
W1 Hotfix         ─── 5 min  ───► unblocks regression test
W2 Coverage       ─── 1-2 days ─► unblocks CI gate (G2)
W3 4-dim upgrade  ─── 1 day   ──► closes functional coverage gap (G3)
W4 Full Agent-CR  ─── 0.5 day ──► finalizes post-commit review (G4)
W5 CI workflow    ─── 1 hour  ──► makes the gate run on every push (G5)
```

### W1: Hotfix — `api_content_stats` null-guard

**File:** `portal/app.py:3543`

**Bug:** When `get_novel_stats(unknown_name)` returns `None`, the handler does `if "error" in stats` which raises `TypeError` → HTTP 500.

**Fix:** `if stats is None or "error" in stats:` (one line).

**Test:** Regression test in `tests/functional/test_content_stats.py` (new file). Pattern: `client.get("/api/content/stats/<unknown_name>")` → assert 200 with `{"error": "novel not found"}` (NOT 500).

**Commit:** `hotfix(M3.1): api_content_stats null-guard`

**Exemption:** Hotfix commit title bypasses the TDD physical gate (per the gate's `hotfix` rule, established in M3 Task 3).

### W2: Coverage gap 55% → 90%

**Scope:** Unit tests for internal helpers in `portal/`. Functional tests in `tests/functional/` already exist for the 82 endpoints.

**Per-module targets:**

| Module | Current | Target | Rationale |
|--------|---------|--------|-----------|
| `repository.py` | 58% | 90% | 110+ methods; high test surface; cover all CRUD methods + lookup helpers |
| `init_unified_db.py` | 0% | 80% | Schema init: smoke test for each `CREATE TABLE` + idempotency |
| `run_v2.py` | 0% | 60% | Entry point hard to test fully; target: import smoke + `ensure_unified_schema()` invocation |
| `models.py` | 0% | 80% | SQLAlchemy ORM model smoke tests (instantiate, basic fields) |
| `resilience.py` | 0% | 80% | Defensive helpers (retries, circuit breaker); cover branches |

**Excluded modules (justified):**

| Module | Reason for exclusion |
|--------|----------------------|
| `init_config_db.py` | Marked "已废弃" → `init_unified_db.py`; refactor in M4 |
| `logging_config.py` | 5-line module, 100% covered by import |
| `errors.py` | Defensive-only (no logic to test) |
| `app.py` (route handlers) | Covered by 4-dim functional tests in W3 |
| `context_builder.py` | Already covered via 4-dim functional tests |

**Coverage tool:** `pytest-cov` (already in `requirements-dev.txt` or `requirements.txt` — verify). The `scripts/measure_coverage.sh` gate (M3 Task 15, commit `aec0b4c`) reads `pytest-cov` output and parses `TOTAL\s+\d+\s+\d+\s+\d+%`.

**Per-file thresholds:** Use `.coveragerc` or `pyproject.toml [tool.coverage.report]` with `exclude_lines` for `if __name__ == "__main__":` and `pragma: no cover`. Each module gets a separate test file:
- `tests/unit/test_repository.py`
- `tests/unit/test_init_unified_db.py`
- `tests/unit/test_run_v2.py`
- `tests/unit/test_models.py`
- `tests/unit/test_resilience.py`

**Test pattern:** pytest, no Flask test_client, no DB (where possible). For repository.py, use the `tmp_db` fixture (already exists in `tests/functional/conftest.py`). For pure-logic modules, no fixtures needed.

**Commits:** 5 commits, one per module:
- `test(M3.1): unit tests for repository.py (58% → 90%)`
- `test(M3.1): unit tests for init_unified_db.py (0% → 80%)`
- `test(M3.1): unit tests for run_v2.py (0% → 60%)`
- `test(M3.1): unit tests for models.py (0% → 80%)`
- `test(M3.1): unit tests for resilience.py (0% → 80%)`

### W3: 4-dim upgrade for 57 non-core endpoints

**Scope:** 8 test files (each covers a category of non-core endpoints) currently have 2-dim tests (happy_path + wrong_method). Add `not_found` and `missing_field` dimensions to bring them to 4-dim.

**Reference pattern:** `tests/functional/test_chapter_lifecycle.py:35-90` (M3 Task 4 reference, 4-dim pattern).

**4 dimensions:**
1. `happy_path` — known input, expect 200/201
2. `wrong_method` — wrong HTTP verb, expect 405 (or shadow-404 if shadowed)
3. `not_found` — unknown ID, expect 404
4. `missing_field` — JSON payload missing required field, expect 400

**Test files to upgrade:**

| File | Endpoints covered | Pattern issues documented |
|------|-------------------|---------------------------|
| `test_novel_crud.py` | 5 novel CRUD | `<novel_name>` greedy match; PUT for 405 |
| `test_outline_api.py` | 4 outline | Uses `_point_content_db_at_tmp` helper |
| `test_outline_table.py` | 5 outline-table | `content_db.DB_PATH` monkeypatch |
| `test_character.py` | 4 character | Payload schema: `name`+`description` |
| `test_foreshadowing.py` | 2 foreshadowing | Same |
| `test_world_building.py` | 3 world-building | `domain`+`name`+`content` |
| `test_plot_arcs.py` | 2 plot-arcs | `name`+`type` |
| `test_pacing_revelation.py` | 5 pacing/revelation | `volume`+`chapter_start`+`chapter_end`+`pace_type` |

**Each test file:** add 2 new test functions per endpoint (one `not_found`, one `missing_field`). Total: ~57 × 2 = 114 new tests.

**Helper extraction:** If the `not_found` and `missing_field` patterns repeat across test files, extract a `tests/functional/_helpers.py` module with reusable fixtures (e.g., `assert_not_found`, `assert_missing_field`).

**Commits:** 8 commits, one per test file:
- `test(M3.1): 4-dim upgrade for novel CRUD (2-dim → 4-dim)`
- `test(M3.1): 4-dim upgrade for outline API (2-dim → 4-dim)`
- ... (6 more)

### W4: Full 6-dim Agent Code Review

**Current state:** M3 (commit `6d6c3e8`) wrote a stub report. The hook is at `.claude/hooks/post-commit`, calling `agent-system/scripts/post_commit_review.sh`.

**Target:** 6 specialized subagents, each reviewing one dimension, writing a section to `.code-reviews/<sha>.md`.

**6 dimensions:**

1. **correctness** — logic errors, type errors, off-by-one, wrong conditional
2. **security** — injection, auth bypass, secrets in code, path traversal
3. **performance** — N+1 queries, missing indexes, O(n²) algorithms
4. **tests** — coverage gaps, missing edge cases, flaky test patterns
5. **style** — PEP 8, naming, comments, docstrings
6. **docs** — docstrings on public functions, README updates, OpenSpec updates

**Implementation:**

`agent-system/scripts/post_commit_review.sh` (rewrite):
```bash
#!/usr/bin/env bash
# 1. Read the diff (via `git show <sha>`)
# 2. Dispatch 6 subagents in parallel (using `claude --agent=...` or `subagent-cli`)
# 3. Each agent writes its section to a tmp file
# 4. Concatenate into .code-reviews/<sha>.md
```

Each subagent invocation:
- Reads the diff (passed via stdin or argv)
- Applies its dimension-specific prompt (in `agent-system/prompts/review/<dim>.md`)
- Writes `<tmp>/<dim>.md`
- The orchestration script concatenates with a summary header

**Fallback:** `AGENT_CR_MODE=stub` env var keeps the M3 stub behavior (placeholder report). Default is `full`.

**Triggers:** All commits except:
- `hotfix` commits (per M3 Task 16)
- Commits to `.claude/hooks/`, `agent-system/scripts/`, `scripts/install-hooks.sh` (hook self-changes)
- Empty diffs (e.g., merge commits)

**Test:** Integration test in `tests/functional/test_agent_cr.py`:
- Trigger a real commit on a test file
- Verify `.code-reviews/<sha>.md` exists with 6 sections + summary header
- Assert each section has a non-empty body

**Commit:**
- `feat(M3.1): wire full 6-dim agent code review (6 specialized subagents)`

### W5: CI workflow file

**File:** `.github/workflows/ci.yml` (new).

**Contents:**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.9"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
      - name: Run tests + coverage
        run: bash scripts/measure_coverage.sh
      - name: Verify spec consistency
        run: python3 scripts/verify_spec.py
```

**Verification:** Create a feature branch, push, verify CI is green. Then merge.

**Commit:**
- `ci(M3.1): add CI workflow (tests + coverage + spec verify)`

## Data Flow

```
developer commit
       │
       ▼
post-commit hook  ──► agent-system/scripts/post_commit_review.sh
                          │
                          ├─► stub? ──► placeholder report
                          │
                          └─► full? ──► 6 parallel subagents
                                            │
                                            ▼
                                       .code-reviews/<sha>.md

later, on push:
       │
       ▼
GitHub Actions CI  ──► measure_coverage.sh (must pass ≥ 90%)
                   ──► verify_spec.py (must pass 5/5)
```

## Error Handling

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Coverage target missed on a stubborn module (e.g., `run_v2.py` is hard to unit-test) | Medium | High | Set per-file thresholds in `.coveragerc`; target the most-testable modules first (repository.py), evaluate, then attempt harder ones |
| 4-dim tests reveal real bugs in `app.py` | High | Medium | Flag bugs as separate hotfixes; don't fix in the 4-dim task. Add to M3.2 backlog. |
| Agent-CR cost (6 subagents per commit) | Low | Low | `AGENT_CR_MODE=stub` fallback; default `full` only on PR commits to `main` |
| Agent-CR API failures (one dim fails, others succeed) | Medium | Low | Per-dim try/catch; if any fails, mark the section as `## <dim> (FAILED: <reason>)` and continue |
| CI workflow fails on Linux (path differences, deps) | Low | Medium | Smoke test on a feature branch first; use Python 3.9 (matches local dev) |
| 4-dim tests are noisy (114 new tests) | High | Low | Establish helper in Task 8 (first 4-dim extension); reuse across all 8 files |

## Testing Strategy

- **W1 (hotfix):** 1 regression test in `tests/functional/test_content_stats.py`
- **W2 (coverage):** ~50 unit tests across 5 new files in `tests/unit/`
- **W3 (4-dim):** ~114 new tests (2 dims × 57 endpoints) across 8 existing files in `tests/functional/`
- **W4 (agent-CR):** 1 integration test in `tests/functional/test_agent_cr.py`
- **W5 (CI):** Smoke test: create a feature branch, push, verify green

**Final test count target:** 356 → ~522 tests (1 hotfix regression + ~50 unit tests + ~114 4-dim extensions + 1 agent-CR integration = 522)

**Coverage target:** 55% → 90% (line) on `portal/`

**Spec verification:** all 5 verify_spec.py checks still pass (endpoint count, repo methods count, etc., unchanged)

## File Touchpoint Summary

| File | W1 | W2 | W3 | W4 | W5 |
|------|----|----|----|----|----|
| `portal/app.py` | ✏️ line 3543 | | | | |
| `tests/functional/test_content_stats.py` (new) | ✏️ | | | | |
| `tests/unit/test_repository.py` (new) | | ✏️ | | | |
| `tests/unit/test_init_unified_db.py` (new) | | ✏️ | | | |
| `tests/unit/test_run_v2.py` (new) | | ✏️ | | | |
| `tests/unit/test_models.py` (new) | | ✏️ | | | |
| `tests/unit/test_resilience.py` (new) | | ✏️ | | | |
| `tests/functional/test_novel_crud.py` | | | ✏️ | | |
| `tests/functional/test_outline_api.py` | | | ✏️ | | |
| `tests/functional/test_outline_table.py` | | | ✏️ | | |
| `tests/functional/test_character.py` | | | ✏️ | | |
| `tests/functional/test_foreshadowing.py` | | | ✏️ | | |
| `tests/functional/test_world_building.py` | | | ✏️ | | |
| `tests/functional/test_plot_arcs.py` | | | ✏️ | | |
| `tests/functional/test_pacing_revelation.py` | | | ✏️ | | |
| `tests/functional/_helpers.py` (new) | | | ✏️ | | |
| `agent-system/scripts/post_commit_review.sh` | | | | ✏️ rewrite | |
| `agent-system/prompts/review/<dim>.md` (6 new) | | | | ✏️ | |
| `tests/functional/test_agent_cr.py` (new) | | | | ✏️ | |
| `.github/workflows/ci.yml` (new) | | | | | ✏️ |
| `requirements-dev.txt` (new if missing) | | maybe | | | ✏️ |
| `.coveragerc` (new) | | ✏️ | | | |

**Total:** ~21 commits, ~22 files modified or created, ~522 tests after completion.

## Commits & Branch

- **Branch:** `main` (incremental quality work, not a feature)
- **Commits:** ~21 atomic commits, each scoped to one task
- **Commit message style:** Consistent with M1-M3 (`test(M3.1): ...`, `feat(M3.1): ...`, `hotfix(M3.1): ...`, `ci(M3.1): ...`)

## Dependencies

- W2 depends on W1 (hotfix unblocks the regression test which is part of the coverage verification)
- W3 depends on W2 (functional tests count toward coverage; must add before measuring)
- W4 depends on W3 (agent-CR is the last thing reviewed; if 4-dim changes the test infrastructure, agent-CR's review will be more accurate)
- W5 depends on W2 (CI gate must have something to gate on)

## Open Questions

None — all clarifications resolved during brainstorming:
- Scope: Full M3.1 (all 5 follow-ups) ✓
- Sequencing: hotfix → coverage → 4-dim → agent-CR → CI ✓
- 4-dim scope: all 57 endpoints ✓
- Agent-CR scope: 6 specialized subagents ✓
- Coverage strategy: pragmatic 90% excluding deprecated modules ✓
