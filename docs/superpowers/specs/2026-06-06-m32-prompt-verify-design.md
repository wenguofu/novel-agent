# M3.2 — Prompt Verify + v1/v2 Reconcile — Design Spec

> **Status:** Design approved (2026-06-06). Awaiting user spec review.
> **Replaces:** N/A (no prior M3.2 spec).
> **Builds on:** M3.1 (commit `5d7a747`) + 2026-06-02 audit in [docs/optimization_plan_writing_prompt.md](../../optimization_plan_writing_prompt.md).

## Purpose

The 2026-06-02 audit in `docs/optimization_plan_writing_prompt.md` identified 11 P0–P3 issues in the chapter-generation prompt pipeline. Substantial implementation has already landed in the repo — but:

1. **The implementation is unverified by tests.** Only 3 thin test files (108 + 147 + 71 lines) touch `context_builder`/`ctx_v2`, all structural. There is no per-layer snapshot test suite. `context_builder.py` and `ctx_v2.py` were both excluded from the M3.1 coverage gate.
2. **There are three parallel implementations** of the same orchestrator: `portal/context_builder.py` (743 lines), `portal/ctx_v2.py` (366 lines, "Volume-Scoped, drop-in replacement"), and `portal/context_builder_v2.py` (512 lines). `portal/run_v2.py:155-158` silently hot-patches `context_builder.build_context = ctx_v2.build_context` at import time. No spec governs which is canonical.
3. **There is no baseline for prompt quality.** No reference document of "what the LLM actually sees" for a known novel × chapter, so any future change to the layer pipeline has no regression baseline.

M3.2 closes these three gaps.

## Goals (Success Criteria)

| # | Goal | Metric |
|---|------|--------|
| G1 | One canonical context builder | `grep -rn "from context_builder import" portal/` returns zero matches (all callers use `from ctx_v2 import build_context`); `portal/context_builder.py` and `portal/context_builder_v2.py` are deleted |
| G2 | Per-layer snapshot tests pass | `pytest tests/unit/test_context_layers.py -v` reports 12 layer test classes + 1 integration test = ≥ 13 tests, all green |
| G3 | Coverage gate passes with ctx_v2 measured | `bash scripts/measure_coverage.sh` reports ≥ 90% line coverage on `portal/` with `ctx_v2.py` **not** in the `.coveragerc` omit list |
| G4 | Bugs found by G2 are fixed in-scope | Any failure in W2 that is not a flaky test becomes a `hotfix(M3.2):` commit with a passing test |
| G5 | Baseline prompt captured | `docs/prompts/baseline_<novel>_vol01_ch001.md` exists with a real captured DeepSeek prompt + metadata (timestamp, novel, vol, ch, total_tokens) + manual review checklist completed |

## Non-Goals (Out of Scope for M3.2)

- **Refactoring `app.py` (3718 lines)** — separate M4 work, same as M3.1 deferral
- **Refactoring `init_config_db.py` deprecation** — separate M4 work
- **Adding new endpoints or features** — M3.2 is quality/verification only
- **Changing the M3 test infrastructure** (`tmp_db`, `client`, `sample_novel` fixtures are stable)
- **Lifting `content_db.py` from coverage omit** — still a "legacy compat shim" per M3.1; not touched
- **Replacing `app.py`'s direct `repository` calls with `ctx_v2`'s volume-scoped wrappers** — would be a behavior change; out of scope
- **Coverage of `agent-system/` or `tests/`** — same as M3.1

## Architecture

**Canonical implementation:** `portal/ctx_v2.py` (366 lines, already the runtime path in production via `run_v2.py:155-158`).

**Demolished modules:**

| Module | Size | Action | Reason |
|--------|------|--------|--------|
| `portal/context_builder.py` | 743 lines | **Delete** | Functionality duplicated in `ctx_v2.py`. Its 12-layer orchestrator is functionally equivalent to `ctx_v2.build_context` (verified by side-by-side read on 2026-06-06). |
| `portal/context_builder_v2.py` | 512 lines | **Delete** | Intermediate alternate. No production caller. Comment header says "drop-in replacement for `context_builder.build_context`" but nothing in the repo uses it. |

**Callers to update:**

| File | Line | Change |
|------|------|--------|
| `portal/run_v2.py` | 155-158 | Delete the 4-line hot-patch block (`_cb._build_context_original = _cb.build_context; _cb.build_context = build_context_v2`). The `from ctx_v2 import build_context as build_context_v2` line on 155 is only used by the hot-patch; delete it too. |
| `portal/app.py` | 1688 | `from context_builder import build_context as _build_ctx` → `from ctx_v2 import build_context as _build_ctx` |
| `portal/app.py` | 2838 | `from context_builder import build_context` → `from ctx_v2 import build_context` |

**Sweep:** `grep -rn "from context_builder import\|import context_builder" portal/ tests/` must return zero matches after W1. If any remain (e.g., a test file imports from it), update those imports too.

**Coverage gate:** `.coveragerc` updates:
- Remove `portal/context_builder.py` and `portal/context_builder_v2.py` from the `omit` list (they don't exist anymore, but the entries would be silently ignored anyway; clean them up for clarity).
- `portal/ctx_v2.py` is **not** added to the omit list — it is measured.

## Workstreams (Execution Order)

M3.2 ships in 5 sequential workstreams. Order chosen so each step has a tight exit gate and bisection is easy.

```
W1 Reconcile v1/v2  ─►  W2 Layer snapshot tests  ─►  W3 Bug fixes  ─►  W4 Coverage lift  ─►  W5 Baseline
  1-2 days              1-2 days                     0-2 days            1 day                0.5 day
─────────────────────  ───────────────────────────  ──────────────────  ───────────────────  ───────────────────
~6-9 days total
```

### W1: Reconcile v1/v2

**Files:**
- Delete: `portal/context_builder.py`, `portal/context_builder_v2.py`
- Modify: `portal/run_v2.py:155-158`
- Modify: `portal/app.py:1688, 2838`
- Modify: `.coveragerc` (cleanup omit list)
- Sweep: any remaining `from context_builder import` in `tests/`, `scripts/`, etc.

**Steps:**

1. `git rm portal/context_builder.py portal/context_builder_v2.py`
2. Edit `portal/run_v2.py:155-158` to delete the 4-line hot-patch block.
3. Edit `portal/app.py:1688` to change the import.
4. Edit `portal/app.py:2838` to change the import.
5. `grep -rn "from context_builder import\|import context_builder" portal/ tests/ scripts/` — if any hits, update them.
6. Edit `.coveragerc` to remove the two deleted-module entries from the `omit` list.
7. Run `pytest tests/ -q` — must pass with 1174 tests (the M3.1 final count). Zero new tests in this workstream.
8. Commit: `refactor(M3.2): delete context_builder.py + context_builder_v2.py; ctx_v2 is canonical`

**Exit gate:**
- `grep -rn "from context_builder" portal/ tests/` → 0 matches
- `pytest tests/ -q` → 1174 passed, 0 failed
- `ls portal/context_builder*.py` → `No such file or directory`

**Risk:** If `ctx_v2.build_context` is *not* behaviorally equivalent to the deleted `context_builder.build_context` (e.g., volume-scoped filtering excludes some layer that the old code included), W2's tests will surface the difference as a bug, addressed in W3.

### W2: Per-layer snapshot tests

**File:** Create `tests/unit/test_context_layers.py`.

**Pattern:** Each test class seeds a `tmp_db` fixture with the layer's input data (a `novels` row + the layer's table rows), calls the layer function (e.g., `_build_genre_rules_context(novel_name)`), and asserts:
- The output is a `str`
- The output contains the seeded data
- The output is under the layer's token budget
- For Layer 1: contains all 14 `project_meta` keys (specific to the spec)
- For Layer 3.5: contains both 🔴 and 🟡 markers
- For Layer 9: contains the `style_presets.prompt` text (not just the style name)

**12 layer test classes:**

| Class | Seeds | Asserts |
|-------|-------|---------|
| `TestLayer0CoreInstructions` | none (jinja2 template) | `core_text` non-empty, contains "写作" or other core-rule markers |
| `TestLayer1ProjectMeta` | novel row + 14 `project_meta` rows | All 14 keys appear, novel title appears, token count ≤ 500 |
| `TestLayer2ChapterContext` | outline + danger_issue + prev chapter | All three sections present in correct order, ≤ 800 tok |
| `TestLayer3Characters` | 4 `characters` rows (3 with all fields, 1 with empty `background` to test fallback) | All 4 names present, field-truncation at 200 chars enforced |
| `TestLayer35GenreRules` | 3 `genre_rules` rows (1 required, 1 optional, 1 in third category) | 🔴 marker on required, 🟡 on optional, group-by-category headers present |
| `TestLayer4Foreshadowing` | 5 `foreshadowing` rows (mix of target_vol=1 and target_vol=2) | Only target_vol ≤ current vol included, ≤ 1000 tok |
| `TestLayer5WorldBuilding` | 6 `world_building` rows (3 in current vol, 3 in later vol) | Local 5 + global 5 logic produces both current-vol and important-setting rows |
| `TestLayer6PacingEmotion` | 3 `pacing_control` rows (matching and non-matching vol/ch) | Only matching rows included, ≤ 500 tok |
| `TestLayer7Revelation` | 4 `revelation_schedule` rows (mix of reveal_vol) | Only reveal_vol ≤ current vol included, ≤ 500 tok |
| `TestLayer8PlotArcs` | 3 `plot_arcs` rows | Vol-range filter applied, ≤ 1000 tok |
| `TestLayer85BannedCompliance` | 5 `banned_words` + 3 `compliance_rules` | All listed in output, ≤ 200 tok |
| `TestLayer9Style` | 1 `style_presets` row with prompt "用简练语言, 多用短句" + `style="测试风格 100%"` | Output contains the prompt text "用简练语言" (not just "测试风格 100%") |

**Integration test (1 class, 1 method):**

```python
class TestBuildContextIntegration:
    def test_full_orchestrator_produces_12_layer_prompt(
        self, client, sample_novel, monkeypatch
    ):
        result = ctx_v2.build_context({...full params...})
        assert result["total_tokens"] <= 10_000
        # All 12 layer names present, in order
        layer_names = [layer["name"] for layer in result["layers"]]
        assert layer_names == [
            "核心指令", "项目元信息", "章节上下文", "角色上下文",
            "类型规则", "伏笔待办", "世界观", "节奏情感", "信息释放",
            "剧情弧线", "禁用词与合规", "写作风格",
        ]
```

**Fixtures:** Reuse the existing `tmp_db` and `sample_novel` fixtures from `tests/functional/conftest.py`. Add layer-specific seed helpers to `tests/unit/test_context_layers.py` (e.g., `_seed_genre_rules(novel_name, rules)`).

**Failure mode:** If any test in this file fails for a reason other than "the layer function does the wrong thing", that's a bug → W3.

**Commit:** `test(M3.2): per-layer snapshot tests for ctx_v2 (12 layers + 1 integration)`

**Exit gate:** `pytest tests/unit/test_context_layers.py -v` → ≥ 13 passed, 0 failed.

### W3: Bug fixes (conditional on W2)

**Trigger:** Any W2 test fails for a correctness reason (not a flaky test, not a fixture issue, not a typo in the test).

- *Flaky test* = fails non-deterministically across re-runs; investigate timing/state, not the implementation.
- *Fixture issue* = the test seeds data incorrectly; fix the test, not `ctx_v2.py`. No `hotfix(M3.2):` commit for fixture issues — amend the W2 commit instead.
- *Typo in the test* = same as fixture issue; fix the test, amend the W2 commit.

Only *correctness* failures become `hotfix(M3.2):` commits.

**Process:** Per bug:
1. Open a `hotfix(M3.2): <description>` commit
2. The test that surfaced the bug is the regression test (already committed in W2)
3. Make minimal change in `portal/ctx_v2.py` (or `portal/content_db.py` if the bug is in a helper)
4. Verify the test now passes
5. Verify the rest of the test suite still passes

**Likely bug candidates (best guesses from 2026-06-02 audit):**

| Candidate | Symptom in test | Likely fix |
|-----------|-----------------|------------|
| P2-2: characters.md fallback never triggered | `TestLayer3Characters::test_empty_background_uses_md_fallback` fails | Fix the conditional in `_build_character_context` to call `_load_character_from_md` when DB fields are empty |
| P2-3: world building local+global logic inverted | `TestLayer5WorldBuilding::test_local_5_plus_global_5` fails | Fix the vol filter: take 5 from current vol + 5 from outside current vol |
| Layer 9: style preset lookup fails on 0% mix | `TestLayer9Style::test_zero_percent_mix_handles_gracefully` fails | Fix the percentage parser to skip zero-percent entries instead of dividing by zero |
| Layer 3.5: genre_rules group ordering wrong | `TestLayer35GenreRules::test_required_before_optional_within_category` fails | Fix the group-then-sort order |

**Commit (per bug):** `hotfix(M3.2): <one-line description>`

**Exit gate:** All W2 tests pass; full suite still green.

### W4: Coverage lift

**Steps:**

1. Run `bash scripts/measure_coverage.sh` and check the report.
2. Confirm `portal/ctx_v2.py` is measured (not in the `omit` list).
3. Check the coverage % on `ctx_v2.py` and `portal/` overall.
4. If `portal/` ≥ 90%, done — go to commit.
5. If `portal/` < 90%:
   a. Look at the missing lines in `ctx_v2.py` (the report has `show_missing = true`).
   b. For each uncovered branch that's a real edge case (not a `pragma: no cover` or a `__main__` guard), add a small test in `tests/unit/test_context_layers.py` or a new `tests/unit/test_ctx_v2_branches.py`.
   c. Re-run gate. If still < 90% after reasonable effort, document the gap in the commit message and ship.

**Commit:** `ci(M3.2): measure ctx_v2.py in coverage gate; add branch tests if needed`

**Exit gate:** `bash scripts/measure_coverage.sh` exits 0 with `TOTAL ... ≥ 90%` line coverage on `portal/`.

### W5: Baseline prompt capture

**Steps:**

1. Pick a representative novel. The repo has at least `yueguang_wenguo` and `webnovel_agent` demo data; use whichever has the richest seed (characters, world_building, style_presets, project_meta, genre_rules). The plan and current code reference `yueguang_wenguo` heavily.
2. Run a small Python snippet to generate the system_prompt for vol-01 ch-001 of that novel:

   ```python
   from ctx_v2 import build_context
   from app import create_app  # if needed for repo setup
   result = build_context({
       "name": "yueguang_wenguo",
       "volume": 1,
       "chapter_num": 1,
       "style": "辰东风 50%, 默认 50%",
       "instructions": "请创作第 1 章",
       "max_tokens": 10_000,
   })
   open("docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md", "w").write(
       f"# Baseline prompt — yueguang_wenguo vol-01 ch-001\n\n"
       f"Captured: 2026-06-06 (M3.2)\n"
       f"Total tokens: {result['total_tokens']}\n"
       f"Layers: {len(result['layers'])}\n\n"
       f"---\n\n"
       f"{result['system_prompt']}"
   )
   ```

3. Manual review (write in commit message body):
   - Does the prompt contain the `style_presets.prompt` text (not just the name)? ✓/✗
   - Does it contain all 14 `project_meta` keys? ✓/✗
   - Does it contain 🔴/🟡 genre rules? ✓/✗
   - Does it contain banned words and compliance rules? ✓/✗
   - Does it contain world building (both current-vol and global)? ✓/✗
   - Is the total under 10,000 tokens? ✓/✗

4. Commit the baseline file: `docs(M3.2): capture baseline DeepSeek prompt for yueguang_wenguo vol-01 ch-001`

**Exit gate:** `docs/prompts/baseline_<novel>_vol01_ch001.md` exists in the repo; commit message contains the manual review checklist.

## Data Flow

```
app.py:1688 api_generate_chapter
   │
   ▼
ctx_v2.build_context(params)        ← canonical, called directly (no hot-patch)
   │
   ├── _get_core_instructions()           Layer 0
   ├── _build_project_meta(name)          Layer 1
   ├── _build_chapter_context(...)        Layer 2
   ├── _build_character_context(...)      Layer 3
   ├── _build_genre_rules_context(...)    Layer 3.5
   ├── _build_foreshadowing_context(...)  Layer 4
   ├── _build_world_context(...)          Layer 5
   ├── _build_pacing_context(...)         Layer 6
   ├── _build_revelation_context(...)     Layer 7
   ├── _build_plot_arc_context(...)       Layer 8
   ├── _build_banned_compliance_context() Layer 8.5
   └── _build_style_context(...)          Layer 9
   │
   ▼
{system_prompt, layers: [...], total_tokens, max_tokens}
```

`build_context` is the **only** entry point. All 12 layer functions are called by it. No other code path constructs the prompt.

## Error Handling

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| W1: `ctx_v2.build_context` is not behaviorally equivalent to the deleted `context_builder.build_context` (e.g., volume-scoped filtering is stricter) | Medium | High | W2's integration test (`TestBuildContextIntegration`) compares the orchestrator's output structure; if it fails, we know there's a behavior diff. The 1174-test suite is the broader regression check. Worst case: revert W1's deletion, keep both, file as M3.3 work. |
| W1: a third-party caller we missed imports `context_builder` | Low | High | The grep sweep (W1 step 5) catches it. If it slips through, the import will fail at runtime and the test suite will catch it. |
| W2: snapshot tests reveal a real bug in `ctx_v2` | High | Medium | W3 fixes in-scope. Each bug is one `hotfix(M3.2):` commit. |
| W2: snapshot tests are too brittle (e.g., depend on exact whitespace) | Medium | Low | Use `in` assertions for substring matching; avoid exact-string equality except where the spec is explicit (e.g., Layer 9 must contain preset.prompt text). |
| W4: coverage drops below 90% after lifting the omit | Medium | Medium | Add targeted branch tests; document any persistent gap. |
| W5: chosen novel doesn't have rich enough seed data | Low | Low | Pick a different novel; or seed additional data in a setup script. |
| `run_v2.py:155-158` hot-patch removal breaks an obscure import path | Low | Medium | The grep sweep + 1174-test gate catches this. If it slips, the 4-line revert is trivial. |

## Testing Strategy

- **W1:** No new tests; existing 1174 tests are the regression gate. `grep` sweep verifies the import path is gone.
- **W2:** ~13 new tests in `tests/unit/test_context_layers.py`. 12 layer classes + 1 integration. Each test class has 1-3 test methods (some layers need happy path + edge case).
- **W3:** Per-bug, 1 regression test (already in W2) + 1 hotfix commit.
- **W4:** Coverage gate (`measure_coverage.sh`) is the test. If < 90%, add branch tests.
- **W5:** Manual review checklist (recorded in commit message). No automated test.

**Final test count target:** 1174 → ~1187 (12 layer test classes × ~1.5 tests avg = ~18 + 1 integration = ~19 new tests). Bug fixes in W3 may add 1-3 more.

**Coverage target:** `portal/` ≥ 90% (gate). `ctx_v2.py` itself should be ≥ 95% given the snapshot tests cover all 12 layers.

**Spec verification:** `verify_spec.py` 5/5 still pass (no endpoint or method count changes).

## File Touchpoint Summary

| File | W1 | W2 | W3 | W4 | W5 |
|------|----|----|----|----|----|
| `portal/context_builder.py` | 🗑️ delete | | | | |
| `portal/context_builder_v2.py` | 🗑️ delete | | | | |
| `portal/run_v2.py` | ✏️ 155-158 | | | | |
| `portal/app.py` | ✏️ 1688, 2838 | | | | |
| `portal/ctx_v2.py` | | | ✏️ (if bugs) | | |
| `portal/content_db.py` | | | ✏️ (if bugs in helpers) | | |
| `tests/unit/test_context_layers.py` (new) | | ✏️ | | ✏️ (if branch tests) | |
| `tests/unit/test_ctx_v2_branches.py` (new, conditional) | | | | ✏️ | |
| `.coveragerc` | ✏️ | | | ✏️ (verify) | |
| `docs/prompts/baseline_<novel>_vol01_ch001.md` (new) | | | | | ✏️ |

**Total:** ~5-10 atomic commits (W1: 1, W2: 1, W3: 0-3, W4: 1, W5: 1), ~4-7 files modified or created, ~19 new tests after completion.

## Commits & Branch

- **Branch:** `main` (incremental quality work, same as M3.1)
- **Commit message style:** Consistent with M1-M3.1:
  - `refactor(M3.2): ...` for W1
  - `test(M3.2): ...` for W2
  - `hotfix(M3.2): ...` for W3 (bypasses TDD physical gate, per the M3 convention)
  - `ci(M3.2): ...` for W4
  - `docs(M3.2): ...` for W5

## Dependencies

- W2 depends on W1 (the snapshot tests target `ctx_v2.build_context`; we need ctx_v2 to be the only call path so the tests are unambiguous).
- W3 depends on W2 (the bugs are surfaced by W2's tests).
- W4 depends on W3 (don't measure coverage while known bugs are unfixed; the bug-fix commits move coverage numbers).
- W5 depends on W4 (the baseline prompt reflects the post-bugfix, post-coverage state; this is the regression baseline going forward).

## Open Questions

None — all clarifications resolved during brainstorming:
- Scope: M3.2 = verify + test + reconcile + bugs + baseline ✓
- Sequencing: W1 → W2 → W3 → W4 → W5 ✓
- Canonical: `ctx_v2.py` ✓
- Bug policy: fix in-scope ✓
- Baseline: capture end-to-end prompt ✓
- Delete vs shim: delete ✓
- Test shape: per-layer + integration ✓
