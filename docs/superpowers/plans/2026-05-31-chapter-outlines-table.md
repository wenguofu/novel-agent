# Per-Chapter Outline Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `chapter_outlines` table to `content_db.py` storing per-chapter outline data (title, function, core_events, foreshadowing, ending_hook, danger_scene) and expose it via REST API endpoints.

**Constraint:** Only YAML format is supported. Auto-generated chapter outlines via the agent system must produce `vol-YY-chapters.yaml` files. MD format outline files are not supported for DB sync.

**Architecture:** Extend `content_db.py` with a new `chapter_outlines` table (novel_id, volume, chapter_num, title, function tags JSON, core_events, foreshadowing list JSON, ending_hook, is_danger_scene bool, word_count, updated_at). Add CRUD API endpoints in `app.py` for reading/updating individual chapter outlines. Wire up sync from YAML outline files on save. All outline content is stored as YAML — MD outline files are ignored for DB sync.

**Tech Stack:** SQLite (content_db.py), Flask (app.py), Python

---

## File Map

- **Modify:** `portal/content_db.py` — add table + repository methods
- **Modify:** `portal/app.py` — add API endpoints
- **Modify:** `portal/frontend/src/pages/Outlines.tsx` — wire to per-chapter API (later)

---

### Task 1: Add `chapter_outlines` table to `content_db.py`

**Files:**
- Modify: `portal/content_db.py:87` (after `outlines` table definition)

- [x] **Step 1: Add the CREATE TABLE statement**

After the existing `outlines` table (line ~95), add:

```python
CREATE TABLE IF NOT EXISTS chapter_outlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume TEXT NOT NULL,
    chapter_num INTEGER NOT NULL,
    title TEXT DEFAULT '',
    function TEXT DEFAULT '[]',
    core_events TEXT DEFAULT '',
    foreshadowing TEXT DEFAULT '[]',
    ending_hook TEXT DEFAULT '',
    is_danger_scene INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, volume, chapter_num)
);
CREATE INDEX IF NOT EXISTS idx_co_novel_vol ON chapter_outlines(novel_id, volume);
```

- [x] **Step 2: Add repository methods**

Add after the existing `outline` upsert/fetch methods (~line 440). Methods to add:

```python
def upsert_chapter_outline(novel_name, volume, chapter_num, data):
    """Insert or update a single chapter outline.
    data: {title, function:[], core_events, foreshadowing:[], ending_hook, is_danger_scene, word_count}
    """
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        raise ValueError(f"Novel not found: {novel_name}")
    conn.execute("""
        INSERT INTO chapter_outlines (novel_id, volume, chapter_num, title, function,
            core_events, foreshadowing, ending_hook, is_danger_scene, word_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, volume, chapter_num) DO UPDATE SET
            title=excluded.title, function=excluded.function,
            core_events=excluded.core_events, foreshadowing=excluded.foreshadowing,
            ending_hook=excluded.ending_hook, is_danger_scene=excluded.is_danger_scene,
            word_count=excluded.word_count, updated_at=datetime('now')
    """, (nid, volume, chapter_num, data.get('title',''),
          json.dumps(data.get('function',[])),
          data.get('core_events',''),
          json.dumps(data.get('foreshadowing',[])),
          data.get('ending_hook',''),
          1 if data.get('is_danger_scene') else 0,
          data.get('word_count', 0)))
    conn.commit()
    conn.close()

def get_chapter_outlines(novel_name, volume):
    """Return list of chapter outlines for a volume, ordered by chapter_num."""
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        return []
    rows = conn.execute("""
        SELECT chapter_num, title, function, core_events, foreshadowing,
               ending_hook, is_danger_scene, word_count, updated_at
        FROM chapter_outlines
        WHERE novel_id=? AND volume=?
        ORDER BY chapter_num
    """, (nid, volume)).fetchall()
    conn.close()
    return [_parse_co_row(r) for r in rows]

def get_chapter_outline(novel_name, volume, chapter_num):
    """Return single chapter outline or None."""
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        return None
    row = conn.execute("""
        SELECT chapter_num, title, function, core_events, foreshadowing,
               ending_hook, is_danger_scene, word_count, updated_at
        FROM chapter_outlines
        WHERE novel_id=? AND volume=? AND chapter_num=?
    """, (nid, volume, chapter_num)).fetchone()
    conn.close()
    return _parse_co_row(row) if row else None

def _parse_co_row(row):
    """Parse a chapter_outlines row into a dict."""
    return {
        'chapter_num': row['chapter_num'],
        'title': row['title'],
        'function': json.loads(row['function'] or '[]'),
        'core_events': row['core_events'],
        'foreshadowing': json.loads(row['foreshadowing'] or '[]'),
        'ending_hook': row['ending_hook'],
        'is_danger_scene': bool(row['is_danger_scene']),
        'word_count': row['word_count'],
        'updated_at': row['updated_at'],
    }
```

- [x] **Step 3: Verify build**

Run: `cd portal && python3 -c "from content_db import get_db; print('OK')"`
Expected: PASS (no import errors)

- [x] **Step 4: Commit**

---

### Task 2: Sync `chapter_outlines` from YAML file on outline save

**Files:**
- Modify: `portal/app.py:900` (`api_edit_outline`)

- [x] **Step 1: After writing outline file in `api_edit_outline`, parse YAML and sync**

In `api_edit_outline` (~line 908), after `write_novel_file`, add a call to parse the written YAML file and upsert each chapter. **Save path must be `.yaml` not `.md`:**

```python
@app.route("/api/novels/<novel_name>/outline/<vol_ref>/edit", methods=["POST"])
def api_edit_outline(novel_name, vol_ref):
    data = request.json
    content = data.get("content", "")
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    # Save as YAML (not MD)
    write_novel_file(novel_name, content, "outline", f"{vol_ref}-chapters.yaml")

    # Sync chapter outlines to DB (only from .yaml file)
    outline_yaml_path = os.path.join(get_novels_dir(), novel_name, "outline", f"{vol_ref}-chapters.yaml")
    if os.path.exists(outline_yaml_path):
        try:
            from content_db import upsert_chapter_outline
            import yaml
            with open(outline_yaml_path, encoding='utf-8') as f:
                parsed = yaml.safe_load(f)
            if parsed and 'chapters' in parsed:
                for ch in parsed['chapters']:
                    upsert_chapter_outline(novel_name, vol_ref, int(ch['number']), {
                        'title': ch.get('title', ''),
                        'function': ch.get('function', []),
                        'core_events': ch.get('core_events', ''),
                        'foreshadowing': ch.get('foreshadowing', []),
                        'ending_hook': ch.get('ending_hook', ''),
                        'is_danger_scene': ch.get('is_danger_scene', False),
                        'word_count': ch.get('word_count', 0),
                    })
        except Exception as e:
            logging.warning(f"[outline_sync] {e}")

    return jsonify({"success": True, "message": "大纲已保存", "vol": vol_ref})
```

- [x] **Step 2: Test the sync end-to-end**

Run: `curl -s -X POST "http://localhost:35001/api/novels/大强成神啦/outline/vol-01/edit" -H "Content-Type: application/json" -d '{"content": "# YAML test\nvolume: 1\nchapters:\n  - number: 1\n    title: \"测试章节\"\n    function: [\"开篇\"]\n    core_events: \"测试事件\"\n    foreshadowing: [\"线索1\"]\n    ending_hook: \"悬念结尾\"\n"}'`

Then check: `curl -s "http://localhost:35001/api/novels/大强成神啦/chapter-outlines/vol-01" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, ensure_ascii=False, indent=2))"`

Expected: chapter list with one entry for chapter 1

- [x] **Step 3: Commit**

---

### Task 3: Add API endpoints for per-chapter outline CRUD

**Files:**
- Modify: `portal/app.py` (add after `api_edit_outline`, ~line 920)

- [x] **Step 1: Add GET endpoint for all chapter outlines in a volume**

```python
@app.route("/api/novels/<novel_name>/chapter-outlines/<vol_ref>")
def api_get_chapter_outlines(novel_name, vol_ref):
    """Return all chapter outlines for a volume."""
    try:
        from content_db import get_chapter_outlines
        rows = get_chapter_outlines(novel_name, vol_ref)
        return jsonify({"success": True, "volume": vol_ref, "chapters": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

- [x] **Step 2: Add PUT endpoint for a single chapter outline**

```python
@app.route("/api/novels/<novel_name>/chapter-outlines/<vol_ref>/<int:ch_num>", methods=["PUT"])
def api_put_chapter_outline(novel_name, vol_ref, ch_num):
    """Update a single chapter outline."""
    data = request.json
    try:
        from content_db import upsert_chapter_outline
        upsert_chapter_outline(novel_name, vol_ref, ch_num, {
            'title': data.get('title', ''),
            'function': data.get('function', []),
            'core_events': data.get('core_events', ''),
            'foreshadowing': data.get('foreshadowing', []),
            'ending_hook': data.get('ending_hook', ''),
            'is_danger_scene': data.get('is_danger_scene', False),
            'word_count': data.get('word_count', 0),
        })
        return jsonify({"success": True, "message": f"第{ch_num}章大纲已更新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

- [x] **Step 3: Test single chapter update**

Run: `curl -s -X PUT "http://localhost:35001/api/novels/大强成神啦/chapter-outlines/vol-01/1" -H "Content-Type: application/json" -d '{"title": "测试更新", "function": ["开篇"], "core_events": "事件", "foreshadowing": [], "ending_hook": "", "is_danger_scene": true, "word_count": 3000}'`

Expected: `{"success": true, "message": "第1章大纲已更新"}`

- [x] **Step 4: Test get all**

Run: `curl -s "http://localhost:35001/api/novels/大强成神啦/chapter-outlines/vol-01" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Got {len(d[\"chapters\"])} chapters')"`

Expected: `Got N chapters`

- [x] **Step 5: Commit**

---

### Task 4: YAML-only enforcement — save as `.yaml` and sync only when `.yaml` exists

**Files:**
- Modify: `portal/app.py` (`api_edit_outline`)

- [x] **Step 1: Update `api_edit_outline` to save as `.yaml` and sync from it**

Change `write_novel_file` path from `{vol_ref}-chapters.md` to `{vol_ref}-chapters.yaml`. Add sync block that reads the `.yaml` file and upserts each chapter (only if `.yaml` exists — MD files are ignored):

```python
@app.route("/api/novels/<novel_name>/outline/<vol_ref>/edit", methods=["POST"])
def api_edit_outline(novel_name, vol_ref):
    data = request.json
    content = data.get("content", "")
    if not content:
        return jsonify({"success": False, "error": "内容不能为空"}), 400

    # Save as YAML (not MD) — DB sync only triggers from YAML files
    write_novel_file(novel_name, content, "outline", f"{vol_ref}-chapters.yaml")

    # Sync chapter outlines to DB (YAML only — MD files are ignored)
    outline_yaml_path = os.path.join(get_novels_dir(), novel_name, "outline", f"{vol_ref}-chapters.yaml")
    if os.path.exists(outline_yaml_path):
        try:
            from content_db import upsert_chapter_outline
            import yaml
            with open(outline_yaml_path, encoding='utf-8') as f:
                parsed = yaml.safe_load(f)
            if parsed and 'chapters' in parsed:
                for ch in parsed['chapters']:
                    upsert_chapter_outline(novel_name, vol_ref, int(ch['number']), {
                        'title': ch.get('title', ''),
                        'function': ch.get('function', []),
                        'core_events': ch.get('core_events', ''),
                        'foreshadowing': ch.get('foreshadowing', []),
                        'ending_hook': ch.get('ending_hook', ''),
                        'is_danger_scene': ch.get('is_danger_scene', False),
                        'word_count': ch.get('word_count', 0),
                    })
        except Exception as e:
            logging.warning(f"[outline_sync] {e}")

    return jsonify({"success": True, "message": "大纲已保存", "vol": vol_ref})
```

- [x] **Step 2: Verify `.md` files are NOT synced**

Confirm that if only a `.md` file exists (no `.yaml`), the sync block does not fire. Write a test: manually call `api_edit_outline` with YAML content, confirm chapters are in DB, then confirm that the old `.md` file path is never touched by the sync logic.

- [x] **Step 3: Commit**

---

## Self-Review Checklist

- [x] `chapter_outlines` table has all fields from YAML schema (`number`, `title`, `function[]`, `core_events`, `foreshadowing[]`, `ending_hook`, `is_danger_scene`, `word_count`)
- [x] `upsert_chapter_outline` parses YAML `chapters` array and stores `function`/`foreshadowing` as JSON
- [x] `api_edit_outline` saves as `.yaml` (not `.md`) and syncs only when that file exists
- [x] GET endpoint returns array sorted by `chapter_num`
- [x] PUT endpoint updates single chapter
- [x] Unique constraint on `(novel_id, volume, chapter_num)` prevents duplicates
- [x] Index on `(novel_id, volume)` for fast volume-scoped queries
- [x] Agent system generates `vol-YY-chapters.yaml` format only (not MD)

---

## Implementation Pointer

> **Status:** All 4 tasks + 8 checklist items were already implemented in commit `28b48bc` (2026-05-31 22:23 +0800) — `feat: chapter_outlines table, story_tracking table, ON CONFLICT fixes, 12 functional tests` — predating the M1/M2/M3 plan series.
>
> **Verified 2026-06-06:** 1015/1015 tests pass (4 unit tests in `tests/test_chapter_outlines.py` + 16 functional tests in `tests/functional/test_outline_api.py::TestGetChapterOutlines/TestPutChapterOutline/TestReadOutline/TestEditOutline`). No code changes needed; this is a checkbox backfill + plan close-out.
>
> **Note:** The original plan was never executed as a 4-task plan — it was implemented as part of a larger commit that also added `story_tracking`, `danger_issues` JSON columns, `ON CONFLICT` fixes, and ORM models (`ChapterOutline`, `DangerIssue`, `StoryTracking`). All atomic work landed in one commit on the day the plan was written.