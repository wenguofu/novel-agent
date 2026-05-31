"""
Content Database — unified access layer for novel content.
Uses repository.py (SQLAlchemy) under the hood; supports SQLite and MySQL
via DATABASE_URL environment variable.

All public functions are maintained for backward compatibility.
Internal DB access goes through repository.get_repo().
"""

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.db")
NOVELS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "novels")

# Lazy import to avoid circular deps
_repo = None

def _get_repo():
    global _repo
    if _repo is None:
        from repository import get_repo
        _repo = get_repo()
    return _repo

def get_db():
    """Return a raw DB connection for backward compatibility.

    For SQLite mode: returns a sqlite3 connection with Row factory.
    For MySQL mode: logs a deprecation warning and returns a session wrapper.

    New code should use repository.get_repo() instead.
    """
    import os as _os
    db_url = _os.environ.get("DATABASE_URL", "")
    if db_url.startswith("mysql"):
        import warnings
        warnings.warn("get_db() is deprecated with MySQL; use repository.get_repo()", DeprecationWarning)
        # Return a thin session wrapper for backward compat
        return _RepoSessionWrapper()

    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class _RepoSessionWrapper:
    """Minimal wrapper that provides sqlite3.Row-like interface over repo methods.
    Only used for backward compatibility in MySQL mode."""

    def execute(self, sql, params=None):
        """Parse common SQL patterns and delegate to repo methods."""
        sql_upper = sql.strip().upper()
        # This is a best-effort compatibility layer; complex queries should use repo directly
        raise NotImplementedError(
            "Direct SQL execution is not supported in MySQL mode. "
            "Use repository.get_repo() methods instead."
        )

    def close(self):
        pass

# ═══════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS novels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    title TEXT DEFAULT '',
    genre TEXT DEFAULT '',
    subgenre TEXT DEFAULT '',
    word_goal TEXT DEFAULT '',
    total_chapters INTEGER DEFAULT 0,
    total_words INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume TEXT NOT NULL,
    content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, volume)
);

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

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume TEXT NOT NULL,
    chapter_num INTEGER NOT NULL,
    chapter_ref TEXT NOT NULL,
    content TEXT NOT NULL,
    title TEXT DEFAULT '',
    word_count INTEGER DEFAULT 0,
    content_hash TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, chapter_ref)
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_ref TEXT NOT NULL,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
    ai_review TEXT DEFAULT '',
    script_analyze_ok INTEGER DEFAULT 0,
    script_compliance_ok INTEGER DEFAULT 0,
    script_forbidden_ok INTEGER DEFAULT 0,
    script_detail TEXT DEFAULT '',
    word_count INTEGER DEFAULT 0,
    wc_ok INTEGER DEFAULT 0,
    compliance_ok INTEGER DEFAULT 0,
    forbidden_ok INTEGER DEFAULT 0,
    bcontrast_count INTEGER DEFAULT 0,
    tell_count INTEGER DEFAULT 0,
    judgment_groups INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, chapter_ref)
);

CREATE TABLE IF NOT EXISTS danger_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume TEXT NOT NULL,
    chapter_num INTEGER,
    danger_level TEXT DEFAULT 'low',
    core_danger TEXT DEFAULT '',
    content TEXT NOT NULL,
    rhythm_data TEXT DEFAULT '{}',
    foreshadowing_data TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, volume, chapter_num)
);

CREATE TABLE IF NOT EXISTS story_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL,
    record_key TEXT NOT NULL,
    record_value TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(novel_id, record_type, record_key)
);
CREATE INDEX IF NOT EXISTS idx_st_novel_type ON story_tracking(novel_id, record_type);

CREATE TABLE IF NOT EXISTS foreshadowing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '剧情',
    status TEXT DEFAULT 'pending',
    introduced_vol INTEGER DEFAULT 0,
    introduced_ch INTEGER DEFAULT 0,
    target_vol INTEGER DEFAULT 0,
    target_ch INTEGER DEFAULT 0,
    resolved_vol INTEGER DEFAULT 0,
    resolved_ch INTEGER DEFAULT 0,
    resolution_note TEXT DEFAULT '',
    priority TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT DEFAULT '配角',
    gender TEXT DEFAULT '',
    age TEXT DEFAULT '',
    identity TEXT DEFAULT '',
    personality TEXT DEFAULT '',
    appearance TEXT DEFAULT '',
    background TEXT DEFAULT '',
    current_status TEXT DEFAULT '',
    current_vol INTEGER DEFAULT 0,
    current_ch INTEGER DEFAULT 0,
    lifeline TEXT DEFAULT '',
    arc TEXT DEFAULT '',
    ending TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, name)
);

CREATE TABLE IF NOT EXISTS character_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    event_type TEXT DEFAULT '状态变更',
    description TEXT NOT NULL,
    vol INTEGER DEFAULT 0,
    ch INTEGER DEFAULT 0,
    chapter_ref TEXT DEFAULT '',
    source TEXT DEFAULT 'manual',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chars_novel ON characters(novel_id);
CREATE INDEX IF NOT EXISTS idx_chevents_char ON character_events(character_id);
CREATE TABLE IF NOT EXISTS world_building (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    domain TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    related_vol INTEGER DEFAULT 0,
    related_ch INTEGER DEFAULT 0,
    tags TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plot_arcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    type TEXT DEFAULT '主线',
    volume_start INTEGER DEFAULT 0,
    chapter_start INTEGER DEFAULT 0,
    volume_end INTEGER DEFAULT 0,
    chapter_end INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    milestones TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    priority TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pacing_control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume INTEGER DEFAULT 0,
    chapter_start INTEGER DEFAULT 0,
    chapter_end INTEGER DEFAULT 0,
    pace_type TEXT DEFAULT '过渡',
    intensity INTEGER DEFAULT 5,
    emotion_target TEXT DEFAULT '',
    word_budget_min INTEGER DEFAULT 2500,
    word_budget_max INTEGER DEFAULT 3500,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS revelation_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    info_type TEXT DEFAULT '世界观',
    reveal_volume INTEGER DEFAULT 0,
    reveal_chapter INTEGER DEFAULT 0,
    content TEXT DEFAULT '',
    audience_knows INTEGER DEFAULT 0,
    protagonist_knows INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wb_novel ON world_building(novel_id);
CREATE INDEX IF NOT EXISTS idx_wb_domain ON world_building(domain);
CREATE INDEX IF NOT EXISTS idx_pa_novel ON plot_arcs(novel_id);
CREATE INDEX IF NOT EXISTS idx_pc_novel ON pacing_control(novel_id);
CREATE INDEX IF NOT EXISTS idx_rs_novel ON revelation_schedule(novel_id);


-- ═══ New Domain Tables ═══

CREATE TABLE IF NOT EXISTS genre_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    rule_category TEXT NOT NULL DEFAULT '',
    rule_content TEXT NOT NULL DEFAULT '',
    is_required INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gr_novel ON genre_rules(novel_id);

CREATE TABLE IF NOT EXISTS story_volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    vol_num INTEGER NOT NULL DEFAULT 0,
    vol_name TEXT DEFAULT '',
    word_range TEXT DEFAULT '',
    goal TEXT DEFAULT '',
    conflict TEXT DEFAULT '',
    payoff TEXT DEFAULT '',
    foreshadowing TEXT DEFAULT '',
    status TEXT DEFAULT '待规划',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sv_novel ON story_volumes(novel_id);

CREATE TABLE IF NOT EXISTS volume_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    vol_num INTEGER NOT NULL DEFAULT 0,
    title TEXT DEFAULT '',
    plan_content TEXT NOT NULL DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, vol_num)
);
CREATE INDEX IF NOT EXISTS idx_vp_novel ON volume_plans(novel_id);

CREATE TABLE IF NOT EXISTS alias_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    category TEXT DEFAULT '',
    alias_name TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    scope TEXT DEFAULT '全书',
    first_chapter TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_an_novel ON alias_names(novel_id);

CREATE TABLE IF NOT EXISTS project_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    meta_key TEXT NOT NULL,
    meta_value TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, meta_key)
);
CREATE INDEX IF NOT EXISTS idx_pm_novel ON project_meta(novel_id);
"""

def migrate_v3():
    """No-op: v3 columns are already present in ORM schema via models_orm.py."""
    pass


def init_db():
    """Create tables via SQLAlchemy ORM (supports SQLite and MySQL)."""
    from repository import ensure_tables, get_repo
    ensure_tables()
    # Run init seed for config tables
    get_repo().init_config_seed()

# ═══════════════════════════════════════════════════════════════════════
# Sync from files
# ═══════════════════════════════════════════════════════════════════════

def count_words(text):
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english

def sync_novel_from_files(novel_name):
    """Sync a single novel's content from files to DB via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    if not os.path.isdir(novel_path):
        return {"error": f"小说目录不存在: {novel_path}"}

    repo = _get_repo()
    try:
        # Upsert novel record
        repo.upsert_novel(novel_name, title=novel_name, genre='')
        novel = repo.get_novel(novel_name)
        if not novel:
            return {"error": "Failed to create novel record"}
        novel_id = novel["id"]

        # Read project.md for metadata
        project_file = os.path.join(novel_path, "project.md")
        if os.path.exists(project_file):
            with open(project_file, encoding="utf-8") as f:
                content_text = f.read()
            title_match = re.search(r'#\s*(?:作品名|书名)[：:]\s*(.+)', content_text)
            title = title_match.group(1).strip() if title_match else novel_name
            genre_match = re.search(r'题材[：:]\s*(.+)', content_text)
            genre = genre_match.group(1).strip() if genre_match else ''
            repo.upsert_novel(novel_name, title=title, genre=genre)

        stats = {"outlines": 0, "chapters": 0, "reviews": 0, "danger_issues": 0}

        # Sync outlines
        outline_dir = os.path.join(novel_path, "outline")
        if os.path.exists(outline_dir):
            for fname in sorted(os.listdir(outline_dir)):
                if fname.endswith("-chapters.md"):
                    vol = fname.replace("-chapters.md", "")
                    fpath = os.path.join(outline_dir, fname)
                    with open(fpath, encoding="utf-8") as fh:
                        content_text = fh.read()
                    wc = count_words(content_text)
                    repo.upsert_outline(novel_name, vol, content_text, wc)
                    stats["outlines"] += 1

        # Sync chapters
        manuscript_dir = os.path.join(novel_path, "manuscript")
        if os.path.exists(manuscript_dir):
            for vol_dir in sorted(os.listdir(manuscript_dir)):
                vol_path = os.path.join(manuscript_dir, vol_dir)
                if not os.path.isdir(vol_path) or vol_dir.startswith('.'):
                    continue
                for ch_file in sorted(os.listdir(vol_path)):
                    if not ch_file.endswith(".md"):
                        continue
                    ch_path = os.path.join(vol_path, ch_file)
                    with open(ch_path, encoding="utf-8") as fh:
                        content_text = fh.read()
                    ch_num_match = re.search(r'ch-(\d+)', ch_file)
                    ch_num = int(ch_num_match.group(1)) if ch_num_match else 0
                    ch_ref = f"{vol_dir}/{ch_file.replace('.md', '')}"
                    wc = count_words(content_text)
                    content_hash = hashlib.md5(content_text.encode()).hexdigest()
                    title_match = re.search(r'^#\s+(.+)$', content_text, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else ''
                    repo.upsert_chapter(novel_name, ch_ref,
                        volume=vol_dir, chapter_num=ch_num, content=content_text,
                        title=title, word_count=wc, content_hash=content_hash)
                    stats["chapters"] += 1

        # Sync reviews
        reviews_dir = os.path.join(novel_path, "reviews")
        if os.path.exists(reviews_dir):
            for fname in sorted(os.listdir(reviews_dir)):
                if fname.endswith(".md"):
                    fpath = os.path.join(reviews_dir, fname)
                    with open(fpath, encoding="utf-8") as fh:
                        content_text = fh.read()
                    ch_ref_match = re.search(r'(ch-\d+)-review', fname)
                    ch_ref = ch_ref_match.group(1) if ch_ref_match else fname.replace(".md", "")
                    wc = count_words(content_text)
                    ai_review = ""
                    script_detail = ""
                    ai_section = False
                    script_section = False
                    for line in content_text.split("\n"):
                        if "AI审稿结果" in line:
                            ai_section = True; script_section = False; continue
                        if "脚本检查" in line:
                            ai_section = False; script_section = True; continue
                        if ai_section:
                            ai_review += line + "\n"
                        if script_section:
                            script_detail += line + "\n"
                    repo.upsert_review(novel_name, ch_ref,
                        ai_review=ai_review.strip(),
                        script_detail=script_detail.strip(),
                        word_count=wc)
                    stats["reviews"] += 1

        return {"success": True, "novel": novel_name, "stats": stats}
    except Exception as e:
        return {"error": str(e)}

def sync_all_novels():
    """Sync all novels from files to DB"""
    results = []
    if os.path.exists(NOVELS_ROOT):
        for d in sorted(os.listdir(NOVELS_ROOT)):
            if os.path.isdir(os.path.join(NOVELS_ROOT, d)) and not d.startswith("."):
                results.append(sync_novel_from_files(d))
    return results


def incremental_sync(novel_name, relative_path):
    """Sync a single file change to DB without full rescan.

    Uses file path to determine which table to update:
      "manuscript/vol-01/ch-0001.md" -> chapters table
      "outline/vol-01-chapters.md"   -> outlines table
      "reviews/ch-0001-review.md"    -> reviews table
    Falls back to full sync if path doesn't match known patterns.

    Returns:
        {"updated": bool, "table": str, "detail": str}
    """
    parts = relative_path.strip("/").split("/")

    if not parts:
        return {"updated": False, "table": "", "detail": "empty path"}

    # Manuscript chapters
    if parts[0] == "manuscript" and len(parts) == 2 and parts[1].endswith(".md"):
        volume = parts[0] + "/" + parts[1] if "/" in relative_path else parts[0]
        _sync_chapter_from_file(novel_name, volume_dir=parts[0], chapter_file=parts[1])
        return {"updated": True, "table": "chapters", "detail": f"synced {relative_path}"}

    # Outline files
    if parts[0] == "outline" and (parts[1].endswith("-chapters.md") or parts[1].endswith("-chapters.yaml") or parts[1].endswith("-chapters.yml")):
        vol_str = parts[1].replace("-chapters.md", "").replace("-chapters.yaml", "").replace("-chapters.yml", "")
        _sync_outline_from_file(novel_name, vol_str)
        return {"updated": True, "table": "outlines", "detail": f"synced {relative_path}"}

    # Review files
    if parts[0] == "reviews" and parts[1].endswith(".md"):
        ch_ref = parts[1].replace("-review.md", "").replace(".md", "")
        _sync_review_from_file(novel_name, ch_ref)
        return {"updated": True, "table": "reviews", "detail": f"synced {relative_path}"}

    # Characters file
    if relative_path == "characters.md":
        _sync_characters_from_file(novel_name)
        return {"updated": True, "table": "characters", "detail": "synced characters"}

    # World bible
    if relative_path == "world_bible.md":
        _sync_world_building_from_file(novel_name)
        return {"updated": True, "table": "world_building", "detail": "synced world_building"}

    # Fallback: full sync
    result = sync_novel_from_files(novel_name)
    if "error" in result:
        return {"updated": False, "table": "", "detail": result["error"]}
    return {"updated": True, "table": "full", "detail": "full sync performed"}


def _sync_chapter_from_file(novel_name, volume_dir=None, chapter_file=None):
    """Read single chapter file and upsert via repo."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    if not volume_dir or not chapter_file:
        return

    ch_path = os.path.join(novel_path, "manuscript", volume_dir, chapter_file) \
        if volume_dir and "manuscript" not in volume_dir \
        else os.path.join(novel_path, volume_dir, chapter_file) if volume_dir and chapter_file \
        else os.path.join(novel_path, chapter_file) if chapter_file else None

    if not ch_path or not os.path.exists(ch_path):
        return

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel:
        return

    with open(ch_path, encoding="utf-8") as fh:
        content = fh.read()

    vol_actual = volume_dir or "vol-01"
    ch_name = chapter_file or os.path.basename(ch_path)
    ch_num_match = re.search(r'ch-(\d+)', ch_name)
    ch_num = int(ch_num_match.group(1)) if ch_num_match else 0
    ch_ref = f"{vol_actual}/{ch_name.replace('.md', '')}"

    wc = count_words(content)
    content_hash = hashlib.md5(content.encode()).hexdigest()
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Check if content changed
    existing_hash = repo.get_chapter_content_hash(novel_name, ch_ref)
    if existing_hash and existing_hash == content_hash:
        return

    repo.upsert_chapter(novel_name, ch_ref,
        volume=vol_actual, chapter_num=ch_num, content=content,
        title=title, word_count=wc, content_hash=content_hash)


def _sync_outline_from_file(novel_name, volume_str):
    """Upsert a single outline file via repo."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    content = None

    for ext in ('.yaml', '.yml'):
        fpath = os.path.join(novel_path, "outline", f"{volume_str}-chapters{ext}")
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            break

    if content is None:
        fpath = os.path.join(novel_path, "outline", f"{volume_str}-chapters.md")
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
        else:
            return

    wc = count_words(content)
    _get_repo().upsert_outline(novel_name, volume_str, content, wc)


def _sync_review_from_file(novel_name, chapter_ref):
    """Upsert a single review file via repo."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "reviews", f"{chapter_ref}-review.md")
    if not os.path.exists(fpath):
        fpath = os.path.join(novel_path, "reviews", f"{chapter_ref}.md")
    if not os.path.exists(fpath):
        return

    with open(fpath, encoding="utf-8") as fh:
        content = fh.read()

    wc = count_words(content)
    ai_review = ""
    script_detail = ""
    ai_section = False
    script_section = False
    for line in content.split("\n"):
        if "AI审稿结果" in line:
            ai_section = True; script_section = False; continue
        if "脚本检查" in line:
            ai_section = False; script_section = True; continue
        if ai_section:
            ai_review += line + "\n"
        if script_section:
            script_detail += line + "\n"

    _get_repo().upsert_review(novel_name, chapter_ref,
        ai_review=ai_review.strip(), script_detail=script_detail.strip(),
        word_count=wc)


def _sync_characters_from_file(novel_name):
    """Re-init characters from file."""
    init_characters_from_files(novel_name)


def _sync_world_building_from_file(novel_name):
    """Re-init world building from file."""
    init_world_building_from_file(novel_name)


# ═══════════════════════════════════════════════════════════════════════
# Query helpers
# ═══════════════════════════════════════════════════════════════════════

def search_all(query, novel_name=None, limit=20):
    """Search across chapters, outlines, reviews via repository."""
    return _get_repo().search_all(query, novel_name=novel_name, limit=limit)
def get_novel_stats(novel_name):
    """Get aggregate statistics for a novel."""
    return _get_repo().get_novel_stats(novel_name)
def get_characters(novel_name, role=None):
    """List characters for a novel."""
    return _get_repo().list_characters(novel_name, role=role)


def get_character(novel_name, cid):
    """Get a single character by ID."""
    return _get_repo().get_character(novel_name, cid)


def add_character(novel_name, name, role="配角", **kwargs):
    """Add a new character."""
    return _get_repo().add_character(novel_name, name, role=role, **kwargs)


def update_character(cid, **kwargs):
    """Update a character."""
    return _get_repo().update_character(cid, **kwargs)


def delete_character(cid):
    """Delete a character."""
    _get_repo().delete_character(cid)


def add_character_event(novel_name, cid, description, event_type="状态变更",
                         vol=0, ch=0, chapter_ref="", source="manual"):
    """Add a character event."""
    return _get_repo().add_character_event(
        novel_name, cid, description, event_type=event_type,
        vol=vol, ch=ch, chapter_ref=chapter_ref, source=source)


def get_character_events(novel_name, cid, limit=50):
    """Get events for a character."""
    return _get_repo().list_character_events(cid, limit=limit)


def add_foreshadowing(novel_name, name, description="", category="剧情",
                       introduced_vol=0, introduced_ch=0, target_vol=0,
                       target_ch=0, priority="normal"):
    """Add a foreshadowing entry."""
    return _get_repo().add_foreshadowing(
        novel_name, name, description=description, category=category,
        introduced_vol=introduced_vol, introduced_ch=introduced_ch,
        target_vol=target_vol, target_ch=target_ch, priority=priority)
def get_foreshadowing(novel_name, status=None, volume=None, limit=100):
    """List foreshadowing entries."""
    return _get_repo().list_foreshadowing(novel_name, status=status, volume=volume, limit=limit)
def get_unresolved_foreshadowing(novel_name, current_vol=None, current_ch=None):
    """Get unresolved foreshadowing to resolve soon."""
    return _get_repo().get_unresolved_foreshadowing(
        novel_name, current_vol=current_vol, current_ch=current_ch)
def update_foreshadowing(fid, **kwargs):
    """Update a foreshadowing entry."""
    return _get_repo().update_foreshadowing(fid, **kwargs)
def delete_foreshadowing(fid):
    """Delete a foreshadowing entry."""
    _get_repo().delete_foreshadowing(fid)
def resolve_foreshadowing(fid, vol, ch, note=""):
    """Mark a foreshadowing as resolved."""
    _get_repo().resolve_foreshadowing(fid, vol, ch, note=note)
def init_foreshadowing_from_outline(novel_name):
    """Scan the outline for implicit foreshadowing points via repository."""
    import glob
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "无大纲目录"}

    patterns = [
        (r'伏笔[：:]?\s*(.+)', '剧情'), (r'铺垫[：:]?\s*(.+)', '剧情'),
        (r'暗示[：:]?\s*(.+)', '剧情'), (r'后续.*?出现[：:]?\s*(.+)', '角色'),
        (r'隐藏[：:]?\s*(.+)', '剧情'), (r'秘密[：:]?\s*(.+)', '世界观'),
        (r'真相[：:]?\s*(.+)', '世界观'), (r'真正.*?是[：:]?\s*(.+)', '身份'),
        (r'叶微伏笔[：:]?\s*(.+)', '女主'),
    ]

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel:
        return {"created": 0, "message": "小说不存在"}

    created = 0
    for fpath in sorted(glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        for m in re.finditer(r'第(\d+)章', text):
            ch_num = int(m.group(1))
            ch_start = m.start()
            next_ch = re.search(r'第(\d+)章', text[ch_start+5:])
            ch_end = ch_start + 5 + next_ch.start() if next_ch else len(text)
            ch_section = text[ch_start:ch_end]

            for pattern, cat in patterns:
                for pm in re.finditer(pattern, ch_section):
                    desc = pm.group(1).strip()[:200]
                    if len(desc) > 5:
                        existing_fs = repo.list_foreshadowing(novel_name)
                        if not any(desc[:30] in fs.get('name', '') for fs in existing_fs):
                            repo.add_foreshadowing(novel_name,
                                name=f"第{ch_num}章伏笔: {desc[:50]}",
                                description=desc, category=cat,
                                introduced_vol=vol_num, introduced_ch=ch_num,
                                target_vol=vol_num+1 if vol_num > 0 else vol_num)
                            created += 1
    return {"created": created, "message": f"从大纲初始化 {created} 条伏笔"}
def init_characters_from_files(novel_name):
    """Parse characters.md into characters table via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    chars_path = os.path.join(novel_path, "characters.md")
    if not os.path.exists(chars_path):
        return {"created": 0, "message": "characters.md not found"}

    with open(chars_path, 'r', encoding='utf-8') as f:
        text = f.read()

    skip_kw = ['背景', '身世', '核心特质', '系统宿主', '异能', '修真传承',
               '成长弧线', '对抗历程', '重生能力', '关系演变', '终极命运',
               '乐园相关', '容器宿主', '破晓联盟', '天骄', '详解', '相关']

    def is_char_name(n):
        n = n.strip()
        for sep in ['（', '(', '——', '—']:
            if sep in n: n = n[:n.index(sep)].strip()
        if len(n) > 12 or len(n) < 1: return False
        if '：' in n or ':' in n: return False
        if n.endswith('天骄') or n.endswith('相关') or n.endswith('宿主'): return False
        for kw in skip_kw:
            if kw in n: return False
        return True

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel:
        return {"created": 0, "message": "小说不存在"}

    created = 0
    for m in re.finditer(r'^(#{3,4})\s+(.+?)$', text, re.MULTILINE):
        name = m.group(2).strip()
        display_name = name
        for sep in ['（', '(', '——', '—']:
            if sep in display_name: display_name = display_name[:display_name.index(sep)].strip()
        if not is_char_name(name): continue

        role = "配角"
        prev_text = text[:m.start()]
        headings = list(re.finditer(r'^##\s+(.+?)$', prev_text, re.MULTILINE))
        if headings:
            h = headings[-1].group(1).strip()
            if "主角" in h and "配角" not in h: role = "主角"
            elif "女主" in h: role = "女主"
            elif "反派" in h: role = "反派"

        level = len(m.group(1))
        rest = text[m.end():]
        next_m = re.search(r'^#{1,' + str(level) + r'}\s', rest, re.MULTILINE)
        section = rest[:next_m.start()] if next_m else rest

        identity = ""; personality = ""; background = ""; status = ""
        for row in re.finditer(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', section):
            k = row.group(1).strip(); v = row.group(2).strip()
            if k in ('身份','职业','现状'): identity = v[:300]
            elif k in ('特质','性格'): personality += v[:200] + "; "
            elif k == '背景': background = v[:500]
            elif k == '异能': status = "异能: " + v[:100]
            elif k == '代号': identity = "代号: " + v[:100]
        if not status:
            status = "初始状态"

        existing = repo.list_characters(novel_name)
        if not any(c.get('name') == display_name for c in existing):
            repo.add_character(novel_name, display_name, role=role,
                identity=identity, personality=personality[:500],
                background=background, current_status=status)
            created += 1

    return {"created": created, "message": f"Initialized {created} characters from characters.md"}
def init_world_building_from_file(novel_name):
    """Parse world_bible.md into world_building table via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    wb_path = os.path.join(novel_path, "world_bible.md")
    if not os.path.exists(wb_path):
        return {"created": 0, "message": "world_bible.md not found"}

    with open(wb_path, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0, "message": "小说不存在"}

    domain_map = {
        '力量体系': '力量体系', '修炼': '力量体系', '等级': '力量体系', '功法': '力量体系',
        '地图': '地图', '地域': '地图', '地理': '地图', '世界': '地图',
        '历史': '历史', '种族': '种族', '组织': '组织', '势力': '组织',
        '规则': '规则', '法则': '规则', '禁忌': '禁忌', '禁地': '禁忌', '科技': '科技',
    }

    created = 0
    existing_entries = repo.list_world_building(novel_name)
    existing_names = {e.get('name', '') for e in existing_entries}

    for m in re.finditer(r'^##\s+(.+?)$', text, re.MULTILINE):
        heading = m.group(1).strip()
        domain = "其他"
        for kw, dm in domain_map.items():
            if kw in heading: domain = dm; break

        start = m.end()
        next_sec = re.search(r'\n##\s', text[start:])
        sect = text[start:start + next_sec.start()].strip() if next_sec else text[start:].strip()

        if len(sect) > 10:
            items = re.findall(r'^[-*]\s+(.+)$', sect, re.MULTILINE)
            if items:
                for item in items[:10]:
                    name = item[:80].strip()
                    if name not in existing_names:
                        repo.add_world_building(novel_name, domain, name, item)
                        existing_names.add(name)
                        created += 1
            else:
                name = heading[:80]
                if name not in existing_names:
                    repo.add_world_building(novel_name, domain, name, sect[:2000])
                    existing_names.add(name)
                    created += 1

    return {"created": created, "message": f"Initialized {created} world_building entries"}
def init_plot_arcs_from_file(novel_name):
    """Parse full_story_arc.md into plot_arcs table via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    arc_path = os.path.join(novel_path, "full_story_arc.md")
    if not os.path.exists(arc_path):
        return {"created": 0, "message": "full_story_arc.md not found"}

    with open(arc_path, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    created = 0
    existing = {a.get('name', '') for a in repo.list_plot_arcs(novel_name)}

    for m in re.finditer(r'##\s+(.+?)$', text, re.MULTILINE):
        heading = m.group(1).strip()
        start = m.end()
        next_sec = re.search(r'\n##\s', text[start:])
        summary = text[start:start + next_sec.start()].strip() if next_sec else text[start:].strip()

        vol_match = re.search(r'第([一二三四五六七八九十\d]+)卷', heading)
        vol_num = _parse_chinese_vol(vol_match.group(1)) if vol_match else 0

        arc_type = "主线"
        if "支线" in heading: arc_type = "支线"
        elif "感情" in heading or "女主" in heading: arc_type = "感情线"
        elif "成长" in heading: arc_type = "成长线"

        name = heading[:80]
        if name not in existing:
            repo.add_plot_arc(novel_name, name, arc_type=arc_type,
                volume_start=vol_num, volume_end=vol_num, summary=summary[:500],
                milestones='[]', status='active', priority='normal')
            existing.add(name)
            created += 1

    return {"created": created, "message": f"Initialized {created} plot arcs"}
def _parse_chinese_vol(s):
    """Parse Chinese volume number: 一→1, 二→2, etc."""
    chinese_nums = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    if s in chinese_nums: return chinese_nums[s]
    try: return int(s)
    except: return 0


def init_pacing_from_outline(novel_name):
    """Parse outline for pacing control entries via repository."""
    import glob as _glob
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "no outline directory"}

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    created = 0
    for fpath in sorted(_glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        # Format 1: Individual chapter markers
        for cm in re.finditer(r'第(\d+)章', text):
            ch_num = int(cm.group(1))
            ch_start = cm.start()
            next_ch = re.search(r'第(\d+)章', text[ch_start+5:])
            ch_end = ch_start + 5 + next_ch.start() if next_ch else len(text)
            section = text[ch_start:ch_end]

            pace_type = "过渡"; emotion = ""; intensity = 5
            pace_m = re.search(r'节奏[：:]\s*(.+)', section)
            if pace_m:
                p = pace_m.group(1).strip()
                if '高潮' in p: pace_type = '高潮'; intensity = 9
                elif '铺垫' in p: pace_type = '铺垫'; intensity = 4
                elif '过渡' in p: pace_type = '过渡'; intensity = 5
                elif '释缓' in p: pace_type = '释缓'; intensity = 3

            emo_m = re.search(r'情感[目标]*[：:]\s*(.+)', section)
            if emo_m:
                e = emo_m.group(1).strip()
                for kw in ['爽','虐','悬','燃','暖','惧','压抑','期待','惊喜','好奇']:
                    if kw in e: emotion = kw; break

            try:
                repo.add_pacing(novel_name, vol_num, ch_num, ch_num,
                    pace_type=pace_type, intensity=intensity, emotion_target=emotion)
                created += 1
            except Exception:
                pass  # duplicate, skip

        # Format 2: Table-based
        table_row_re = re.compile(
            r'^\|\s*(\d{3})\s*[-–]\s*(\d{3})\s*\|\s*([^|]+)\s*\|'
            r'[^|]*\|[^|]*\|\s*([^|]+?)\s*\|', re.MULTILINE)
        for rm in table_row_re.finditer(text):
            ch_start = int(rm.group(1)); ch_end = int(rm.group(2))
            pace_label = rm.group(3).strip()
            emotion_text = rm.group(4).strip()

            pace_type = "过渡"; intensity = 5
            if any(kw in pace_label for kw in ['高潮','高压','危机']):
                pace_type = '高潮'; intensity = 9
            elif any(kw in pace_label for kw in ['铺垫','伏笔']):
                pace_type = '铺垫'; intensity = 4
            elif any(kw in pace_label for kw in ['过渡','桥接']):
                pace_type = '过渡'; intensity = 5
            elif any(kw in pace_label for kw in ['释缓','放松','日常']):
                pace_type = '释缓'; intensity = 3

            emotion = ""
            for kw in ['爽','虐','悬','燃','暖','惧','压抑','期待','惊喜','好奇','留白']:
                if kw in emotion_text: emotion = kw; break

            try:
                repo.add_pacing(novel_name, vol_num, ch_start, ch_end,
                    pace_type=pace_type, intensity=intensity, emotion_target=emotion)
                created += 1
            except Exception:
                pass

    return {"created": created, "message": f"Initialized {created} pacing entries"}
def init_revelation_from_outline(novel_name):
    """Parse outline for information release schedule via repository."""
    import glob as _glob
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "no outline directory"}

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    created = 0
    for fpath in sorted(_glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        # Format 1: Individual chapter markers
        for pattern, info_type in [
            (r'信息释放[：:]\s*(.+)', '世界观'),
            (r'伏笔揭示[：:]\s*(.+)', '伏笔揭示'),
            (r'揭示[：:]\s*(.+)', '角色秘密'),
            (r'真相[：:]\s*(.+)', '世界观'),
        ]:
            for m in re.finditer(pattern, text):
                info_content = m.group(1).strip()[:300]
                before = text[:m.start()]
                ch_matches = list(re.finditer(r'第(\d+)章', before))
                ch_num = int(ch_matches[-1].group(1)) if ch_matches else 0

                name = f"第{vol_num}卷第{ch_num}章: {info_content[:60]}"
                try:
                    repo.add_revelation(novel_name, name, info_type=info_type,
                        reveal_volume=vol_num, reveal_chapter=ch_num, content=info_content)
                    created += 1
                except Exception:
                    pass

        # Format 2: Table-based
        table_row_re = re.compile(
            r'^\|\s*(\d{3})\s*[-–]\s*(\d{3})\s*\|'
            r'[^|]*\|[^|]*\|\s*([^|]+?)\s*\|', re.MULTILINE)
        for rm in table_row_re.finditer(text):
            ch_start = int(rm.group(1)); ch_end = int(rm.group(2))
            info_content = rm.group(3).strip()
            if not info_content or len(info_content) < 3: continue

            name = f"第{vol_num}卷第{ch_start}-{ch_end}章: {info_content[:60]}"
            info_type = "世界观"
            if any(kw in info_content for kw in ['身份','秘密','真实']): info_type = "角色秘密"
            elif any(kw in info_content for kw in ['伏笔','铺垫','揭示']): info_type = "伏笔揭示"
            elif any(kw in info_content for kw in ['规则','设定','体系']): info_type = "世界观"

            try:
                repo.add_revelation(novel_name, name, info_type=info_type,
                    reveal_volume=vol_num, reveal_chapter=ch_start, content=info_content)
                created += 1
            except Exception:
                pass

    return {"created": created, "message": f"Initialized {created} revelation entries"}
def init_genre_rules_from_file(novel_name):
    """Parse genre_bible.md for genre rules via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "genre_bible.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "genre_bible.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    repo.clear_genre_rules(novel_name)
    created = 0

    sections = re.split(r'\n##\s+', text)
    for sec in sections[1:]:
        lines = sec.strip().split('\n')
        category = lines[0].strip()
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- '):
                rule = line[2:].strip()
                repo.add_genre_rule(novel_name, category, rule)
                created += 1

    return {"created": created, "message": f"Initialized {created} genre rules"}
def init_story_volumes_from_file(novel_name):
    """Parse full_story_arc.md for volume structure via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "full_story_arc.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "full_story_arc.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    repo.clear_story_volumes(novel_name)
    created = 0

    for m in re.finditer(
        r'\|\s*第\s*(\d+)\s*卷[：:]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        text
    ):
        repo.add_story_volume(novel_name, int(m.group(1)),
            vol_name=m.group(2).strip(), word_range=m.group(3).strip(),
            goal=m.group(4).strip(), conflict=m.group(5).strip(),
            payoff=m.group(6).strip(), foreshadowing=m.group(7).strip(),
            status=m.group(8).strip())
        created += 1

    return {"created": created, "message": f"Initialized {created} story volumes"}
def init_volume_plans_from_files(novel_name):
    """Parse volume_plan.md and volume_plan/vol-XX.md via repository."""
    import glob as _glob
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    vp_dir = os.path.join(novel_path, "volume_plan")
    if not os.path.exists(vp_dir):
        return {"created": 0, "message": "no volume_plan directory"}

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    repo.clear_volume_plans(novel_name)
    created = 0

    for fpath in sorted(_glob.glob(os.path.join(vp_dir, "vol-*.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            plan_text = f.read()
        title = ""
        tm = re.search(r'^#\s+(.+)', plan_text, re.MULTILINE)
        if tm: title = tm.group(1).strip()
        repo.upsert_volume_plan(novel_name, vol_num, title=title,
            plan_content=plan_text, word_count=len(plan_text))
        created += 1

    root_plan = os.path.join(novel_path, "volume_plan.md")
    if os.path.exists(root_plan):
        with open(root_plan, 'r', encoding='utf-8') as f:
            plan_text = f.read()
        repo.upsert_volume_plan(novel_name, 0, title="卷规划总览",
            plan_content=plan_text, word_count=len(plan_text))
        created += 1

    return {"created": created, "message": f"Initialized {created} volume plans"}
def init_alias_names_from_file(novel_name):
    """Parse alias_registry.md for alias names via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "alias_registry.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "alias_registry.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    repo.clear_alias_names(novel_name)
    created = 0

    for m in re.finditer(
        r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        text
    ):
        row = [m.group(i).strip() for i in range(1, 6)]
        if row[0] in ('类别', '---', ':---'): continue
        repo.add_alias_name(novel_name, row[0], row[1], row[2], row[3], row[4])
        created += 1

    return {"created": created, "message": f"Initialized {created} alias names"}
def init_project_meta_from_file(novel_name):
    """Parse project.md for project metadata via repository."""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "project.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "project.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return {"created": 0}

    repo.clear_project_meta(novel_name)
    created = 0

    for m in re.finditer(r'^-\s*(.+?)[：:]\s*(.+)$', text, re.MULTILINE):
        key = m.group(1).strip()
        value = m.group(2).strip()
        repo.upsert_project_meta(novel_name, key, value)
        created += 1

    return {"created": created, "message": f"Initialized {created} project meta entries"}
def init_all_from_files(novel_name):
    """Orchestrate full initialization from all files via repository."""
    results = {'success': True, 'tables': {}, 'errors': []}
    init_funcs = {
        'world_building': init_world_building_from_file,
        'plot_arcs': init_plot_arcs_from_file,
        'pacing_control': init_pacing_from_outline,
        'revelation_schedule': init_revelation_from_outline,
        'characters': init_characters_from_files,
        'foreshadowing': init_foreshadowing_from_outline,
        'genre_rules': init_genre_rules_from_file,
        'story_volumes': init_story_volumes_from_file,
        'volume_plans': init_volume_plans_from_files,
        'alias_names': init_alias_names_from_file,
        'project_meta': init_project_meta_from_file,
    }
    repo = _get_repo()
    for table_name, func in init_funcs.items():
        try:
            result = func(novel_name)
            created = result.get('created', 0)
            if created == 0 and table_name != 'foreshadowing':
                existing = repo.list_novels()  # just check repo is alive
            results['tables'][table_name] = created
        except Exception as e:
            results['errors'].append(f"{table_name}: {str(e)}")
            results['tables'][table_name] = 0
    results['success'] = len(results['errors']) == 0
    return results
def auto_update_after_save(novel_name, volume, chapter_num, content):
    """Auto-update state after a chapter is saved via repository."""
    import json as _json
    repo = _get_repo()
    novel = repo.get_novel(novel_name)
    if not novel: return
    nid = novel['id']
    volume_str = f"vol-{volume:02d}"

    # 1. Update characters: detect appearances from content
    characters = repo.list_characters(novel_name)
    appeared = [c['name'] for c in characters if c.get('name') and c['name'] in content]
    if appeared:
        repo.update_chapter_metadata(novel_name, volume_str, chapter_num,
            characters_appeared=_json.dumps(appeared))

    # 2. Check foreshadowing: note items whose target chapter is reached
    pending_fs = repo.list_pending_foreshadowing(novel_name)
    for f in pending_fs:
        tv = f.get('target_vol', 0)
        tc = f.get('target_ch', 0)
        if tv > 0 and tv == volume and tc > 0 and tc == chapter_num:
            existing_note = f.get('resolution_note', '') or ''
            new_note = existing_note + f' [到达目标第{volume}卷第{chapter_num}章，等待填坑]'
            repo.resolve_foreshadowing(f['id'], volume, chapter_num, note=new_note)

    # 3. Mark foreshadowing as touched if referenced in content
    touched = [f['id'] for f in pending_fs if f.get('name') and f['name'] in content]
    if touched:
        repo.update_chapter_metadata(novel_name, volume_str, chapter_num,
            foreshadowing_touched=_json.dumps(touched))

    # 4. Auto-discover new foreshadowing hints
    _discover_foreshadowing_hints_internal(repo, novel_name, volume, chapter_num, content)

    # 5. Detect "forgotten" foreshadowing
    _find_forgotten_foreshadowing_internal(repo, nid, volume, chapter_num, content)

def _get_novel_id(conn, novel_name):
    """Return novel id by name, or None if not found."""
    row = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    return row['id'] if row else None

def upsert_chapter_outline(novel_name, volume, chapter_num, data):
    """Insert or update a single chapter outline.
    data: {title, function:[], core_events, foreshadowing:[], ending_hook, is_danger_scene, word_count}
    """
    import json
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
        'function': __import__('json').loads(row['function'] or '[]'),
        'core_events': row['core_events'],
        'foreshadowing': __import__('json').loads(row['foreshadowing'] or '[]'),
        'ending_hook': row['ending_hook'],
        'is_danger_scene': bool(row['is_danger_scene']),
        'word_count': row['word_count'],
        'updated_at': row['updated_at'],
    }


# ─── Danger Issues ───────────────────────────────────────────────────────────

def upsert_danger_issue(novel_name, volume, chapter_num, data):
    """Insert or update a danger issue record.
    data: {danger_level, core_danger, content, rhythm_data, foreshadowing_data}
    """
    import json
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        raise ValueError(f"Novel not found: {novel_name}")
    conn.execute("""
        INSERT INTO danger_issues (novel_id, volume, chapter_num, danger_level,
            core_danger, content, rhythm_data, foreshadowing_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, volume, chapter_num) DO UPDATE SET
            danger_level=excluded.danger_level, core_danger=excluded.core_danger,
            content=excluded.content, rhythm_data=excluded.rhythm_data,
            foreshadowing_data=excluded.foreshadowing_data
    """, (nid, volume, chapter_num,
          data.get('danger_level', 'low'),
          data.get('core_danger', ''),
          data.get('content', ''),
          json.dumps(data.get('rhythm_data', {})),
          json.dumps(data.get('foreshadowing_data', []))))
    conn.commit()
    conn.close()


def get_danger_issues(novel_name, volume):
    """Return all danger issues for a volume."""
    import json
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        return []
    rows = conn.execute("""
        SELECT chapter_num, danger_level, core_danger, content, rhythm_data, foreshadowing_data
        FROM danger_issues
        WHERE novel_id=? AND volume=?
        ORDER BY chapter_num
    """, (nid, volume)).fetchall()
    conn.close()
    return [_parse_di_row(r) for r in rows]


def _parse_di_row(row):
    import json
    return {
        'chapter_num': row['chapter_num'],
        'danger_level': row['danger_level'],
        'core_danger': row['core_danger'],
        'content': row['content'],
        'rhythm_data': json.loads(row['rhythm_data'] or '{}'),
        'foreshadowing_data': json.loads(row['foreshadowing_data'] or '[]'),
    }


# ─── Story Tracking ─────────────────────────────────────────────────────────────

def upsert_story_tracking(novel_name, record_type, record_key, record_value):
    """Upsert a single story tracking record."""
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        raise ValueError(f"Novel not found: {novel_name}")
    conn.execute("""
        INSERT INTO story_tracking (novel_id, record_type, record_key, record_value, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(novel_id, record_type, record_key) DO UPDATE SET
            record_value=excluded.record_value, updated_at=datetime('now')
    """, (nid, record_type, record_key, record_value))
    conn.commit()
    conn.close()


def get_story_tracking(novel_name, record_type=None):
    """Return story tracking records. If record_type is None, return all."""
    conn = get_db()
    nid = _get_novel_id(conn, novel_name)
    if nid is None:
        return []
    if record_type:
        rows = conn.execute("""
            SELECT record_type, record_key, record_value, updated_at
            FROM story_tracking WHERE novel_id=? AND record_type=?
            ORDER BY record_key
        """, (nid, record_type)).fetchall()
    else:
        rows = conn.execute("""
            SELECT record_type, record_key, record_value, updated_at
            FROM story_tracking WHERE novel_id=?
            ORDER BY record_type, record_key
        """, (nid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]