# M3.2 — Prompt Verify + v1/v2 Reconcile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `context_builder.py` the canonical runtime path (currently dead code via `run_v2.py:155-158` hot-patch), add per-layer snapshot tests, lift coverage gate, fix any bugs the tests find, and capture a baseline prompt for future regression detection.

**Architecture:** Delete `ctx_v2.py` (366 lines, the Volume-Scoped rewrite that hot-patches in front of the plan) and `context_builder_v2.py` (512 lines, unused alternate). Remove the `run_v2.py:155-158` hot-patch so `app.py`'s `from context_builder import build_context` calls the 12-layer plan implementation. Add per-layer snapshot tests against `context_builder.py`'s layer functions. Lift the coverage gate (currently `context_builder.py` is in `.coveragerc` omit).

**Tech Stack:** Python 3.9, Flask, pytest, pytest-cov, SQLAlchemy, jinja2, pydantic. The 12-layer orchestrator already in `context_builder.py` uses `repository.get_repo()` for data access, `TokenBudget` for token accounting, and `prompt_manager.get_prompt_manager().render_or_default("core_instructions", ...)` for the jinja2 Layer 0.

---

## File Structure

**Delete:**
- `portal/ctx_v2.py` (366 lines, the Volume-Scoped alternate)
- `portal/context_builder_v2.py` (512 lines, the unused alternate)

**Modify:**
- `portal/run_v2.py` (lines 155-158: remove hot-patch + the import on 155)
- `.coveragerc` (remove `context_builder.py`, `ctx_v2.py`, `context_builder_v2.py` from `omit`)

**Create:**
- `tests/unit/test_context_layers.py` — 12 per-layer test classes + 1 integration test (~600-800 lines)
- `tests/unit/test_context_builder_branches.py` — branch tests for `context_builder.py`, conditional on W4
- `docs/prompts/baseline_<novel>_vol01_ch001.md` — captured DeepSeek prompt (W5)

**Unchanged (canonical):**
- `portal/context_builder.py` (743 lines) — the 12-layer plan; runtime path after W1

---

## Task Index

**Phase 1 — W1: Reconcile v1/v2** (T1.1–T1.4)
- T1.1: Remove the hot-patch in `run_v2.py`
- T1.2: Delete `ctx_v2.py` and `context_builder_v2.py`
- T1.3: Update `.coveragerc`
- T1.4: Verify the 1174-test gate is green

**Phase 2 — W2: Per-layer snapshot tests** (T2.1–T2.13, TDD-shaped)
- T2.1: Layer 0 — Core Instructions
- T2.2: Layer 1 — Project Meta (14 keys)
- T2.3: Layer 2 — Chapter Context
- T2.4: Layer 3 — Characters
- T2.5: Layer 3.5 — Genre Rules
- T2.6: Layer 4 — Foreshadowing
- T2.7: Layer 5 — World Building
- T2.8: Layer 6 — Pacing/Emotion
- T2.9: Layer 7 — Revelation
- T2.10: Layer 8 — Plot Arcs
- T2.11: Layer 8.5 — Banned + Compliance
- T2.12: Layer 9 — Style (preset.prompt + style.md + JSON fingerprint)
- T2.13: Integration test (full 12-layer orchestrator)

**Phase 3 — W3: Bug fixes** (T3.1+ — only if W2 surfaces correctness bugs)

**Phase 4 — W4: Coverage lift** (T4.1–T4.2)

**Phase 5 — W5: Baseline prompt capture** (T5.1–T5.2)

---

## Phase 1 — W1: Reconcile v1/v2

### Task 1.1: Remove the hot-patch in `run_v2.py`

**Files:**
- Modify: `portal/run_v2.py:155-158`

The hot-patch overrides `context_builder.build_context` with `ctx_v2.build_context` at import time, which is why the plan's implementation never runs in production. Removing it is the core of W1.

- [ ] **Step 1: Read the hot-patch block in `portal/run_v2.py:155-158`**

```bash
sed -n '150,165p' portal/run_v2.py
```

Expected output (something like):
```python
# ctx_v2 hot-patch: route context_builder.build_context to the
# volume-scoped implementation
from ctx_v2 import build_context as build_context_v2
import context_builder as _cb
_cb._build_context_original = _cb.build_context
_cb.build_context = build_context_v2
```

- [ ] **Step 2: Delete the hot-patch block AND the `from ctx_v2 import` line above it**

Open `portal/run_v2.py` and remove the entire hot-patch block (the 4 lines that touch `_cb.build_context` plus the `from ctx_v2 import build_context as build_context_v2` line if it exists separately). Keep all other imports and code in the file intact. The final result should not reference `ctx_v2` anywhere in `run_v2.py`.

- [ ] **Step 3: Verify `ctx_v2` is no longer imported in `run_v2.py`**

```bash
grep -n "ctx_v2" portal/run_v2.py
```

Expected: no output (0 matches).

- [ ] **Step 4: Commit**

```bash
git add portal/run_v2.py
git commit -m "refactor(M3.2): remove ctx_v2 hot-patch in run_v2.py"
```

### Task 1.2: Delete `ctx_v2.py` and `context_builder_v2.py`

**Files:**
- Delete: `portal/ctx_v2.py`
- Delete: `portal/context_builder_v2.py`

- [ ] **Step 1: Confirm no remaining references to `ctx_v2` or `context_builder_v2` in `portal/`**

```bash
grep -rn "ctx_v2\|context_builder_v2" portal/ --include="*.py"
```

Expected: no output. If there are hits, they need to be updated in this task (e.g., a stray import).

- [ ] **Step 2: Delete the two files**

```bash
git rm portal/ctx_v2.py portal/context_builder_v2.py
```

Expected: both files removed. `git status` shows "deleted: portal/ctx_v2.py" and "deleted: portal/context_builder_v2.py".

- [ ] **Step 3: Verify `context_builder.py` is still present**

```bash
ls -la portal/context_builder.py
```

Expected: file exists, ~743 lines (`wc -l portal/context_builder.py` reports 743).

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(M3.2): delete ctx_v2.py and context_builder_v2.py (no longer used)"
```

### Task 1.3: Update `.coveragerc`

**Files:**
- Modify: `.coveragerc`

`context_builder.py` was in the omit list (M3.1 commit `c818113`). It is now the canonical runtime path, so it must be measured. The deleted `ctx_v2.py` and `context_builder_v2.py` entries should be cleaned up.

- [ ] **Step 1: Read current `.coveragerc`**

```bash
cat .coveragerc
```

- [ ] **Step 2: Edit `.coveragerc` to remove the three module entries**

Open `.coveragerc` and in the `[run] omit` list, remove these three lines:

```ini
    # Excluded by M3.1 spec §W2 'Excluded modules (justified)':
    #   app.py: route handlers — covered by 4-dim functional tests in W3
    #   context_builder.py: covered by 4-dim functional tests in W3
    #   content_db.py: legacy compat shim to repository (delegates only)
    portal/app.py
    portal/context_builder.py
    portal/content_db.py
```

Replace with:

```ini
    # Excluded modules (justified):
    #   app.py: route handlers — covered by 4-dim functional tests in M3.1 W3
    #   content_db.py: legacy compat shim to repository (delegates only)
    portal/app.py
    portal/content_db.py
```

(`context_builder.py` is removed from the omit list — it will now be measured. The other comments stay; the `ctx_v2.py` and `context_builder_v2.py` lines from before are not in the file per the M3.1 spec, but verify with the cat in Step 1.)

- [ ] **Step 3: Verify the omit list is what we expect**

```bash
cat .coveragerc
```

Expected: the `omit` list contains `portal/init_config_db.py`, `portal/logging_config.py`, `portal/errors.py`, `portal/app.py`, `portal/content_db.py`. `portal/context_builder.py` is **not** in the list.

- [ ] **Step 4: Commit**

```bash
git add .coveragerc
git commit -m "ci(M3.2): remove context_builder.py from .coveragerc omit (now canonical)"
```

### Task 1.4: Verify the 1174-test gate is green

**No file changes.** This is the exit gate for W1. The runtime now uses `context_builder.build_context` (12 layers) instead of `ctx_v2.build_context` (11 layers). The 1174 existing tests are the regression check.

- [ ] **Step 1: Run the full test suite**

```bash
bash scripts/measure_coverage.sh 2>&1 | tail -50
```

Expected: all tests pass (the M3.1 final count was 1174). The coverage report may show a different TOTAL now that `context_builder.py` is measured — that's expected; W4 will address it.

If any test fails:
1. Read the failure. If it's a behavioral diff between `context_builder.build_context` and `ctx_v2.build_context` (e.g., a test that depends on a specific prompt structure), the W2 snapshot tests will document the canonical behavior; for now, the test is the regression. **Do not modify the test** unless the failure is clearly a test bug.
2. If the failure is a hard import error (e.g., a test file still imports from `ctx_v2`), fix the import and re-run.

- [ ] **Step 2: Verify W1 exit gate**

```bash
grep -rn "ctx_v2" portal/ tests/ 2>/dev/null
```

Expected: no output.

```bash
ls portal/ctx_v2.py portal/context_builder_v2.py 2>&1
```

Expected: `No such file or directory` (2 files listed as missing).

- [ ] **Step 3: Commit (only if Step 1 required test fixes)**

```bash
git add -A
git commit -m "test(M3.2): update imports after ctx_v2 deletion (W1 follow-up)"
```

Skip this commit if no test changes were needed.

---

## Phase 2 — W2: Per-layer snapshot tests

The 12 layer test classes follow the same TDD pattern. Each task writes the test (asserting current/expected behavior), runs it, then either:
- (a) Test passes on the existing implementation — fine, the implementation is correct, move on.
- (b) Test fails because the implementation is buggy — that's a W3 bug fix; add a `# FIXME: surfaced by T2.N; will be fixed in W3` comment in the test and continue. The test stays as the regression test.

The 12 layer functions live in `portal/context_builder.py` and use `repository.get_repo()` for data. Each test seeds the relevant DB rows via the `tmp_db` fixture (defined in `tests/functional/conftest.py`) and calls the layer function directly.

For the integration test (T2.13), we call `context_builder.build_context()` (the orchestrator) with full params and assert the layered output structure.

### Task 2.1: Layer 0 — Core Instructions

**Files:**
- Create: `tests/unit/test_context_layers.py` (initial scaffold + Layer 0 class)

- [ ] **Step 1: Create the test file with the Layer 0 class**

```python
"""Per-layer snapshot tests for context_builder (M3.2 W2).

Each test class seeds the relevant DB tables via the ``tmp_db`` fixture
(defined in ``tests/functional/conftest.py``) and calls the corresponding
layer function in ``portal/context_builder.py``. Substring/contains
assertions are preferred over exact-string equality to avoid brittleness.

The integration test (TestBuildContextIntegration) at the bottom of this
file calls the full ``build_context`` orchestrator and asserts the 12
layers appear in the correct order with the correct token accounting.
"""
import pytest


class TestLayer0CoreInstructions:
    """Layer 0: Core Instructions (jinja2 template, fallback default)."""

    def test_core_instructions_renders_non_empty(self):
        from context_builder import _get_core_instructions
        text = _get_core_instructions()
        assert isinstance(text, str)
        assert len(text) > 50
        # The fallback default contains these markers
        assert "写作" in text or "章节" in text

    def test_core_instructions_under_token_budget(self):
        from context_builder import _get_core_instructions
        from context_builder import _count_tokens
        text = _get_core_instructions()
        # Layer 0 budget is 500 tokens per the orchestrator
        assert _count_tokens(text) <= 500
```

- [ ] **Step 2: Run the test to verify it passes**

```bash
pytest tests/unit/test_context_layers.py::TestLayer0CoreInstructions -v
```

Expected: 2 tests pass. If any test fails, that's a real bug in the layer (W3). Add a FIXME comment in the test and continue.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 0 (core instructions) snapshot test"
```

### Task 2.2: Layer 1 — Project Meta (14 keys)

**Files:**
- Modify: `tests/unit/test_context_layers.py` (append `TestLayer1ProjectMeta` class)

- [ ] **Step 1: Append the Layer 1 test class**

```python
class TestLayer1ProjectMeta:
    """Layer 1: Project Meta (novel row + all 14 project_meta keys).

    This is the M3.1 P1-3 fix: the layer must load the full project_meta
    table, not just the 3 fields on the novel row.
    """

    @pytest.fixture
    def seeded_novel_with_14_keys(self, tmp_db):
        """Seed a novel row + 14 project_meta rows for test_novel."""
        from repository import get_repo
        repo = get_repo()
        # Insert novel row
        repo.upsert_novel({
            "name": "test_novel",
            "title": "测试小说",
            "genre": "玄幻",
            "word_goal": 1_000_000,
        })
        # Insert 14 project_meta key/value pairs
        keys = [
            ("world_core", "诸神黄昏后的废土世界"),
            ("magic_system", "元素亲和 + 血脉觉醒"),
            ("main_conflict", "神族遗民 vs 新生帝国"),
            ("tone", "史诗 + 暗黑 + 成长"),
            ("pov", "第三人称限制"),
            ("tense", "过去时"),
            ("protagonist_name", "林渊"),
            ("protagonist_archetype", "废柴逆袭"),
            ("love_interest", "苏晴"),
            ("antagonist", "魔皇残魂"),
            ("theme", "命运 vs 自由意志"),
            ("target_audience", "男频玄幻读者"),
            ("chapter_word_count_target", "3000"),
            ("update_frequency", "日更"),
        ]
        for k, v in keys:
            repo.upsert_project_meta("test_novel", k, v)
        return "test_novel"

    def test_all_14_keys_appear_in_output(self, seeded_novel_with_14_keys):
        from context_builder import _build_project_meta
        from context_builder import _count_tokens
        text = _build_project_meta("test_novel")
        for k, v in [
            ("world_core", "诸神黄昏"),
            ("magic_system", "元素亲和"),
            ("main_conflict", "神族遗民"),
            ("protagonist_name", "林渊"),
            ("antagonist", "魔皇残魂"),
            ("theme", "命运"),
        ]:
            assert k in text, f"missing key {k} in layer 1"
            assert v in text, f"missing value for {k} in layer 1"
        # Token budget check (Layer 1 = 500)
        assert _count_tokens(text) <= 500

    def test_novel_title_appears(self, seeded_novel_with_14_keys):
        from context_builder import _build_project_meta
        text = _build_project_meta("test_novel")
        assert "测试小说" in text
        assert "玄幻" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer1ProjectMeta -v
```

Expected: 2 tests pass. If a test fails (e.g., `_build_project_meta` doesn't load all 14 keys, or the function signature is different), it's a W3 bug. Add FIXME and continue.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 1 (project meta 14 keys) snapshot test"
```

### Task 2.3: Layer 2 — Chapter Context

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 2 test class**

```python
class TestLayer2ChapterContext:
    """Layer 2: Chapter context (outline + danger_issue + prev chapter)."""

    @pytest.fixture
    def seeded_novel(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        # Outline for vol-01
        repo.upsert_outline("test_novel", "vol-01", {
            "content": "第001章 觉醒\n本章主角觉醒血脉。\n第002章 试炼\n本章进入试炼之地。",
        })
        # Danger issue
        repo.upsert_danger_issue("test_novel", "vol-01", 1, {"content": "血脉觉醒的代价"})
        # Previous chapter
        repo.upsert_chapter("test_novel", "vol-01", 0, {
            "content": "上一章末尾：林渊在山巅独坐，望着远方的神山，心中百感交集。",
        })
        return "test_novel"

    def test_outline_section_appears(self, seeded_novel):
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 1)
        assert isinstance(text, str)
        # The outline for chapter 1 should be in the text
        assert "觉醒" in text

    def test_danger_issue_appears(self, seeded_novel):
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 1)
        assert "血脉觉醒的代价" in text or "danger" in text.lower() or "危机" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer2ChapterContext -v
```

Expected: 2 tests pass. If `repo.upsert_danger_issue` doesn't exist, use the actual repository method name (check `portal/repository.py` for the right method). Adapt the test.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 2 (chapter context) snapshot test"
```

### Task 2.4: Layer 3 — Characters

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 3 test class**

```python
class TestLayer3Characters:
    """Layer 3: Characters (volume-scoped via current_vol)."""

    @pytest.fixture
    def seeded_novel_with_chars(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        # Active in vol 1
        repo.upsert_character("test_novel", {
            "name": "林渊",
            "role": "主角",
            "identity": "废柴少年，意外觉醒血脉",
            "personality": "坚韧、内敛",
            "current_status": "正在觉醒",
            "emotional_state": "迷茫",
            "current_vol": 1,
            "current_ch": 1,
        })
        # Active in vol 2 (should be excluded from vol-1 prompt)
        repo.upsert_character("test_novel", {
            "name": "苏晴",
            "role": "女主",
            "identity": "帝国公主",
            "current_vol": 2,
            "current_ch": 1,
        })
        return "test_novel"

    def test_active_char_appears(self, seeded_novel_with_chars):
        from context_builder import _build_character_context
        text = _build_character_context("test_novel", 1, 1)
        assert "林渊" in text
        assert "废柴少年" in text

    def test_future_vol_char_excluded(self, seeded_novel_with_chars):
        from context_builder import _build_character_context
        text = _build_character_context("test_novel", 1, 1)
        # 苏晴 is in vol 2; should NOT appear in vol-1 prompt
        assert "苏晴" not in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer3Characters -v
```

Expected: 2 tests pass. If `_build_character_context` doesn't filter by volume, that's a W3 bug. Add FIXME and continue.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 3 (characters, volume-scoped) snapshot test"
```

### Task 2.5: Layer 3.5 — Genre Rules

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 3.5 test class**

```python
class TestLayer35GenreRules:
    """Layer 3.5: Genre rules (must/optional markers, grouped by category)."""

    @pytest.fixture
    def seeded_novel_with_genre_rules(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        repo.upsert_genre_rule("test_novel", {
            "rule_key": "magic_required",
            "rule_value": "每章必须有至少1次血脉能力使用",
            "rule_category": "必须元素",
            "is_required": True,
        })
        repo.upsert_genre_rule("test_novel", {
            "rule_key": "dialogue_ratio",
            "rule_value": "对话占比 20-30%",
            "rule_category": "节奏规则",
            "is_required": False,
        })
        return "test_novel"

    def test_required_marker_appears(self, seeded_novel_with_genre_rules):
        from context_builder import _build_genre_rules_context
        text = _build_genre_rules_context("test_novel")
        assert "🔴" in text or "必须" in text

    def test_optional_marker_appears(self, seeded_novel_with_genre_rules):
        from context_builder import _build_genre_rules_context
        text = _build_genre_rules_context("test_novel")
        assert "🟡" in text or "可选" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer35GenreRules -v
```

Expected: 2 tests pass. If `repo.upsert_genre_rule` doesn't exist or the layer function uses a different method, adapt.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 3.5 (genre rules) snapshot test"
```

### Task 2.6: Layer 4 — Foreshadowing

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 4 test class**

```python
class TestLayer4Foreshadowing:
    """Layer 4: Foreshadowing (filtered by target_vol <= current)."""

    @pytest.fixture
    def seeded_novel_with_foreshadowing(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        # Due now
        repo.upsert_foreshadowing("test_novel", {
            "name": "神山之谜",
            "description": "神山为何封印八位古神",
            "target_vol": 1,
            "introduced_vol": 1,
        })
        # Future vol (should be excluded from vol-1 prompt)
        repo.upsert_foreshadowing("test_novel", {
            "name": "叛神者身份",
            "description": "主角是叛神者后裔",
            "target_vol": 3,
            "introduced_vol": 1,
        })
        return "test_novel"

    def test_due_now_foreshadowing_appears(self, seeded_novel_with_foreshadowing):
        from context_builder import _build_foreshadowing_context
        text = _build_foreshadowing_context("test_novel", 1)
        assert "神山之谜" in text

    def test_future_foreshadowing_excluded(self, seeded_novel_with_foreshadowing):
        from context_builder import _build_foreshadowing_context
        text = _build_foreshadowing_context("test_novel", 1)
        assert "叛神者身份" not in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer4Foreshadowing -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 4 (foreshadowing, vol-filtered) snapshot test"
```

### Task 2.7: Layer 5 — World Building

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 5 test class**

```python
class TestLayer5WorldBuilding:
    """Layer 5: World building (local 5 + global 5 per P2-3)."""

    @pytest.fixture
    def seeded_novel_with_world(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        # Local (current vol)
        for i in range(3):
            repo.upsert_world_building("test_novel", {
                "domain": "地理",
                "name": f"第1卷地点{i}",
                "content": f"第1卷专属地点{i}的描述",
                "current_vol": 1,
            })
        # Global (later vol, important settings)
        repo.upsert_world_building("test_novel", {
            "domain": "体系",
            "name": "八神体系",
            "content": "世界观的八位古神设定",
            "current_vol": 0,  # global
        })
        return "test_novel"

    def test_local_world_appears(self, seeded_novel_with_world):
        from context_builder import _build_world_context
        text = _build_world_context("test_novel", 1, 1)
        assert "第1卷地点" in text

    def test_global_world_appears(self, seeded_novel_with_world):
        from context_builder import _build_world_context
        text = _build_world_context("test_novel", 1, 1)
        assert "八神体系" in text or "八位古神" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer5WorldBuilding -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 5 (world building, local+global) snapshot test"
```

### Task 2.8: Layer 6 — Pacing/Emotion

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 6 test class**

```python
class TestLayer6PacingEmotion:
    """Layer 6: Pacing/Emotion (filtered by vol/ch)."""

    @pytest.fixture
    def seeded_novel_with_pacing(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        repo.upsert_pacing("test_novel", {
            "volume": 1,
            "chapter_start": 1,
            "chapter_end": 5,
            "pace_type": "快节奏",
            "intensity": 8,
            "emotion_target": "紧张",
            "word_budget_min": 2800,
            "word_budget_max": 3200,
        })
        return "test_novel"

    def test_pacing_appears(self, seeded_novel_with_pacing):
        from context_builder import _build_pacing_context
        text = _build_pacing_context("test_novel", 1, 1)
        assert "快节奏" in text or "紧张" in text
        assert "2800" in text or "3200" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer6PacingEmotion -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 6 (pacing/emotion) snapshot test"
```

### Task 2.9: Layer 7 — Revelation

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 7 test class**

```python
class TestLayer7Revelation:
    """Layer 7: Revelation (filtered by reveal_vol <= current)."""

    @pytest.fixture
    def seeded_novel_with_revelation(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        repo.upsert_revelation("test_novel", {
            "name": "主角血脉来源",
            "content": "主角是叛神者后裔",
            "reveal_vol": 1,
            "info_type": "身份",
        })
        repo.upsert_revelation("test_novel", {
            "name": "魔皇残魂真相",
            "content": "魔皇是八神之一",
            "reveal_vol": 3,  # future
            "info_type": "真相",
        })
        return "test_novel"

    def test_current_vol_revelation_appears(self, seeded_novel_with_revelation):
        from context_builder import _build_revelation_context
        text = _build_revelation_context("test_novel", 1)
        assert "主角血脉来源" in text

    def test_future_revelation_excluded(self, seeded_novel_with_revelation):
        from context_builder import _build_revelation_context
        text = _build_revelation_context("test_novel", 1)
        assert "魔皇残魂" not in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer7Revelation -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 7 (revelation, vol-filtered) snapshot test"
```

### Task 2.10: Layer 8 — Plot Arcs

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 8 test class**

```python
class TestLayer8PlotArcs:
    """Layer 8: Plot arcs (filtered by vol range)."""

    @pytest.fixture
    def seeded_novel_with_arcs(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        repo.upsert_plot_arc("test_novel", {
            "name": "觉醒弧",
            "type": "成长",
            "summary": "主角从废柴到觉醒",
            "start_vol": 1,
            "end_vol": 2,
        })
        return "test_novel"

    def test_arc_appears(self, seeded_novel_with_arcs):
        from context_builder import _build_plot_arc_context
        text = _build_plot_arc_context("test_novel", 1)
        assert "觉醒弧" in text
        assert "成长" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer8PlotArcs -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 8 (plot arcs) snapshot test"
```

### Task 2.11: Layer 8.5 — Banned + Compliance

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 8.5 test class**

```python
class TestLayer85BannedCompliance:
    """Layer 8.5: Banned words + compliance rules (config DB)."""

    @pytest.fixture
    def seeded_banned_and_compliance(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        for word, cat in [("违禁词1", "政治"), ("违禁词2", "色情")]:
            repo.upsert_banned_word({"word": word, "category": cat, "severity": "high"})
        repo.upsert_compliance_rule({
            "rule_key": "max_chapter_words",
            "rule_value": "5000",
            "description": "单章不超过 5000 字",
        })
        return "test_novel"

    def test_banned_words_appear(self, seeded_banned_and_compliance):
        from context_builder import _build_banned_compliance_context
        text = _build_banned_compliance_context()
        assert "违禁词1" in text or "违禁词" in text

    def test_compliance_rule_appears(self, seeded_banned_and_compliance):
        from context_builder import _build_banned_compliance_context
        text = _build_banned_compliance_context()
        assert "5000" in text or "max_chapter_words" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer85BannedCompliance -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 8.5 (banned + compliance) snapshot test"
```

### Task 2.12: Layer 9 — Style

**Files:**
- Modify: `tests/unit/test_context_layers.py`

- [ ] **Step 1: Append the Layer 9 test class**

```python
class TestLayer9Style:
    """Layer 9: Style (preset.prompt + style.md + JSON fingerprint).

    This is the P0-1 / P0-2 / P2-1 fix: the layer must load the actual
    style_presets.prompt content, not just the style name. The P2-1
    distilled JSON fingerprint is also appended.
    """

    @pytest.fixture
    def seeded_style_preset(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        repo.upsert_style_preset({
            "name": "测试风格",
            "prompt": "用简练语言, 多用短句, 节奏快",
            "description": "测试用风格预设",
        })
        return "test_novel"

    def test_preset_prompt_appears(self, seeded_style_preset):
        from context_builder import _build_style_context
        text = _build_style_context("测试风格 100%", "", "test_novel")
        # The layer must load preset.prompt, not just the name
        assert "简练语言" in text or "节奏快" in text

    def test_style_name_appears(self, seeded_style_preset):
        from context_builder import _build_style_context
        text = _build_style_context("测试风格 100%", "", "test_novel")
        assert "测试风格" in text
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/unit/test_context_layers.py::TestLayer9Style -v
```

Expected: 2 tests pass. **This is the P0-1 critical test** — if "简练语言" is not in the output, that's the core bug the audit was meant to fix, and the implementation is broken. Mark as W3 bug.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): Layer 9 (style preset.prompt + style.md) snapshot test"
```

### Task 2.13: Integration test — full 12-layer orchestrator

**Files:**
- Modify: `tests/unit/test_context_layers.py` (append integration class)

- [ ] **Step 1: Append the integration test class**

```python
class TestBuildContextIntegration:
    """Integration: full build_context orchestrator produces 12 layers."""

    @pytest.fixture
    def fully_seeded_novel(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel({"name": "test_novel", "title": "测试", "genre": "玄幻", "word_goal": 1000})
        # Minimal seeding for a passing run
        repo.upsert_outline("test_novel", "vol-01", {"content": "第001章\n本章测试。"})
        repo.upsert_style_preset({
            "name": "默认",
            "prompt": "标准网文风格",
        })
        return "test_novel"

    def test_orchestrator_returns_12_layers(self, fully_seeded_novel):
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "默认 100%",
            "instructions": "请创作第 1 章",
            "max_tokens": 10_000,
        })
        assert "system_prompt" in result
        assert "layers" in result
        assert "total_tokens" in result
        layer_names = [layer["name"] for layer in result["layers"]]
        assert layer_names == [
            "核心指令", "项目元信息", "章节上下文", "角色上下文",
            "类型规则", "伏笔待办", "世界观", "节奏情感", "信息释放",
            "剧情弧线", "禁用词与合规", "写作风格",
        ], f"layer names/order mismatch: {layer_names}"

    def test_orchestrator_respects_token_budget(self, fully_seeded_novel):
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "默认 100%",
            "instructions": "请创作第 1 章",
            "max_tokens": 10_000,
        })
        assert result["total_tokens"] <= 10_000
```

- [ ] **Step 2: Run the integration test**

```bash
pytest tests/unit/test_context_layers.py::TestBuildContextIntegration -v
```

Expected: 2 tests pass. If the layer order is different, check the actual order in `context_builder.py:118-190` and update the assertion (the orchestrator is the source of truth).

- [ ] **Step 3: Run the full test file**

```bash
pytest tests/unit/test_context_layers.py -v
```

Expected: ≥ 26 tests pass (12 layer classes × ~2 tests avg + 2 integration tests).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_context_layers.py
git commit -m "test(M3.2): integration test (12-layer orchestrator) + W2 complete"
```

---

## Phase 3 — W3: Bug fixes (conditional)

**Only execute this phase if T2.1–T2.13 surfaced a correctness bug.** Read the W2 test output and identify failures. Per the spec, only *correctness* failures become `hotfix(M3.2):` commits; *fixture* or *typo* issues amend the W2 commit.

If no W2 tests failed, **skip to Phase 4**.

### Task 3.1: Fix bug surfaced by Layer N

**Pattern (replace N with the layer number):**

- [ ] **Step 1: Read the failing test and identify the root cause**

```bash
pytest tests/unit/test_context_layers.py::TestLayerN -v
```

Read the assertion message. Determine if it's:
- A *correctness* bug in `portal/context_builder.py` → continue with this task
- A *fixture* issue (wrong test data) → amend T2.N, no hotfix needed
- A *typo* in the test → amend T2.N, no hotfix needed

- [ ] **Step 2: Make the minimal fix in `portal/context_builder.py`**

For example, if the bug is that `_build_style_context` doesn't call `repo.get_style_preset_by_name()`:

```python
# In portal/context_builder.py around line 622
# BEFORE (bug):
parts.append(f"## 写作风格\n风格：{style}\n")
# AFTER (fix):
preset = repo.get_style_preset_by_name(name) if name else None
if preset:
    parts.append(f"## 写作风格预设\n{preset.get('prompt', '')}\n")
```

- [ ] **Step 3: Run the W2 test to verify the fix**

```bash
pytest tests/unit/test_context_layers.py::TestLayerN -v
```

Expected: PASS.

- [ ] **Step 4: Run the full W2 test file to verify no regressions**

```bash
pytest tests/unit/test_context_layers.py -v
```

Expected: all W2 tests pass.

- [ ] **Step 5: Commit with hotfix prefix**

```bash
git add portal/context_builder.py tests/unit/test_context_layers.py
git commit -m "hotfix(M3.2): <one-line description of the fix>"
```

### Task 3.2: Fix bug surfaced by Layer M (if any)

Repeat Task 3.1 for each additional bug. One `hotfix(M3.2):` commit per bug.

---

## Phase 4 — W4: Coverage lift

### Task 4.1: Run the coverage gate and check the report

**No file changes.** This task verifies the gate passes now that `context_builder.py` is measured.

- [ ] **Step 1: Run the gate**

```bash
bash scripts/measure_coverage.sh
```

Expected: gate exits 0 with `TOTAL ... ≥ 90%` line coverage on `portal/`. The report shows `context_builder.py` with a coverage number (not 0% and not in the omit list).

- [ ] **Step 2: If the gate fails (< 90%), proceed to T4.2; otherwise skip to Phase 5**

Look at the `TOTAL` line in the output. If ≥ 90%, this task is complete; commit nothing.

### Task 4.2: Add branch tests for uncovered lines (conditional)

**Only execute if T4.1 reports < 90% on `portal/`.**

**Files:**
- Create: `tests/unit/test_context_builder_branches.py` (or extend `test_context_layers.py`)

- [ ] **Step 1: Identify uncovered lines in `context_builder.py`**

```bash
bash scripts/measure_coverage.sh 2>&1 | grep -A 200 "context_builder.py" | head -100
```

Look for the `>>>` markers indicating missing lines. Group them by branch (e.g., empty-novel fallback, token-overflow path, jinja2-missing fallback).

- [ ] **Step 2: For each uncovered branch, add a test**

Example pattern:

```python
class TestContextBuilderBranches:
    def test_build_context_handles_missing_novel(self, tmp_db, monkeypatch):
        from context_builder import build_context
        # No novel seeded; should return empty prompt, not crash
        result = build_context({
            "name": "no_such_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        assert "system_prompt" in result
```

Adapt the test to the specific uncovered branch. Common cases:
- Empty novel name
- max_tokens = 0
- style with no preset match
- jinja2 template missing → fallback default

- [ ] **Step 3: Re-run the gate**

```bash
bash scripts/measure_coverage.sh
```

Expected: `TOTAL ... ≥ 90%` line coverage on `portal/`. If still < 90%, document the remaining gap in the commit message and ship.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_context_builder_branches.py tests/unit/test_context_layers.py
git commit -m "ci(M3.2): measure context_builder.py in coverage gate; add branch tests"
```

---

## Phase 5 — W5: Baseline prompt capture

### Task 5.1: Generate the baseline prompt

**Files:**
- Create: `scripts/capture_baseline_prompt.py` (helper script)
- Create: `docs/prompts/baseline_<novel>_vol01_ch001.md` (the captured output)

- [ ] **Step 1: Pick a representative novel**

```bash
ls novels/ 2>/dev/null | head -10
```

Pick `yueguang_wenguo` (or `webnovel_agent`) — whichever has the richest seeded data (characters, world_building, style_presets, project_meta, genre_rules). The audit and code reference `yueguang_wenguo` heavily, so prefer it.

If neither novel has rich enough seed data, seed a temporary one for the capture:

```python
# In a Python REPL
from repository import get_repo
repo = get_repo()
repo.upsert_novel({"name": "yueguang_wenguo", "title": "...", "genre": "...", "word_goal": ...})
# Seed at least: 5 project_meta, 3 characters, 3 world_building, 1 style_preset
```

- [ ] **Step 2: Write the capture script**

Create `scripts/capture_baseline_prompt.py`:

```python
"""Capture the baseline DeepSeek system prompt for a known novel × chapter.

Used by M3.2 W5 to establish a regression baseline for prompt-quality
changes. Run from the project root:

    python scripts/capture_baseline_prompt.py

The output is written to docs/prompts/baseline_<novel>_vol01_ch001.md
with a metadata header and the full system_prompt as the body.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "portal"))

from context_builder import build_context
from datetime import datetime

NOVEL = "yueguang_wenguo"
VOLUME = 1
CHAPTER_NUM = 1
STYLE = "辰东风 50%, 默认 50%"
INSTRUCTIONS = "请创作第 1 章"
MAX_TOKENS = 10_000


def main():
    result = build_context({
        "name": NOVEL,
        "volume": VOLUME,
        "chapter_num": CHAPTER_NUM,
        "style": STYLE,
        "instructions": INSTRUCTIONS,
        "max_tokens": MAX_TOKENS,
    })

    out_path = os.path.join(
        os.path.dirname(__file__), "..",
        "docs", "prompts",
        f"baseline_{NOVEL}_vol{VOLUME:02d}_ch{CHAPTER_NUM:03d}.md",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    layer_summary = "\n".join(
        f"- {layer['name']}: {layer['tokens_used']} tokens"
        for layer in result["layers"]
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Baseline prompt — {NOVEL} vol-{VOLUME:02d} ch-{CHAPTER_NUM:03d}\n\n")
        f.write(f"**Captured:** {datetime.now().strftime('%Y-%m-%d')} (M3.2 W5)\n")
        f.write(f"**Total tokens:** {result['total_tokens']}\n")
        f.write(f"**Max tokens:** {result['max_tokens']}\n")
        f.write(f"**Layers:** {len(result['layers'])}\n\n")
        f.write(f"## Layer breakdown\n\n{layer_summary}\n\n")
        f.write("---\n\n")
        f.write("## System prompt\n\n")
        f.write("```\n")
        f.write(result["system_prompt"])
        f.write("\n```\n")

    print(f"Baseline prompt written to {out_path}")
    print(f"  Total tokens: {result['total_tokens']}")
    print(f"  Layers: {len(result['layers'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

```bash
python scripts/capture_baseline_prompt.py
```

Expected: a message like `Baseline prompt written to ../docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md` with `Total tokens: <N>` and `Layers: 12`.

If the script fails (e.g., the novel doesn't exist in the DB), either:
- Use the seeded `test_novel` (change `NOVEL = "test_novel"` in the script and re-run)
- Seed `yueguang_wenguo` first (per Step 1's seed snippet)

- [ ] **Step 4: Verify the output file**

```bash
ls -la docs/prompts/
head -30 docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md
wc -l docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md
```

Expected: file exists, has a metadata header with timestamp/tokens/layers, body is the full system prompt.

### Task 5.2: Manual review and commit

**Files:**
- Commit: `docs/prompts/baseline_<novel>_vol01_ch001.md`
- Commit: `scripts/capture_baseline_prompt.py`

- [ ] **Step 1: Read the captured prompt and verify the checklist**

Open `docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md` and verify:

- [ ] Does the prompt contain the `style_presets.prompt` text (not just the name)?
- [ ] Does it contain the `project_meta` keys?
- [ ] Does it contain 🔴/🟡 genre rules (if genre_rules are seeded)?
- [ ] Does it contain banned words and compliance rules (if seeded)?
- [ ] Does it contain world building (current-vol + global)?
- [ ] Is the total token count under 10,000?

Record ✓/✗ for each in the commit message.

- [ ] **Step 2: Commit the script and baseline**

```bash
git add scripts/capture_baseline_prompt.py docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md
git commit -m "docs(M3.2): capture baseline DeepSeek prompt for yueguang_wenguo vol-01 ch-001

Manual review checklist (recorded in body for git archeology):
- [✓/✗] style_presets.prompt present
- [✓/✗] project_meta keys present
- [✓/✗] genre rules with markers
- [✓/✗] banned + compliance
- [✓/✗] world building (local + global)
- [✓/✗] total < 10,000 tokens"
```

Replace the `[✓/✗]` placeholders with actual results from Step 1.

- [ ] **Step 3: Verify M3.2 exit gate**

```bash
git log --oneline | head -10
pytest tests/ -q 2>&1 | tail -5
bash scripts/measure_coverage.sh 2>&1 | tail -3
```

Expected:
- M3.2 commits visible in `git log` (5-10 commits)
- Full test suite still green (1174+ W2 tests)
- Coverage gate ≥ 90% on `portal/`

---

## Execution Summary

**Total tasks:** 5 phases, 18-22 tasks (T2.1–T2.13 is 13 tasks, T3.1+ is conditional, T1.1–T1.4, T4.1–T4.2, T5.1–T5.2)

**Total commits:** 14-18 atomic commits (1 per task, plus 0-3 hotfixes for W3)

**Total tests added:** 25-30 (12 layer classes × ~2 tests + 2 integration + 0-3 branch tests for W4)

**Test count growth:** 1174 → ~1200+

**Coverage target:** `portal/` ≥ 90% (gate), with `context_builder.py` measured (not in omit)

**Baseline artifact:** `docs/prompts/baseline_yueguang_wenguo_vol01_ch001.md` for future regression detection
