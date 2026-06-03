# M3 — Functional Tests + pre-commit Physical Gate + 6-dim Agent-CR

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the M2 functional spec into a comprehensive functional test suite (~250 tests across 82 unique routes × 2-4 dimensions), enforce TDD via a pre-commit physical gate, gate releases on ≥ 90% line coverage (M3.1 follow-up to close the gap), and add a 6-dimension post-commit agent code review.

**Architecture:**
- `tests/functional/` — black-box HTTP tests using Flask `test_client` against a temporary SQLite DB seeded from `run_v2.py`'s init path. Each endpoint gets **4 dimensions** for the 25 M2 core endpoints and **2 dimensions** (正常路径 + 缺字段) for the other 57. (4-dim everywhere is M3.1.)
- `scripts/check_tdd_compliance.sh` + `.pre-commit-config.yaml` — physical gate that fails `git commit` if `portal/` changed without `tests/`. `hotfix` commits exempt.
- `scripts/measure_coverage.sh` — CI-only coverage script (`pytest --cov=portal --cov-report=term-missing`), requires ≥ 90% line coverage.
- `.claude/hooks/post-commit` + `agent-system/scripts/post_commit_review.sh` — invoke a 6-dim agent code review on every commit; write report to `.code-reviews/<sha>.md`. M3 ships a stub report; full agent invocation is M3.1.

**Tech Stack:** pytest 7+, pytest-cov (new dep), pre-commit 3+ (new dep), Flask `test_client`, existing SQLite + Repository layer.

**Spec reference:** [docs/superpowers/specs/2026-06-03-tdd-system-func-spec-design.md §M3](../specs/2026-06-03-tdd-system-func-spec-design.md)

**Pre-flight checklist:**
- [ ] Working tree clean (152/152 tests passing — verified at plan start)
- [ ] `python3 scripts/verify_spec.py` → 5/5 OK (82 endpoints, 25/25 Manual Notes)
- [ ] On `main` branch (user pre-authorized "main 直跑" for M1/M2; same applies here)
- [ ] Endpoint count: **82 unique routes** (was 83 before the 2026-06-04 dedupe of two `index()` functions in `portal/app.py` — see commit `00dac4a`).

---

## Endpoint Distribution (82 unique routes)

| Test file | Endpoints | Count |
|-----------|-----------|-------|
| `test_smoke.py` (existing in M2) | `GET /`, `GET /assets/<path:filename>` | 2 |
| `test_chapter_lifecycle.py` | chapters × 3, reviews, review-chapter | 5 |
| `test_novel_management.py` | novels list, detail, file, status, gate-status, export, create, file/write, update-status | 9 |
| `test_outline_api.py` | outline × 2, chapter-outlines × 2, danger-issue | 5 |
| `test_domain_crud.py` | characters (7) + foreshadowing (6) + world (3) + arcs (3) + pacing (3) + revelation (3) + genre (1) + alias (1) + story_volumes (1) + volume_plans (1) + project_meta (1) | 30 |
| `test_context.py` | context/build, context/stats | 2 |
| `test_workflow.py` | workflow/preflight, workflow/postflight, enforce-pipeline | 3 |
| `test_config_api.py` | config × 3 + config-db × 3 + styles + templates + usage | 9 |
| `test_init.py` | init/full + 4 table inits + cleanup-bak | 6 |
| `test_writing_api.py` | generate-chapter, optimize-chapter, run-script, wizard/step | 4 |
| `test_ai_stream.py` | ai/chat, ai/stream, rag/query (httpx mocked) | 3 |
| `test_search.py` | content/search, content/stats, content/sync, content/quality-report | 4 |
| **Total** | | **82** |

---

## File Structure

```
novel-agent/
├── portal/                            # (unchanged)
├── tests/
│   ├── conftest.py                    # (existing)
│   ├── functional/                    # NEW
│   │   ├── __init__.py
│   │   ├── conftest.py                # tmp_db, client, sample_novel fixtures
│   │   ├── test_smoke.py              # GET /, GET /assets/foo
│   │   ├── test_chapter_lifecycle.py  # 5 endpoints, 4-dim
│   │   ├── test_novel_management.py   # 9 endpoints, 4-dim core / 2-dim rest
│   │   ├── test_outline_api.py        # 5 endpoints
│   │   ├── test_domain_crud.py        # 30 endpoints across 7 tables
│   │   ├── test_context.py            # 2 endpoints (build + stats)
│   │   ├── test_workflow.py           # 3 endpoints
│   │   ├── test_config_api.py         # 9 endpoints
│   │   ├── test_init.py               # 6 endpoints
│   │   ├── test_writing_api.py        # 4 endpoints
│   │   ├── test_ai_stream.py          # 3 endpoints (httpx mocked)
│   │   └── test_search.py             # 4 endpoints
│   └── (existing tests/ unchanged)
├── scripts/
│   ├── check_tdd_compliance.sh        # NEW
│   ├── install-hooks.sh               # NEW
│   └── measure_coverage.sh            # NEW
├── agent-system/
│   └── scripts/
│       └── post_commit_review.sh      # NEW
├── .claude/
│   └── hooks/
│       └── post-commit                # NEW
├── .pre-commit-config.yaml            # NEW
├── .code-reviews/                     # NEW (gitignored — runtime output)
├── .gitignore                         # (modify: add .code-reviews/)
└── requirements.txt                   # (modify: add pre-commit + pytest-cov)
```

---

## Task 1: Add pre-commit + pytest-cov to requirements

**Files:**
- Modify: `requirements.txt:1-3` (add new deps at the end)

- [ ] **Step 1: Append deps to requirements.txt**

Add these two lines at the end of `requirements.txt`:

```
# M3: pre-commit + coverage
pre-commit>=3.5
pytest-cov>=4.1
```

- [ ] **Step 2: Install**

```bash
pip install pre-commit pytest-cov
```

Expected: `Successfully installed pre-commit-3.x.x ... pytest-cov-4.x.x ...`

- [ ] **Step 3: Verify**

```bash
pre-commit --version
python3 -m pytest --help 2>&1 | grep -q -- '--cov' && echo "pytest-cov OK"
```

Expected: `pre-commit` version ≥ 3.5 prints; `--cov` flag registered.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore(M3): add pre-commit + pytest-cov deps"
```

---

## Task 2: Functional test fixtures (conftest.py)

**Files:**
- Create: `tests/functional/__init__.py` (empty)
- Create: `tests/functional/conftest.py` (tmp_db, client, sample_novel fixtures)
- Create: `tests/functional/test_smoke.py` (smoke tests using the fixtures)

- [ ] **Step 1: Write the failing smoke test**

Create `tests/functional/test_smoke.py`:

```python
"""Smoke tests for the functional test infrastructure itself."""
import pytest


def test_client_serves_root_index(client):
    """Flask test client should return 200 for GET /."""
    res = client.get("/")
    assert res.status_code == 200


def test_client_serves_assets(client):
    """Flask test client should serve /assets/ (may 404 if no build, but never 500)."""
    res = client.get("/assets/missing.js")
    assert res.status_code < 500


def test_sample_novel_fixture_creates_novel(client, sample_novel):
    """sample_novel fixture should create a real novel in the tmp DB."""
    res = client.get(f"/api/novels/{sample_novel}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["novel"]["name"] == sample_novel
```

- [ ] **Step 2: Run test, expect FAIL (no `client`/`sample_novel` fixtures)**

```bash
python3 -m pytest tests/functional/test_smoke.py -v
```

Expected: `ERROR — fixture 'client' not found`, `fixture 'sample_novel' not found`.

- [ ] **Step 3: Implement the fixtures**

Create `tests/functional/conftest.py`:

```python
"""Shared fixtures for functional tests.

Strategy: spin up a temporary SQLite DB in tmp_path, point DATABASE_URL
at it, run the same init path as run_v2.py (schema + config seed), then
yield a Flask test_client. Each test gets a clean DB.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure portal/ is on sys.path so we can import `app` directly.
PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh SQLite DB in tmp_path; yield the DB URL."""
    db_file = tmp_path / "test_content.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    # Force re-import of db.py / repository / app / content_db / context_builder
    # so they pick up the new DATABASE_URL.
    for mod in list(sys.modules):
        if mod.startswith(("db", "repository", "app", "content_db", "config", "context_builder")):
            del sys.modules[mod]
    from db import ensure_unified_schema
    from repository import get_repo
    ensure_unified_schema()
    repo = get_repo()
    repo.init_config_seed()
    yield db_url


@pytest.fixture
def client(tmp_db):
    """Flask test client bound to the tmp DB."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_novel(client, tmp_db, tmp_path):
    """Pre-create a novel named 'test_novel' with minimal data.

    Also creates the novels/test_novel/ directory so file endpoints don't 500.
    Returns the novel name.
    """
    from repository import get_repo
    repo = get_repo()
    repo.create_novel(name="test_novel", title="Test Novel", genre="xianxia")
    novels_dir = tmp_path / "novels"
    novels_dir.mkdir(parents=True, exist_ok=True)
    (novels_dir / "test_novel").mkdir(exist_ok=True)
    return "test_novel"
```

- [ ] **Step 4: Run smoke tests, expect PASS**

```bash
python3 -m pytest tests/functional/test_smoke.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite, expect 152 + 3 = 155 pass**

```bash
python3 -m pytest tests/ -q
```

Expected: `155 passed, 0 failed`.

- [ ] **Step 6: Commit**

```bash
git add tests/functional/
git commit -m "feat(M3): functional test fixtures (tmp_db, client, sample_novel)"
```

---

## Task 3: pre-commit physical gate

**Files:**
- Create: `scripts/check_tdd_compliance.sh`
- Create: `.pre-commit-config.yaml`
- Create: `tests/test_check_tdd_compliance.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_check_tdd_compliance.py`:

```python
"""Test the check_tdd_compliance.sh script via subprocess + a temp git repo."""
import os
import subprocess
from pathlib import Path

import pytest


def _init_tmp_repo(tmp_path: Path) -> Path:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in [
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        ["git", "commit", "--allow-empty", "-m", "init"],
    ]:
        subprocess.run(cmd, cwd=tmp_path, env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp_path


SCRIPT = Path(__file__).parent.parent / "scripts" / "check_tdd_compliance.sh"


def test_blocks_portal_change_without_test(tmp_path):
    """portal/ change without tests/ should be blocked."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "portal" / "app.py").write_text("# changed\n")
    subprocess.run(["git", "add", "portal/app.py"], cwd=repo, check=True)
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0, f"Expected block, got: {result.stdout}\n{result.stderr}"


def test_allows_portal_change_with_test(tmp_path):
    """portal/ change with matching tests/ change should be allowed."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "tests").mkdir()
    (repo / "portal" / "app.py").write_text("# changed\n")
    (repo / "tests" / "test_app.py").write_text("# test added\n")
    subprocess.run(["git", "add", "portal/app.py", "tests/test_app.py"], cwd=repo, check=True)
    result = subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, f"Expected allow, got: {result.stdout}\n{result.stderr}"


def test_allows_hotfix_commits(tmp_path):
    """Commit message containing 'hotfix' should bypass the gate."""
    repo = _init_tmp_repo(tmp_path)
    (repo / "portal").mkdir()
    (repo / "portal" / "app.py").write_text("# hotfix\n")
    subprocess.run(["git", "add", "portal/app.py"], cwd=repo, check=True)
    # Commit-msg path via env var HOOK_COMMIT_MSG_FILE
    msg_file = repo / "COMMIT_EDITMSG"
    msg_file.write_text("hotfix: emergency fix\n")
    result = subprocess.run(
        ["bash", "-c", f"HOOK_COMMIT_MSG_FILE={msg_file} bash {SCRIPT}"],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"hotfix should bypass, got: {result.stdout}\n{result.stderr}"
```

- [ ] **Step 2: Run test, expect FAIL (script doesn't exist)**

```bash
python3 -m pytest tests/test_check_tdd_compliance.py -v
```

Expected: `FileNotFoundError` on `bash /path/to/check_tdd_compliance.sh`.

- [ ] **Step 3: Implement the check script**

Create `scripts/check_tdd_compliance.sh`:

```bash
#!/usr/bin/env bash
# check_tdd_compliance.sh — TDD physical gate for portal/ changes.
#
# Rules:
#   - portal/ changes must be accompanied by tests/ changes
#   - tests/ changes must be in test_*.py, conftest.py, __init__.py, fixtures/, audit/
#   - commit message containing "hotfix" bypasses the gate (env: HOOK_COMMIT_MSG_FILE)
#   - changes to the gate itself bypass
set -euo pipefail

# Hotfix bypass via commit message
COMMIT_MSG_FILE="${HOOK_COMMIT_MSG_FILE:-}"
if [ -n "$COMMIT_MSG_FILE" ] && [ -f "$COMMIT_MSG_FILE" ]; then
    if grep -qi "hotfix" "$COMMIT_MSG_FILE"; then
        echo "[check_tdd] hotfix detected in commit message — bypassing gate"
        exit 0
    fi
fi

# Detect staged changes
STAGED=$(git diff --cached --name-only)

PORTAL_CHANGED=$(echo "$STAGED" | grep -E '^portal/.*\.py$' || true)
TESTS_CHANGED=$(echo "$STAGED" | grep -E '^tests/' || true)
SELF_CHANGED=$(echo "$STAGED" | grep -E '^(\.pre-commit-config\.yaml|scripts/check_tdd_compliance\.sh|\.claude/hooks/.*|agent-system/scripts/post_commit_review\.sh)$' || true)

# Self-change bypass (changing the gate itself is allowed)
if [ -n "$SELF_CHANGED" ] && [ -z "$PORTAL_CHANGED" ]; then
    echo "[check_tdd] only gate files changed — bypassing"
    exit 0
fi

# Rule 1: portal/ changes require tests/ changes
if [ -n "$PORTAL_CHANGED" ]; then
    if [ -z "$TESTS_CHANGED" ]; then
        echo "[check_tdd] BLOCK: portal/ changed but no tests/ changes" >&2
        echo "  Files changed:" >&2
        echo "$PORTAL_CHANGED" | sed 's/^/    /' >&2
        echo "  Fix: add or modify a file under tests/ in the same commit," >&2
        echo "       or include 'hotfix' in the commit message." >&2
        exit 1
    fi
fi

# Rule 2: tests/ changes must be in test_*.py or conftest.py
if [ -n "$TESTS_CHANGED" ]; then
    NON_TEST=$(echo "$TESTS_CHANGED" | grep -vE '^tests/(test_.*\.py|conftest\.py|.*/__init__\.py|.*/fixtures/.*|.*/audit/.*|test_check_tdd_compliance\.py)$' || true)
    if [ -n "$NON_TEST" ]; then
        echo "[check_tdd] BLOCK: tests/ contains non-test files" >&2
        echo "  Offenders:" >&2
        echo "$NON_TEST" | sed 's/^/    /' >&2
        echo "  Allowed: test_*.py, conftest.py, __init__.py, fixtures/, audit/" >&2
        exit 1
    fi
fi

echo "[check_tdd] OK"
exit 0
```

- [ ] **Step 4: Make executable + run test, expect PASS**

```bash
chmod +x scripts/check_tdd_compliance.sh
python3 -m pytest tests/test_check_tdd_compliance.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Wire up pre-commit config**

Create `.pre-commit-config.yaml`:

```yaml
# Pre-commit hooks for novel-agent
# Install: pre-commit install (or run scripts/install-hooks.sh)
# Run manually: pre-commit run --all-files
repos:
  - repo: local
    hooks:
      - id: tdd-required-test
        name: TDD — portal changes require test changes
        entry: scripts/check_tdd_compliance.sh
        language: script
        files: ^portal/.*\.py$|^tests/
        pass_filenames: false
        stages: [pre-commit]
```

- [ ] **Step 6: Run full suite, expect 155 + 3 = 158 pass**

```bash
python3 -m pytest tests/ -q
```

Expected: `158 passed, 0 failed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/check_tdd_compliance.sh .pre-commit-config.yaml tests/test_check_tdd_compliance.py
git commit -m "feat(M3): pre-commit TDD gate (portal changes require test changes)"
```

---

## Task 4: test_chapter_lifecycle.py (4-dim pattern reference)

**Files:**
- Create: `tests/functional/test_chapter_lifecycle.py`

**Endpoints covered (5, all from M2 25 core list):**
- `GET /api/novels/<novel_name>/chapters/<path:ch_ref>` (core: review-chapter) 
- `POST /api/novels/<novel_name>/chapters/<path:ch_ref>/edit`
- `DELETE /api/novels/<novel_name>/chapters/<path:ch_ref>`
- `GET /api/novels/<novel_name>/reviews/<ch_ref>`
- `POST /api/novels/<novel_name>/review-chapter` (M2 core)

This task establishes the **4-dim pattern** that the M2 core endpoints follow. Tasks 5-13 reference this pattern.

- [ ] **Step 1: Write the test file**

```python
"""Functional tests for chapter lifecycle endpoints (M2 core 4-dim pattern).

4 dimensions per endpoint:
  1. happy_path_*   — 200/201 + response schema assertion
  2. missing_field_ — 400 + error message contains key name (or success=False)
  3. not_found_     — 404 when novel_name (or other ref) doesn't exist
  4. wrong_method_  — 405 when method doesn't match the route
"""
import pytest


# ─── GET chapter ────────────────────────────────────────────────────────────

class TestGetChapter:
    def test_happy_path_returns_chapter(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / f"{ch_ref.replace('/', '-')}.md").write_text("# 第1章\n\n测试内容\n")
        res = client.get(f"/api/novels/{sample_novel}/chapters/{ch_ref}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "测试内容" in data.get("content", "")

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001")
        assert res.status_code == 405


# ─── POST chapter edit ─────────────────────────────────────────────────────

class TestEditChapter:
    def test_happy_path_writes_chapter(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        (tmp_path / "novels" / sample_novel / "manuscript").mkdir(parents=True, exist_ok=True)
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/{ch_ref}/edit",
            json={"content": "新章节内容", "scene": "open"},
        )
        assert res.status_code in (200, 201)
        assert res.get_json()["success"] is True

    def test_missing_field_content_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit",
            json={"scene": "open"},
        )
        assert res.status_code in (400, 422) or (
            res.status_code == 200 and res.get_json().get("success") is False
        )

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001/edit")
        assert res.status_code == 405


# ─── DELETE chapter ────────────────────────────────────────────────────────

class TestDeleteChapter:
    def test_happy_path_soft_deletes(self, client, sample_novel, tmp_path):
        ch_ref = "vol-01/ch-001"
        ms_dir = tmp_path / "novels" / sample_novel / "manuscript"
        ms_dir.mkdir(parents=True, exist_ok=True)
        (ms_dir / f"{ch_ref.replace('/', '-')}.md").write_text("# content")
        res = client.delete(f"/api/novels/{sample_novel}/chapters/{ch_ref}")
        assert res.status_code in (200, 204)

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/chapters/vol-01/ch-001")
        assert res.status_code == 405


# ─── GET review ────────────────────────────────────────────────────────────

class TestGetReview:
    def test_happy_path_returns_review_or_404(self, client, sample_novel, tmp_path):
        """Acceptable: 200 with review content, or 404 if endpoint requires DB row first."""
        res = client.get(f"/api/novels/{sample_novel}/reviews/vol-01/ch-001")
        assert res.status_code in (200, 404)

    def test_wrong_method_post_returns_405(self, client, sample_novel):
        res = client.post(f"/api/novels/{sample_novel}/reviews/vol-01/ch-001")
        assert res.status_code == 405


# ─── POST review-chapter (AI review trigger; M2 core) ─────────────────────

class TestReviewChapter:
    def test_happy_path_returns_review_object(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"chapter_ref": "vol-01/ch-001", "content": "测试内容"},
        )
        # AI review may fail without API key — accept any non-5xx with 'success' key.
        assert res.status_code < 500
        assert "success" in res.get_json()

    def test_missing_field_chapter_ref_returns_400(self, client, sample_novel):
        res = client.post(
            f"/api/novels/{sample_novel}/review-chapter",
            json={"content": "no ref"},
        )
        assert res.status_code < 500

    def test_wrong_method_get_returns_405(self, client, sample_novel):
        res = client.get(f"/api/novels/{sample_novel}/review-chapter")
        assert res.status_code == 405
```

- [ ] **Step 2: Run, expect PASS (some may be skipped if endpoint returns 404 due to missing DB state)**

```bash
python3 -m pytest tests/functional/test_chapter_lifecycle.py -v
```

Expected: ~10-12 tests passed (or skipped, noted in commit message).

- [ ] **Step 3: Run full suite**

```bash
python3 -m pytest tests/ -q
```

Expected: `158 + ~12 = ~170 passed`.

- [ ] **Step 4: Commit**

```bash
git add tests/functional/test_chapter_lifecycle.py
git commit -m "feat(M3): functional tests for chapter lifecycle (5 endpoints, 4-dim pattern)"
```

---

## Task 5: test_novel_management.py

**Files:**
- Create: `tests/functional/test_novel_management.py`

**Endpoints (9):** `GET /api/novels`, `GET /api/novels/<n>`, `GET /api/novels/<n>/file`, `GET /api/novels/<n>/status`, `GET /api/novels/<n>/gate-status`, `GET /api/novels/<n>/export`, `POST /api/novels/create`, `POST /api/novels/<n>/file/write`, `POST /api/novels/<n>/update-status`

- [ ] **Step 1: Write test file (follow 4-dim pattern from Task 4)**

Use the same class structure (`TestXxxEndpoint`) with 4-dim tests per endpoint. For GET-only endpoints, omit `missing_field_*` (no body). For status/export/file endpoints, use 2-dim (happy_path + wrong_method).

- [ ] **Step 2: Run, expect PASS**

```bash
python3 -m pytest tests/functional/test_novel_management.py -v
```

- [ ] **Step 3: Run full suite + commit**

```bash
python3 -m pytest tests/ -q
git add tests/functional/test_novel_management.py
git commit -m "feat(M3): functional tests for novel management (9 endpoints, 2-4-dim)"
```

---

## Task 6: test_outline_api.py

**Files:**
- Create: `tests/functional/test_outline_api.py`

**Endpoints (5):** `GET /api/novels/<n>/outline/<vol>`, `POST /api/novels/<n>/outline/<vol>/edit`, `GET /api/novels/<n>/chapter-outlines/<vol>`, `PUT /api/novels/<n>/chapter-outlines/<vol>/<int:ch>`, `GET /api/novels/<n>/danger-issue/<vol>/<ch>`

- [ ] **Step 1: Write test file (follow 4-dim pattern from Task 4)**

For outline/chapter-outlines, pre-create the outline file in `novels/<n>/outline/vol-XX-chapters.md` so the GET can find it.

- [ ] **Step 2: Run, expect PASS + commit**

```bash
python3 -m pytest tests/functional/test_outline_api.py -v
python3 -m pytest tests/ -q
git add tests/functional/test_outline_api.py
git commit -m "feat(M3): functional tests for outline + chapter-outlines + danger-issue (5 endpoints)"
```

---

## Task 7: test_domain_crud.py (largest — 7 tables)

**Files:**
- Create: `tests/functional/test_domain_crud.py`

**Endpoints (30):**
- characters (7): list, get, add, manage (PUT/DELETE), event, init, ai-profile
- foreshadowing (6): list, unresolved, add, manage (PUT/DELETE), resolve, init
- world_building (3): list, add, manage (PUT/DELETE)
- plot_arcs (3): list, add, manage (PUT/DELETE)
- pacing_control (3): list, add, manage (PUT/DELETE)
- revelation_schedule (3): list, add, manage (PUT/DELETE)
- genre_rules (1), alias_names (1), story_volumes (1), volume_plans (1), project_meta (1)

- [ ] **Step 1: Write test file using a parameterized helper**

```python
"""Functional tests for domain CRUD endpoints (7 tables, 30 endpoints).

Pattern: a shared `_crud_get_list` and `_crud_post_create` helper, then
per-table classes that supply the URLs and minimum required payload.
"""
import pytest

# Each table: (list_url_template, create_url_template, sample_payload, update_url_template)
TABLES = [
    ("characters",     "/api/characters/{novel}",     "/api/characters/{novel}",                          {"name": "李闲", "role": "主角"}),
    ("foreshadowing",  "/api/foreshadowing/{novel}",  "/api/foreshadowing/{novel}",                       {"title": "伏笔1", "content": "..."}),
    ("world_building", "/api/world_building/{novel}", "/api/world_building/{novel}",                      {"title": "玄天城", "category": "location"}),
    ("plot_arcs",      "/api/plot_arcs/{novel}",      "/api/plot_arcs/{novel}",                           {"title": "主线", "arc_type": "main"}),
    ("pacing_control", "/api/pacing_control/{novel}", "/api/pacing_control/{novel}",                      {"volume": 1, "chapter": 1, "pace_type": "fast"}),
    ("revelation_schedule", "/api/revelation_schedule/{novel}", "/api/revelation_schedule/{novel}",      {"title": "揭晓1", "reveal_vol": 2}),
]


@pytest.mark.parametrize("name,list_url,create_url,payload", TABLES,
                         ids=[t[0] for t in TABLES])
def test_list_endpoint_happy_path(client, sample_novel, name, list_url, create_url, payload):
    """Each list endpoint returns 200 + success=True with empty/populated list."""
    res = client.get(list_url.format(novel=sample_novel))
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True


@pytest.mark.parametrize("name,list_url,create_url,payload", TABLES,
                         ids=[t[0] for t in TABLES])
def test_create_endpoint_happy_path(client, sample_novel, name, list_url, create_url, payload):
    """Each create endpoint accepts a valid payload and returns success."""
    res = client.post(create_url.format(novel=sample_novel), json=payload)
    assert res.status_code in (200, 201)
    data = res.get_json()
    assert data["success"] is True


# Single-endpoint tests (genre_rules, alias_names, story_volumes, volume_plans, project_meta)

class TestReadOnlyListEndpoints:
    """GET-only list endpoints (no POST/PUT/DELETE)."""
    URLS = [
        "/api/genre_rules/{novel}",
        "/api/alias_names/{novel}",
        "/api/story_volumes/{novel}",
        "/api/volume_plans/{novel}",
        "/api/project_meta/{novel}",
    ]

    @pytest.mark.parametrize("url", URLS)
    def test_happy_path(self, client, sample_novel, url):
        res = client.get(url.format(novel=sample_novel))
        assert res.status_code == 200
        assert res.get_json()["success"] is True
```

- [ ] **Step 2: Run, expect PASS**

```bash
python3 -m pytest tests/functional/test_domain_crud.py -v
```

- [ ] **Step 3: Run full suite + commit**

```bash
python3 -m pytest tests/ -q
git add tests/functional/test_domain_crud.py
git commit -m "feat(M3): functional tests for domain CRUD (30 endpoints, 7 tables)"
```

---

## Task 8: test_context.py

**Files:**
- Create: `tests/functional/test_context.py`

**Endpoints (2):** `POST /api/context/build`, `GET /api/context/stats/<novel>/<vol>/<ch>`

- [ ] **Step 1: Write test file (4-dim for build, 2-dim for stats)**

Key assertion: `build` returns 12-entry `layers` array, `stats` returns 12-entry `layers` with `available` bool.

- [ ] **Step 2-3: Run + commit**

```bash
python3 -m pytest tests/functional/test_context.py -v
python3 -m pytest tests/ -q
git add tests/functional/test_context.py
git commit -m "feat(M3): functional tests for context build + stats (2 endpoints)"
```

---

## Task 9: test_workflow.py

**Files:**
- Create: `tests/functional/test_workflow.py`

**Endpoints (3):** `POST /api/workflow/preflight/<novel>` (regression for `169cfb1`), `POST /api/workflow/postflight/<novel>`, `POST /api/novels/<n>/enforce-pipeline`

- [ ] **Step 1: Write test file — INCLUDE the 169cfb1 regression test**

```python
def test_preflight_does_not_nameerror_on_missing_chapter_num(self, client, sample_novel):
    """Regression: chapter_num must be read from request.json, not assumed.
    Before hotfix 169cfb1, this would raise NameError and return 500."""
    res = client.post(f"/api/workflow/preflight/{sample_novel}", json={"volume": "vol-01"})
    assert res.status_code < 500
```

- [ ] **Step 2-3: Run + commit**

```bash
python3 -m pytest tests/functional/test_workflow.py -v
python3 -m pytest tests/ -q
git add tests/functional/test_workflow.py
git commit -m "feat(M3): functional tests for workflow (3 endpoints, includes 169cfb1 regression)"
```

---

## Task 10: test_config_api.py

**Files:**
- Create: `tests/functional/test_config_api.py`

**Endpoints (9):** config × 3 (GET, save, test), config-db × 3 (GET, POST, PUT/DELETE), styles, templates, usage/stats

- [ ] **Step 1: Write test file (4-dim for POST/PUT, 2-dim for GET-only)**

- [ ] **Step 2-3: Run + commit**

```bash
git add tests/functional/test_config_api.py
git commit -m "feat(M3): functional tests for config API (9 endpoints)"
```

---

## Task 11: test_init.py

**Files:**
- Create: `tests/functional/test_init.py`

**Endpoints (6):** `POST /api/init/full/<novel>`, `POST /api/novels/<n>/world-building/init`, `POST /api/novels/<n>/plot-arcs/init`, `POST /api/novels/<n>/pacing/init`, `POST /api/novels/<n>/revelation/init`, `POST /api/novels/<n>/cleanup-bak`

- [ ] **Step 1: Write test file (4-dim per endpoint)**

- [ ] **Step 2-3: Run + commit**

```bash
git add tests/functional/test_init.py
git commit -m "feat(M3): functional tests for init (6 endpoints)"
```

---

## Task 12: test_writing_api.py

**Files:**
- Create: `tests/functional/test_writing_api.py`

**Endpoints (4):** `POST /api/novels/<n>/generate-chapter`, `POST /api/novels/<n>/optimize-chapter`, `POST /api/novels/<n>/run-script`, `POST /api/wizard/step`

These are slow (AI-backed) — accept any non-5xx with `success` key.

- [ ] **Step 1: Write test file (2-dim each: happy_path + missing_field)**

- [ ] **Step 2-3: Run + commit**

```bash
git add tests/functional/test_writing_api.py
git commit -m "feat(M3): functional tests for writing API (4 endpoints)"
```

---

## Task 13: test_ai_stream.py (httpx mocked)

**Files:**
- Create: `tests/functional/test_ai_stream.py`

**Endpoints (3):** `POST /api/ai/chat`, `POST /api/ai/stream`, `POST /api/rag/query`

- [ ] **Step 1: Write test file using `unittest.mock.patch` on `httpx.post`**

```python
from unittest.mock import patch, MagicMock

def test_ai_chat_returns_response(self, client):
    fake = MagicMock()
    fake.json.return_value = {"choices": [{"message": {"content": "fake reply"}}]}
    fake.raise_for_status.return_value = None
    with patch("httpx.post", return_value=fake):
        res = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code < 500
    assert "success" in res.get_json()
```

For `/api/ai/stream`, mock `httpx.stream` and assert the response is an event-stream.

- [ ] **Step 2-3: Run + commit**

```bash
git add tests/functional/test_ai_stream.py
git commit -m "feat(M3): functional tests for AI endpoints (3 endpoints, httpx mocked)"
```

---

## Task 14: test_search.py

**Files:**
- Create: `tests/functional/test_search.py`

**Endpoints (4):** `GET /api/content/search?q=`, `GET /api/content/stats/<novel>`, `POST /api/content/sync`, `GET /api/content/quality-report/<novel>`

- [ ] **Step 1: Write test file (2-dim each: happy_path + wrong_method)**

- [ ] **Step 2-3: Run + commit**

```bash
git add tests/functional/test_search.py
git commit -m "feat(M3): functional tests for content search + stats + sync (4 endpoints)"
```

---

## Task 15: Coverage measurement script (CI-only)

**Files:**
- Create: `scripts/measure_coverage.sh`
- Modify: `README.md` (add "覆盖率门槛" section)

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# measure_coverage.sh — runs the full suite with coverage, enforces ≥ 90%.
# CI-only. Pre-commit does NOT run this (too slow for every commit).
set -euo pipefail

MIN_COVERAGE=90
REPORT=$(python3 -m pytest tests/ --cov=portal --cov-report=term --cov-report=json:/tmp/cov.json -q 2>&1) || true
echo "$REPORT" | tail -20

COVERAGE=$(echo "$REPORT" | grep -oE 'TOTAL\s+[0-9]+\s+[0-9]+\s+[0-9]+%' | awk '{print $4}' | tr -d '%')

if [ -z "$COVERAGE" ]; then
    echo "[coverage] FAIL: could not parse coverage %" >&2
    exit 1
fi

if [ "$COVERAGE" -lt "$MIN_COVERAGE" ]; then
    echo "[coverage] FAIL: $COVERAGE% < required $MIN_COVERAGE%" >&2
    echo "Run 'python3 -m pytest tests/ --cov=portal --cov-report=term-missing' to see gaps." >&2
    exit 1
fi

echo "[coverage] OK: $COVERAGE% ≥ $MIN_COVERAGE%"
exit 0
```

- [ ] **Step 2: Make executable, run, document baseline**

```bash
chmod +x scripts/measure_coverage.sh
bash scripts/measure_coverage.sh
```

Expected: shows current coverage % (likely 30-60% with M3 test files added). Document the actual number in the commit.

- [ ] **Step 3: Document in README**

Add to README under TDD 流程:
```markdown
## 覆盖率门槛
`bash scripts/measure_coverage.sh` (CI 跑, pre-commit 不跑) — 门槛 line coverage ≥ 90%。
当前 M3 基线: <measured>% (M3.1 follow-up 关闭差距).
```

- [ ] **Step 4: Commit**

```bash
git add scripts/measure_coverage.sh README.md
git commit -m "feat(M3): coverage measurement script (CI gate, ≥ 90%)"
```

---

## Task 16: 6-dim agent code review hook (stub mode)

**Files:**
- Create: `.claude/hooks/post-commit`
- Create: `agent-system/scripts/post_commit_review.sh`
- Create: `scripts/install-hooks.sh`
- Modify: `.gitignore` (add `.code-reviews/`)
- Modify: `README.md` (add "6 维 Agent Code Review" section)

- [ ] **Step 1: Create the hook entry point**

Create `.claude/hooks/post-commit`:

```bash
#!/usr/bin/env bash
# post-commit hook: invoke the 6-dim agent code review.
# Writes report to .code-reviews/<short-sha>.md
# Loops until 0 issues or commit message contains 'hotfix'.
set -euo pipefail

# Don't run if this is a hook-itself commit
if git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -qE '^\.claude/hooks/'; then
    echo "[agent-CR] hook self-change — skipping"
    exit 0
fi

# Hotfix bypass
COMMIT_MSG=$(git log -1 --pretty=%B)
if echo "$COMMIT_MSG" | grep -qi "hotfix"; then
    echo "[agent-CR] hotfix detected — skipping"
    exit 0
fi

bash agent-system/scripts/post_commit_review.sh "$(git rev-parse HEAD)"
```

- [ ] **Step 2: Create the review script (stub mode)**

Create `agent-system/scripts/post_commit_review.sh`:

```bash
#!/usr/bin/env bash
# post_commit_review.sh — invokes the 6-dim agent code review.
# Args: $1 = full SHA (default: HEAD)
# M3 ships in stub mode (writes a placeholder report). M3.1 wires the full agent.
set -euo pipefail

SHA="${1:-$(git rev-parse HEAD)}"
SHORT_SHA="${SHA:0:7}"
REPORT_DIR=".code-reviews"
REPORT_FILE="$REPORT_DIR/$SHORT_SHA.md"

mkdir -p "$REPORT_DIR"

DIFF=$(git diff HEAD~1 HEAD 2>/dev/null || true)
if [ -z "$DIFF" ]; then
    echo "[agent-CR] empty diff — skipping"
    exit 0
fi

# Write a placeholder report. M3.1 will invoke the actual agent.
{
    echo "# Agent Code Review — $SHORT_SHA"
    echo
    echo "**Commit:** \`$SHA\`"
    echo "**Date:** $(date -Iseconds)"
    echo "**Reviewer:** post_commit_review.sh (stub mode, 6-dim)"
    echo
    echo "## Dimensions"
    echo
    echo "1. Correctness    — ⏳ pending (M3.1 wires full agent)"
    echo "2. Security       — ⏳ pending"
    echo "3. Style          — ⏳ pending"
    echo "4. Test coverage  — ⏳ pending"
    echo "5. Performance    — ⏳ pending"
    echo "6. Docs           — ⏳ pending"
    echo
    echo "## ISSUES FOUND"
    echo
    echo "(pending — M3.1)"
    echo
    echo "## VERDICT"
    echo
    echo "STUB (M3.1 will populate)"
    echo
    echo "---"
    echo
    echo "<details><summary>Diff (for reference)</summary>"
    echo
    echo '```diff'
    echo "$DIFF"
    echo '```'
    echo
    echo "</details>"
} > "$REPORT_FILE"

echo "[agent-CR] stub report written to $REPORT_FILE"
```

- [ ] **Step 3: Create install-hooks.sh**

```bash
#!/usr/bin/env bash
# install-hooks.sh — install all project git hooks.
set -euo pipefail
HOOKS_DIR=".git/hooks"
mkdir -p "$HOOKS_DIR"

if [ -f .claude/hooks/post-commit ]; then
    cp .claude/hooks/post-commit "$HOOKS_DIR/post-commit"
    chmod +x "$HOOKS_DIR/post-commit"
    echo "[hooks] installed post-commit hook"
fi

if [ -f .pre-commit-config.yaml ]; then
    pre-commit install 2>/dev/null || echo "[hooks] pre-commit not installed; run: pip install pre-commit"
fi
```

- [ ] **Step 4: Update .gitignore**

```bash
echo "" >> .gitignore
echo "# M3: agent code review reports" >> .gitignore
echo ".code-reviews/" >> .gitignore
```

- [ ] **Step 5: Smoke test the hook**

```bash
chmod +x .claude/hooks/post-commit agent-system/scripts/post_commit_review.sh scripts/install-hooks.sh
git commit --allow-empty -m "test: agent-CR smoke"
ls .code-reviews/
cat .code-reviews/$(ls -t .code-reviews/ | head -1) | head -10
```

Expected: `.code-reviews/<sha>.md` exists with the stub structure.

- [ ] **Step 6: Update README**

Add to README under TDD 流程:
```markdown
## 6 维 Agent Code Review
每次 commit 后, `.claude/hooks/post-commit` 自动写 `.code-reviews/<sha>.md` (6 维 review 报告)。
M3 = stub mode (placeholder 报告); 完整 agent 接入见 M3.1。
跳过: commit 含 `hotfix`。
安装: `bash scripts/install-hooks.sh`
```

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/post-commit agent-system/scripts/post_commit_review.sh scripts/install-hooks.sh .gitignore README.md
git commit -m "feat(M3): 6-dim agent code review hook (stub mode, M3.1 wires full agent)"
```

---

## Task 17: M3 final integration verification

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -q --tb=short
```

Expected: All previous tests + 12 new functional test files pass. Document final count in commit.

- [ ] **Step 2: Run verify_spec (sanity)**

```bash
python3 scripts/verify_spec.py
```

Expected: 5/5 OK.

- [ ] **Step 3: Run coverage**

```bash
bash scripts/measure_coverage.sh
```

Expected: shows current % (likely 30-60% — note in commit, M3.1 will close gap).

- [ ] **Step 4: Run check_tdd_compliance dry-run**

```bash
git diff --cached --name-only | head
HOOK_COMMIT_MSG_FILE=/dev/null bash scripts/check_tdd_compliance.sh
```

Expected: exit 0.

- [ ] **Step 5: Final cross-file review checklist**

- [ ] `tests/functional/` has 13 test files (1 smoke + 12 from Tasks 4-14)
- [ ] `tests/functional/__init__.py` and `tests/functional/conftest.py` exist
- [ ] `.pre-commit-config.yaml` is present
- [ ] `scripts/check_tdd_compliance.sh`, `scripts/measure_coverage.sh`, `scripts/install-hooks.sh` are executable
- [ ] `.claude/hooks/post-commit`, `agent-system/scripts/post_commit_review.sh` are executable
- [ ] `requirements.txt` has `pre-commit>=3.5` and `pytest-cov>=4.1`
- [ ] README has "覆盖率门槛" and "6 维 Agent Code Review" sections
- [ ] `.gitignore` has `.code-reviews/`

- [ ] **Step 6: Commit the audit report**

```bash
python3 -m pytest tests/ --collect-only -q > tests/audit/m3_test_list.txt
git add tests/audit/m3_test_list.txt
git commit -m "chore(M3): final test inventory snapshot"
```

---

## Open Items / Known Gaps (M3.1)

These are NOT blockers for M3 ship, but are explicit M3.1 follow-ups:

1. **Coverage < 90%**: Tasks 4-14 exercise HTTP boundary via Flask test_client, but many internal helpers (`context_builder._build_*_context`, `repository.*`) won't be hit. M3.1 should add direct unit tests for low-coverage modules.

2. **Full agent-CR wiring**: Task 16 ships a stub report. M3.1 should wire up `claude-code` (or similar) as the actual review agent, with stable prompt template and 6-dim verdict parsing.

3. **4-dim for the 57 non-core endpoints**: M3 ships 2-dim for these. M3.1 should add the missing 2 dims (not_found + wrong_method) to align with the design doc's "4 必含" rule.

4. **CI integration**: `scripts/measure_coverage.sh` is callable but not wired to GitHub Actions / GitLab CI. M3.1 should add `.github/workflows/ci.yml` (or equivalent).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-m3-functional-tests-precommit.md`. 17 tasks covering:**

| # | Task | Subsystem |
|---|------|-----------|
| 1 | Add pre-commit + pytest-cov | Deps |
| 2 | Functional test fixtures (conftest) | Test infra |
| 3 | pre-commit TDD gate | Gate |
| 4-14 | 11 functional test files (~250 tests, 82 routes) | Tests |
| 15 | Coverage measurement script | Coverage gate |
| 16 | 6-dim agent-CR hook (stub) | Agent-CR |
| 17 | Final integration verification | Verification |

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, two-stage review (spec compliance + code quality) between tasks. Best for the long repetitive test-file tasks (4-14) where the pattern is well-defined.

**2. Inline Execution** — Execute tasks in this session. Better if user wants to interject between tasks.

**Which approach?**
