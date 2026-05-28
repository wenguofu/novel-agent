"""
Content Database — SQLite + FTS5 full-text search for novel content.

Tables: novels, outlines, chapters, reviews, danger_issues
All tables have FTS5 virtual tables for full-text search.
"""

import hashlib
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.db")
NOVELS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "novels")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

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
    UNIQUE(novel_id, chapter_ref, created_at)
);

CREATE TABLE IF NOT EXISTS danger_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    volume TEXT NOT NULL,
    chapter_num INTEGER,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(novel_id, volume, chapter_num)
);

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
    updated_at TEXT DEFAULT (datetime('now'))
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



-- FTS5 virtual tables for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS chapters_fts USING fts5(
    title, content, content=chapters, content_rowid=id
);

CREATE VIRTUAL TABLE IF NOT EXISTS outlines_fts USING fts5(
    content, content=outlines, content_rowid=id
);

CREATE VIRTUAL TABLE IF NOT EXISTS reviews_fts USING fts5(
    ai_review, script_detail, content=reviews, content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS chapters_ai AFTER INSERT ON chapters BEGIN
    INSERT INTO chapters_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;
CREATE TRIGGER IF NOT EXISTS chapters_ad AFTER DELETE ON chapters BEGIN
    INSERT INTO chapters_fts(chapters_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
END;
CREATE TRIGGER IF NOT EXISTS chapters_au AFTER UPDATE ON chapters BEGIN
    INSERT INTO chapters_fts(chapters_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
    INSERT INTO chapters_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS outlines_ai AFTER INSERT ON outlines BEGIN
    INSERT INTO outlines_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS outlines_ad AFTER DELETE ON outlines BEGIN
    INSERT INTO outlines_fts(outlines_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS outlines_au AFTER UPDATE ON outlines BEGIN
    INSERT INTO outlines_fts(outlines_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO outlines_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS reviews_ai AFTER INSERT ON reviews BEGIN
    INSERT INTO reviews_fts(rowid, ai_review, script_detail) VALUES (new.id, new.ai_review, new.script_detail);
END;
CREATE TRIGGER IF NOT EXISTS reviews_ad AFTER DELETE ON reviews BEGIN
    INSERT INTO reviews_fts(reviews_fts, rowid, ai_review, script_detail) VALUES('delete', old.id, old.ai_review, old.script_detail);
END;
CREATE TRIGGER IF NOT EXISTS reviews_au AFTER UPDATE ON reviews BEGIN
    INSERT INTO reviews_fts(reviews_fts, rowid, ai_review, script_detail) VALUES('delete', old.id, old.ai_review, old.script_detail);
    INSERT INTO reviews_fts(rowid, ai_review, script_detail) VALUES (new.id, new.ai_review, new.script_detail);
END;

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
    """Add v3 extended columns to existing tables (idempotent)"""
    conn = get_db()
    try:
        # characters: emotional_state, ability_level, relationship_map
        for col, col_type in [
            ('emotional_state', "TEXT DEFAULT ''"),
            ('ability_level', "TEXT DEFAULT ''"),
            ('relationship_map', "TEXT DEFAULT '[]'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE characters ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # foreshadowing: hint_method, reveal_method, is_dark
        for col, col_type in [
            ('hint_method', "TEXT DEFAULT ''"),
            ('reveal_method', "TEXT DEFAULT ''"),
            ('is_dark', "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE foreshadowing ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # chapters: pace_type, emotional_beat, foreshadowing_touched, characters_appeared
        for col, col_type in [
            ('pace_type', "TEXT DEFAULT ''"),
            ('emotional_beat', "TEXT DEFAULT ''"),
            ('foreshadowing_touched', "TEXT DEFAULT '[]'"),
            ('characters_appeared', "TEXT DEFAULT '[]'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE chapters ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # characters v3.1: 8-dimension profile fields
        for col, col_type in [
            ('desire', "TEXT DEFAULT ''"),
            ('fear', "TEXT DEFAULT ''"),
            ('lie', "TEXT DEFAULT ''"),
            ('truth', "TEXT DEFAULT ''"),
            ('ability_curve', "TEXT DEFAULT ''"),
            ('ability_cost', "TEXT DEFAULT ''"),
            ('emotion_curve', "TEXT DEFAULT ''"),
            ('dilemma', "TEXT DEFAULT ''"),
            ('mirror', "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE characters ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        # reviews v3.1: quality tracking columns (BUG-01/02 fix)
        for col, col_type in [
            ('wc_ok', "INTEGER DEFAULT 0"),
            ('compliance_ok', "INTEGER DEFAULT 0"),
            ('forbidden_ok', "INTEGER DEFAULT 0"),
            ('bcontrast_count', "INTEGER DEFAULT 0"),
            ('tell_count', "INTEGER DEFAULT 0"),
            ('judgment_groups', "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE reviews ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if not exist, then apply v3 migrations"""
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    migrate_v3()

# ═══════════════════════════════════════════════════════════════════════
# Sync from files
# ═══════════════════════════════════════════════════════════════════════

def count_words(text):
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english

def sync_novel_from_files(novel_name):
    """Sync a single novel's content from files to DB"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    if not os.path.isdir(novel_path):
        return {"error": f"小说目录不存在: {novel_path}"}

    conn = get_db()
    try:
        # Insert/update novel record
        conn.execute("""INSERT INTO novels (name, title, genre, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET updated_at=datetime('now')""",
            (novel_name, novel_name, ''))

        novel_id = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()["id"]

        # Read project.md for metadata
        project_file = os.path.join(novel_path, "project.md")
        if os.path.exists(project_file):
            with open(project_file, encoding="utf-8") as f:
                content = f.read()
            # Extract title
            title_match = re.search(r'#\s*(?:作品名|书名)[：:]\s*(.+)', content)
            title = title_match.group(1).strip() if title_match else novel_name
            genre_match = re.search(r'题材[：:]\s*(.+)', content)
            genre = genre_match.group(1).strip() if genre_match else ''
            conn.execute("UPDATE novels SET title=?, genre=? WHERE id=?", (title, genre, novel_id))

        stats = {"outlines": 0, "chapters": 0, "reviews": 0, "danger_issues": 0}

        # Sync outlines
        outline_dir = os.path.join(novel_path, "outline")
        if os.path.exists(outline_dir):
            for f in sorted(os.listdir(outline_dir)):
                if f.endswith("-chapters.md"):
                    vol = f.replace("-chapters.md", "")
                    fpath = os.path.join(outline_dir, f)
                    with open(fpath, encoding="utf-8") as fh:
                        content = fh.read()
                    wc = count_words(content)
                    conn.execute("""INSERT INTO outlines (novel_id, volume, content, word_count, updated_at)
                        VALUES (?, ?, ?, ?, datetime('now'))
                        ON CONFLICT(novel_id, volume) DO UPDATE SET content=excluded.content, word_count=excluded.word_count, updated_at=datetime('now')""",
                        (novel_id, vol, content, wc))
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
                        content = fh.read()
                    ch_num_match = re.search(r'ch-(\d+)', ch_file)
                    ch_num = int(ch_num_match.group(1)) if ch_num_match else 0
                    ch_ref = f"{vol_dir}/{ch_file.replace('.md', '')}"
                    wc = count_words(content)
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    # Extract title from first heading
                    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else ''
                    conn.execute("""INSERT INTO chapters (novel_id, volume, chapter_num, chapter_ref, content, title, word_count, content_hash, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                        ON CONFLICT(novel_id, chapter_ref) DO UPDATE SET content=excluded.content, title=excluded.title, word_count=excluded.word_count, content_hash=excluded.content_hash, updated_at=datetime('now')""",
                        (novel_id, vol_dir, ch_num, ch_ref, content, title, wc, content_hash))
                    stats["chapters"] += 1

        # Sync reviews
        reviews_dir = os.path.join(novel_path, "reviews")
        if os.path.exists(reviews_dir):
            for f in sorted(os.listdir(reviews_dir)):
                if f.endswith(".md"):
                    fpath = os.path.join(reviews_dir, f)
                    with open(fpath, encoding="utf-8") as fh:
                        content = fh.read()
                    ch_ref_match = re.search(r'(ch-\d+)-review', f)
                    ch_ref = ch_ref_match.group(1) if ch_ref_match else f.replace(".md", "")
                    wc = count_words(content)
                    # Extract review data
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
                    conn.execute("""INSERT INTO reviews (novel_id, chapter_ref, ai_review, script_detail, word_count, created_at)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                        ON CONFLICT(novel_id, chapter_ref, created_at) DO NOTHING""",
                        (novel_id, ch_ref, ai_review.strip(), script_detail.strip(), wc))
                    stats["reviews"] += 1

        conn.commit()
        return {"success": True, "novel": novel_name, "stats": stats}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        conn.close()

def sync_all_novels():
    """Sync all novels from files to DB"""
    results = []
    if os.path.exists(NOVELS_ROOT):
        for d in sorted(os.listdir(NOVELS_ROOT)):
            if os.path.isdir(os.path.join(NOVELS_ROOT, d)) and not d.startswith("."):
                results.append(sync_novel_from_files(d))
    return results

# ═══════════════════════════════════════════════════════════════════════
# Query helpers
# ═══════════════════════════════════════════════════════════════════════

def search_all(query, novel_name=None, limit=20):
    """Full-text search across chapters, outlines, reviews
    Falls back to LIKE search when FTS5 can't match (Chinese text without spaces)
    """
    conn = get_db()
    results = {"chapters": [], "outlines": [], "reviews": []}
    try:
        # Build novel filter
        novel_filter_sql = ""
        novel_params = []
        if novel_name:
            novel_filter_sql = "AND n.id = (SELECT id FROM novels WHERE name=?)"
            novel_params = [novel_name]

        # Try FTS5 first
        try:
            # Search chapters via FTS5
            rows = conn.execute(f"""
                SELECT c.chapter_ref, c.title, c.word_count, c.volume, n.name as novel_name,
                       snippet(chapters_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
                FROM chapters_fts f
                JOIN chapters c ON c.id = f.rowid
                JOIN novels n ON n.id = c.novel_id
                WHERE chapters_fts MATCH ? {novel_filter_sql}
                ORDER BY rank LIMIT ?
            """, [query] + novel_params + [limit]).fetchall()
            results["chapters"] = [dict(r) for r in rows]

            # Search outlines via FTS5
            rows = conn.execute(f"""
                SELECT o.volume, n.name as novel_name,
                       snippet(outlines_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
                FROM outlines_fts f
                JOIN outlines o ON o.id = f.rowid
                JOIN novels n ON n.id = o.novel_id
                WHERE outlines_fts MATCH ? {novel_filter_sql}
                ORDER BY rank LIMIT ?
            """, [query] + novel_params + [limit]).fetchall()
            results["outlines"] = [dict(r) for r in rows]

            # Search reviews via FTS5
            rows = conn.execute(f"""
                SELECT r.chapter_ref, n.name as novel_name, r.word_count,
                       snippet(reviews_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
                FROM reviews_fts f
                JOIN reviews r ON r.id = f.rowid
                JOIN novels n ON n.id = r.novel_id
                WHERE reviews_fts MATCH ? {novel_filter_sql}
                ORDER BY rank LIMIT ?
            """, [query] + novel_params + [limit]).fetchall()
            results["reviews"] = [dict(r) for r in rows]
        except Exception:
            pass  # FTS5 may fail on special chars

        # Fallback to LIKE if FTS5 returned nothing
        if not results["chapters"] and not results["outlines"] and not results["reviews"]:
            like_query = f"%{query}%"
            like_params = [like_query] + novel_params

            # LIKE search chapters
            like_rows = conn.execute(f"""
                SELECT c.chapter_ref, c.title, c.word_count, c.volume, n.name as novel_name,
                       SUBSTR(c.content, MAX(1, INSTR(c.content, ?) - 20), 100) as snippet
                FROM chapters c
                JOIN novels n ON n.id = c.novel_id
                WHERE c.content LIKE ? {novel_filter_sql}
                ORDER BY c.volume, c.chapter_num LIMIT ?
            """, [query] + like_params + [limit]).fetchall()
            results["chapters"] = [
                {"chapter_ref": r["chapter_ref"], "title": r["title"],
                 "word_count": r["word_count"], "volume": r["volume"],
                 "novel_name": r["novel_name"],
                 "snippet": f"...{r['snippet']}..." if r["snippet"] else ""}
                for r in like_rows
            ]

            # LIKE search outlines
            like_rows = conn.execute(f"""
                SELECT o.volume, n.name as novel_name,
                       SUBSTR(o.content, MAX(1, INSTR(o.content, ?) - 20), 100) as snippet
                FROM outlines o
                JOIN novels n ON n.id = o.novel_id
                WHERE o.content LIKE ? {novel_filter_sql}
                LIMIT ?
            """, [query] + like_params + [limit]).fetchall()
            results["outlines"] = [
                {"volume": r["volume"], "novel_name": r["novel_name"],
                 "snippet": f"...{r['snippet']}..." if r["snippet"] else ""}
                for r in like_rows
            ]

            # LIKE search reviews
            like_rows = conn.execute(f"""
                SELECT r.chapter_ref, n.name as novel_name, r.word_count,
                       SUBSTR(r.ai_review, MAX(1, INSTR(r.ai_review, ?) - 20), 100) as snippet
                FROM reviews r
                JOIN novels n ON n.id = r.novel_id
                WHERE (r.ai_review LIKE ? OR r.script_detail LIKE ?) {novel_filter_sql}
                LIMIT ?
            """, [query, like_query, like_query] + novel_params + [limit]).fetchall()
            results["reviews"] = [
                {"chapter_ref": r["chapter_ref"], "novel_name": r["novel_name"],
                 "word_count": r["word_count"],
                 "snippet": f"...{r['snippet']}..." if r["snippet"] else ""}
                for r in like_rows
            ]
    finally:
        conn.close()
    return results

def get_novel_stats(novel_name):
    """Get statistics for a novel"""
    conn = get_db()
    try:
        novel = conn.execute("SELECT * FROM novels WHERE name=?", (novel_name,)).fetchone()
        if not novel:
            return {"error": "小说不存在"}
        novel = dict(novel)
        # Chapter word count trend (last 20 chapters)
        chapters = conn.execute("""SELECT chapter_ref, word_count, created_at FROM chapters
            WHERE novel_id=? ORDER BY chapter_num DESC LIMIT 20""", (novel["id"],)).fetchall()
        novel["recent_chapters"] = [dict(c) for c in reversed(chapters)]
        # Review pass rate
        total_reviews = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE novel_id=?", (novel["id"],)).fetchone()["c"]
        novel["total_reviews"] = total_reviews
        return novel
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════
# Foreshadowing Management
# ═══════════════════════════════════════════════════════════════════════

def add_foreshadowing(novel_name, name, description="", category="剧情",
                       introduced_vol=0, introduced_ch=0, target_vol=0,
                       target_ch=0, priority="normal"):
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel:
        conn.close(); return None
    conn.execute("""INSERT INTO foreshadowing
        (novel_id, name, description, category, introduced_vol, introduced_ch,
         target_vol, target_ch, priority)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (novel["id"], name, description, category, introduced_vol,
         introduced_ch, target_vol, target_ch, priority))
    conn.commit()
    fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return fid

def get_foreshadowing(novel_name, status=None, volume=None, limit=100):
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel:
        conn.close(); return []
    sql = "SELECT * FROM foreshadowing WHERE novel_id=?"
    params = [novel["id"]]
    if status:
        sql += " AND status=?"; params.append(status)
    if volume is not None:
        sql += " AND (target_vol=? OR introduced_vol=?)"; params.extend([volume, volume])
    sql += " ORDER BY priority DESC, target_vol ASC, introduced_ch ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_unresolved_foreshadowing(novel_name, current_vol=None, current_ch=None):
    """Get foreshadowing that should be resolved soon (before or at current position)"""
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel:
        conn.close(); return []
    nid = novel["id"]
    sql = """SELECT * FROM foreshadowing WHERE novel_id=? AND status != 'resolved'
             AND status != 'abandoned'"""
    params = [nid]
    if current_vol is not None:
        sql += " AND (target_vol <= ? OR target_vol = 0 OR introduced_vol = ?)"
        params.extend([current_vol, current_vol])
    sql += " ORDER BY priority DESC, target_vol ASC, introduced_ch ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_foreshadowing(fid, **kwargs):
    conn = get_db()
    allowed = ["name","description","category","status","introduced_vol",
               "introduced_ch","target_vol","target_ch","resolved_vol",
               "resolved_ch","resolution_note","priority"]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed:
            updates.append(f"{k}=?")
            params.append(v)
    if updates:
        params.append(fid)
        conn.execute(f"UPDATE foreshadowing SET {','.join(updates)}, updated_at=datetime('now') WHERE id=?", params)
        conn.commit()
    conn.close()

def delete_foreshadowing(fid):
    conn = get_db()
    conn.execute("DELETE FROM foreshadowing WHERE id=?", (fid,))
    conn.commit()
    conn.close()

def resolve_foreshadowing(fid, vol, ch, note=""):
    """Mark a foreshadowing as resolved with volume/chapter info"""
    conn = get_db()
    conn.execute("""UPDATE foreshadowing SET status='resolved', resolved_vol=?,
        resolved_ch=?, resolution_note=?, updated_at=datetime('now')
        WHERE id=?""", (vol, ch, note, fid))
    conn.commit()
    conn.close()

def init_foreshadowing_from_outline(novel_name):
    """Scan the outline for implicit foreshadowing points and create them.
    Uses pattern matching to find foreshadowing hints in outline text."""
    import glob
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "无大纲目录"}

    # Patterns that suggest foreshadowing
    patterns = [
        (r'伏笔[：:]?\s*(.+)', '剧情'),
        (r'铺垫[：:]?\s*(.+)', '剧情'),
        (r'暗示[：:]?\s*(.+)', '剧情'),
        (r'后续.*?出现[：:]?\s*(.+)', '角色'),
        (r'隐藏[：:]?\s*(.+)', '剧情'),
        (r'秘密[：:]?\s*(.+)', '世界观'),
        (r'真相[：:]?\s*(.+)', '世界观'),
        (r'真正.*?是[：:]?\s*(.+)', '身份'),
        (r'叶微伏笔[：:]?\s*(.+)', '女主'),
    ]

    created = 0
    for fpath in sorted(glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find chapter sections
        for m in re.finditer(r'第(\d+)章', content):
            ch_num = int(m.group(1))
            ch_start = m.start()
            next_ch = re.search(r'第(\d+)章', content[ch_start+5:])
            ch_end = ch_start + 5 + next_ch.start() if next_ch else len(content)
            ch_section = content[ch_start:ch_end]

            for pattern, cat in patterns:
                for pm in re.finditer(pattern, ch_section):
                    desc = pm.group(1).strip()[:200]
                    if len(desc) > 5:
                        # Check if similar foreshadowing already exists
                        conn = get_db()
                        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
                        if novel:
                            existing = conn.execute(
                                "SELECT id FROM foreshadowing WHERE novel_id=? AND name LIKE ?",
                                (novel["id"], f"%{desc[:30]}%")).fetchone()
                            if not existing:
                                add_foreshadowing(novel_name,
                                    name=f"第{ch_num}章伏笔: {desc[:50]}",
                                    description=desc, category=cat,
                                    introduced_vol=vol_num, introduced_ch=ch_num,
                                    target_vol=vol_num+1 if vol_num>0 else vol_num)
                                created += 1
                        conn.close()
    return {"created": created, "message": f"从大纲初始化 {created} 条伏笔"}

if __name__ == "__main__":
    init_db()
    print("DB initialized. Syncing all novels...")
    results = sync_all_novels()
    for r in results:
        if "error" in r:
            print(f"  ❌ {r.get('novel', '?')}: {r['error']}")
        else:
            s = r["stats"]
            print(f"  ✅ {r['novel']}: {s['chapters']}章 {s['outlines']}大纲 {s['reviews']}审稿")

# ═══════════════════════════════════════════════════════════════════════
# Character Management
# ═══════════════════════════════════════════════════════════════════════

def get_characters(novel_name, role=None):
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return []
    sql = "SELECT * FROM characters WHERE novel_id=? "
    params = [novel["id"]]
    if role:
        sql += "AND role=?"; params.append(role)
    sql += "ORDER BY CASE role WHEN '主角' THEN 0 WHEN '女主' THEN 1 WHEN '反派' THEN 2 ELSE 3 END, name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_character(novel_name, cid):
    conn = get_db()
    row = conn.execute("""SELECT c.* FROM characters c
        JOIN novels n ON c.novel_id=n.id
        WHERE n.name=? AND c.id=?""", (novel_name, cid)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_character(novel_name, name, role="配角", **kwargs):
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return None
    allowed = ["gender","age","identity","personality","appearance","background",
               "current_status","current_vol","current_ch","lifeline","arc","ending","notes"]
    fields = ["novel_id","name","role"]
    values = [novel["id"], name, role]
    for k in allowed:
        if k in kwargs and kwargs[k]:
            fields.append(k); values.append(kwargs[k])
    conn.execute(f"INSERT INTO characters ({','.join(fields)}) VALUES ({','.join('?'*len(fields))})", values)
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return cid

def update_character(cid, **kwargs):
    conn = get_db()
    allowed = ["name","role","gender","age","identity","personality","appearance",
               "background","current_status","current_vol","current_ch","lifeline",
               "arc","ending","notes","desire","fear","lie","truth",
               "ability_level","ability_curve","ability_cost",
               "emotional_state","emotion_curve","relationship_map",
               "dilemma","mirror"]
    updates = []; params = []
    for k,v in kwargs.items():
        if k in allowed:
            updates.append(f"{k}=?"); params.append(v)
    if updates:
        params.append(cid)
        conn.execute(f"UPDATE characters SET {','.join(updates)}, updated_at=datetime('now') WHERE id=?", params)
        conn.commit()
    conn.close()

def delete_character(cid):
    conn = get_db()
    conn.execute("DELETE FROM characters WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def add_character_event(novel_name, cid, description, event_type="状态变更",
                         vol=0, ch=0, chapter_ref="", source="manual"):
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return None
    conn.execute("""INSERT INTO character_events
        (novel_id, character_id, event_type, description, vol, ch, chapter_ref, source)
        VALUES (?,?,?,?,?,?,?,?)""",
        (novel["id"], cid, event_type, description, vol, ch, chapter_ref, source))
    conn.commit()
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return eid

def get_character_events(novel_name, cid, limit=50):
    conn = get_db()
    rows = conn.execute("""SELECT * FROM character_events
        WHERE character_id=? ORDER BY vol ASC, ch ASC LIMIT ?""", (cid, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def init_characters_from_files(novel_name):
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    chars_path = os.path.join(novel_path, "characters.md")
    if not os.path.exists(chars_path):
        return {"created": 0, "message": "characters.md not found"}

    with open(chars_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Sub-section keywords that are NOT character names
    skip_kw = ['背景', '身世', '核心特质', '系统宿主', '异能', '修真传承',
               '成长弧线', '对抗历程', '重生能力', '关系演变', '终极命运',
               '乐园相关', '容器宿主', '破晓联盟', '天骄', '详解', '相关']

    def is_char_name(n):
        n = n.strip()
        # Strip descriptions: 沈念（乐园引路人）→沈念, 初号——奥科洛斯→初号
        for sep in ['（', '(', '——', '—']:
            if sep in n: n = n[:n.index(sep)].strip()
        if len(n) > 12 or len(n) < 1: return False
        if '：' in n or ':' in n: return False
        if n.endswith('天骄') or n.endswith('相关') or n.endswith('宿主'): return False
        for kw in skip_kw:
            if kw in n: return False
        return True

    created = 0
    # Scan both ### and #### headings
    for m in re.finditer(r'^(#{3,4})\s+(.+?)$', text, re.MULTILINE):
        name = m.group(2).strip()
        # Use stripped name for storage (remove parenthetical)
        display_name = name
        for sep in ['（', '(', '——', '—']:
            if sep in display_name: display_name = display_name[:display_name.index(sep)].strip()
        if not is_char_name(name): continue

        # Determine role: find the closest ## section heading before this character
        role = "配角"
        prev_text = text[:m.start()]
        # Find all ## headings in reverse, take the last one (closest)
        headings = list(re.finditer(r'^##\s+(.+?)$', prev_text, re.MULTILINE))
        if headings:
            h = headings[-1].group(1).strip()
            if "主角" in h and "配角" not in h: role = "主角"
            elif "女主" in h: role = "女主"
            elif "反派" in h: role = "反派" 

        # Extract section content
        level = len(m.group(1))
        rest = text[m.end():]
        next_m = re.search(r'^#{1,' + str(level) + r'}\s', rest, re.MULTILINE)
        section = rest[:next_m.start()] if next_m else rest

        # Extract fields from table rows
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

        conn = get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
        if novel:
            existing = conn.execute("SELECT id FROM characters WHERE novel_id=? AND name=?",
                (novel["id"], name)).fetchone()
            if not existing:
                add_character(novel_name, display_name, role=role,
                    identity=identity, personality=personality[:500],
                    background=background, current_status=status)
                created += 1
        conn.close()

    return {"created": created, "message": f"Initialized {created} characters from characters.md"}


# ═══════════════════════════════════════════════════════════════════════
# V3 Init Engine — populate domain tables from files
# ═══════════════════════════════════════════════════════════════════════

def init_world_building_from_file(novel_name):
    """Parse world_bible.md into world_building table entries"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    wb_path = os.path.join(novel_path, "world_bible.md")
    if not os.path.exists(wb_path):
        return {"created": 0, "message": "world_bible.md not found"}

    with open(wb_path, 'r', encoding='utf-8') as f:
        text = f.read()

    created = 0
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0, "message": "novel not found"}
    nid = novel["id"]

    # Find section headers (## 力量体系, ## 地图, etc.)
    domain_map = {
        '力量体系': '力量体系', '修炼': '力量体系', '等级': '力量体系', '功法': '力量体系',
        '地图': '地图', '地域': '地图', '地理': '地图', '世界': '地图',
        '历史': '历史', '种族': '种族', '组织': '组织', '势力': '组织',
        '规则': '规则', '法则': '规则', '禁忌': '禁忌', '禁地': '禁忌',
        '科技': '科技',
    }

    for m in re.finditer(r'^##\s+(.+?)$', text, re.MULTILINE):
        heading = m.group(1).strip()
        domain = "其他"
        for kw, dm in domain_map.items():
            if kw in heading: domain = dm; break

        # Get content until next ##
        start = m.end()
        next_sec = re.search(r'\n##\s', text[start:])
        content = text[start:start + next_sec.start()].strip() if next_sec else text[start:].strip()

        if len(content) > 10:
            # Check for sub-items
            items = re.findall(r'^[-*]\s+(.+)$', content, re.MULTILINE)
            if items:
                for item in items[:10]:
                    name = item[:80].strip()
                    if not conn.execute("SELECT id FROM world_building WHERE novel_id=? AND name=?",
                                        (nid, name)).fetchone():
                        conn.execute("""INSERT INTO world_building
                            (novel_id, domain, name, content) VALUES (?,?,?,?)""",
                            (nid, domain, name, item))
                        created += 1
            else:
                # Single entry for the whole section
                name = heading[:80]
                if not conn.execute("SELECT id FROM world_building WHERE novel_id=? AND name=?",
                                    (nid, name)).fetchone():
                    conn.execute("""INSERT INTO world_building
                        (novel_id, domain, name, content) VALUES (?,?,?,?)""",
                        (nid, domain, name, content[:2000]))
                    created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} world_building entries"}


def init_plot_arcs_from_file(novel_name):
    """Parse full_story_arc.md into plot_arcs table"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    arc_path = os.path.join(novel_path, "full_story_arc.md")
    if not os.path.exists(arc_path):
        return {"created": 0, "message": "full_story_arc.md not found"}

    with open(arc_path, 'r', encoding='utf-8') as f:
        text = f.read()

    created = 0
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    for m in re.finditer(r'##\s+(.+?)$', text, re.MULTILINE):
        heading = m.group(1).strip()
        start = m.end()
        next_sec = re.search(r'\n##\s', text[start:])
        summary = text[start:start + next_sec.start()].strip() if next_sec else text[start:].strip()

        # Extract volume info from heading: "第一卷：青云崛起"
        vol_match = re.search(r'第([一二三四五六七八九十\d]+)卷', heading)
        vol_num = _parse_chinese_vol(vol_match.group(1)) if vol_match else 0

        # Determine type
        arc_type = "主线"
        if "支线" in heading: arc_type = "支线"
        elif "感情" in heading or "女主" in heading: arc_type = "感情线"
        elif "成长" in heading: arc_type = "成长线"

        if not conn.execute("SELECT id FROM plot_arcs WHERE novel_id=? AND name=?",
                            (nid, heading[:80])).fetchone():
            conn.execute("""INSERT INTO plot_arcs
                (novel_id, name, type, volume_start, volume_end, summary, milestones, status, priority)
                VALUES (?,?,?,?,?,?,?,'active','normal')""",
                (nid, heading[:80], arc_type, vol_num, vol_num, summary[:500], '[]'))
            created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} plot arcs"}


def _parse_chinese_vol(s):
    """Parse Chinese volume number: 一→1, 二→2, etc."""
    chinese_nums = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    if s in chinese_nums: return chinese_nums[s]
    try: return int(s)
    except: return 0


def init_pacing_from_outline(novel_name):
    """Parse outline vol-XX-chapters.md for pacing control entries.
    Supports two formats:
    1. Individual chapter: '第001章 节奏：高潮 情感：紧张'
    2. Table format: '| 042-045 | 桥弧复验... | ... | ... | 李闲压住... | ... |'
    """
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "no outline directory"}

    created = 0
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    import glob
    for fpath in sorted(glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        # ─── Format 1: Individual chapter markers (第001章 节奏：...) ───
        for cm in re.finditer(r'第(\d+)章', text):
            ch_num = int(cm.group(1))
            ch_start = cm.start()
            next_ch = re.search(r'第(\d+)章', text[ch_start+5:])
            ch_end = ch_start + 5 + next_ch.start() if next_ch else len(text)
            section = text[ch_start:ch_end]

            pace_type = "过渡"
            emotion = ""
            intensity = 5

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
                for kw in ['爽', '虐', '悬', '燃', '暖', '惧', '压抑', '期待', '惊喜', '好奇']:
                    if kw in e: emotion = kw; break

            if not conn.execute("""SELECT id FROM pacing_control
                WHERE novel_id=? AND volume=? AND chapter_start=?""",
                (nid, vol_num, ch_num)).fetchone():
                conn.execute("""INSERT INTO pacing_control
                    (novel_id, volume, chapter_start, chapter_end, pace_type,
                     intensity, emotion_target, word_budget_min, word_budget_max)
                    VALUES (?,?,?,?,?,?,?,2500,3500)""",
                    (nid, vol_num, ch_num, ch_num, pace_type, intensity, emotion))
                created += 1

        # ─── Format 2: Table-based (| 章节范围 | 节奏类型 | ... | 情绪回报 | ...) ───
        # Match lines like: | 042-045 | 桥弧复验与首场危机 | ... | ... | 李闲压住茶桌... | ... |
        table_row_re = re.compile(
            r'^\|\s*(\d{3})\s*[-–]\s*(\d{3})\s*\|\s*([^|]+)\s*\|'
            r'[^|]*\|[^|]*\|\s*([^|]+?)\s*\|',
            re.MULTILINE
        )
        for rm in table_row_re.finditer(text):
            ch_start = int(rm.group(1))
            ch_end = int(rm.group(2))
            pace_label = rm.group(3).strip()
            emotion_text = rm.group(4).strip()

            # Map pace type
            pace_type = "过渡"
            intensity = 5
            if any(kw in pace_label for kw in ['高潮', '高压', '危机']):
                pace_type = '高潮'; intensity = 9
            elif any(kw in pace_label for kw in ['铺垫', '伏笔']):
                pace_type = '铺垫'; intensity = 4
            elif any(kw in pace_label for kw in ['过渡', '桥接']):
                pace_type = '过渡'; intensity = 5
            elif any(kw in pace_label for kw in ['释缓', '放松', '日常']):
                pace_type = '释缓'; intensity = 3

            # Extract emotion keyword
            emotion = ""
            for kw in ['爽', '虐', '悬', '燃', '暖', '惧', '压抑', '期待', '惊喜', '好奇', '留白']:
                if kw in emotion_text: emotion = kw; break

            if not conn.execute("""SELECT id FROM pacing_control
                WHERE novel_id=? AND volume=? AND chapter_start=?""",
                (nid, vol_num, ch_start)).fetchone():
                conn.execute("""INSERT INTO pacing_control
                    (novel_id, volume, chapter_start, chapter_end, pace_type,
                     intensity, emotion_target, word_budget_min, word_budget_max)
                    VALUES (?,?,?,?,?,?,?,2500,3500)""",
                    (nid, vol_num, ch_start, ch_end, pace_type, intensity, emotion))
                created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} pacing entries"}


def init_revelation_from_outline(novel_name):
    """Parse outline for information release schedule.
    Supports two formats:
    1. Individual markers: '信息释放：...' or '伏笔揭示：...' near '第001章'
    2. Table format: '| 042-045 | ... | ... | 外线石、旧印... | ... | ... |' (col 4 = 信息释放)
    """
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    outline_dir = os.path.join(novel_path, "outline")
    if not os.path.exists(outline_dir):
        return {"created": 0, "message": "no outline directory"}

    created = 0
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    import glob
    for fpath in sorted(glob.glob(os.path.join(outline_dir, "vol-*-chapters.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read()

        # ─── Format 1: Individual chapter markers ───
        for pattern, info_type in [
            (r'信息释放[：:]\s*(.+)', '世界观'),
            (r'伏笔揭示[：:]\s*(.+)', '伏笔揭示'),
            (r'揭示[：:]\s*(.+)', '角色秘密'),
            (r'真相[：:]\s*(.+)', '世界观'),
        ]:
            for m in re.finditer(pattern, text):
                content = m.group(1).strip()[:300]
                before = text[:m.start()]
                ch_matches = list(re.finditer(r'第(\d+)章', before))
                ch_num = int(ch_matches[-1].group(1)) if ch_matches else 0

                name = f"第{vol_num}卷第{ch_num}章: {content[:60]}"
                if not conn.execute("SELECT id FROM revelation_schedule WHERE novel_id=? AND name=?",
                                    (nid, name)).fetchone():
                    conn.execute("""INSERT INTO revelation_schedule
                        (novel_id, name, info_type, reveal_volume, reveal_chapter,
                         content, audience_knows, protagonist_knows, priority)
                        VALUES (?,?,?,?,?,?,0,0,'normal')""",
                        (nid, name, info_type, vol_num, ch_num, content))
                    created += 1

        # ─── Format 2: Table-based (| 章节范围 | 节奏类型 | 章节任务 | 信息释放 | 情绪回报 | 限制 |) ───
        # Extract info_release from column 4 of the rhythm table
        table_row_re = re.compile(
            r'^\|\s*(\d{3})\s*[-–]\s*(\d{3})\s*\|'
            r'[^|]*\|[^|]*\|\s*([^|]+?)\s*\|',
            re.MULTILINE
        )
        for rm in table_row_re.finditer(text):
            ch_start = int(rm.group(1))
            ch_end = int(rm.group(2))
            info_content = rm.group(3).strip()

            if not info_content or len(info_content) < 3:
                continue

            name = f"第{vol_num}卷第{ch_start}-{ch_end}章: {info_content[:60]}"

            # Determine info_type from content
            info_type = "世界观"
            if any(kw in info_content for kw in ['身份', '秘密', '真实']):
                info_type = "角色秘密"
            elif any(kw in info_content for kw in ['伏笔', '铺垫', '揭示']):
                info_type = "伏笔揭示"
            elif any(kw in info_content for kw in ['规则', '设定', '体系']):
                info_type = "世界观"

            if not conn.execute("SELECT id FROM revelation_schedule WHERE novel_id=? AND name=?",
                                (nid, name)).fetchone():
                conn.execute("""INSERT INTO revelation_schedule
                    (novel_id, name, info_type, reveal_volume, reveal_chapter,
                     content, audience_knows, protagonist_knows, priority)
                    VALUES (?,?,?,?,?,?,0,0,'normal')""",
                    (nid, name, info_type, vol_num, ch_start, info_content))
                created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} revelation entries"}


def init_genre_rules_from_file(novel_name):
    """Parse genre_bible.md for genre rules"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "genre_bible.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "genre_bible.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    # Clear existing
    conn.execute("DELETE FROM genre_rules WHERE novel_id=?", (nid,))
    created = 0

    # Parse sections: ## category followed by list items
    sections = re.split(r'\n##\s+', text)
    for sec in sections[1:]:  # skip content before first ##
        lines = sec.strip().split('\n')
        category = lines[0].strip()
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- '):
                content = line[2:].strip()
                conn.execute("INSERT INTO genre_rules (novel_id, rule_category, rule_content) VALUES (?,?,?)",
                             (nid, category, content))
                created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} genre rules"}


def init_story_volumes_from_file(novel_name):
    """Parse full_story_arc.md for volume structure table"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "full_story_arc.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "full_story_arc.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    conn.execute("DELETE FROM story_volumes WHERE novel_id=?", (nid,))
    created = 0

    # Find table under "## 分卷结构" — parse rows like | 第N卷：name | range | ... |
    for m in re.finditer(
        r'\|\s*第\s*(\d+)\s*卷[：:]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        text
    ):
        vol_num = int(m.group(1))
        vol_name = m.group(2).strip()
        word_range = m.group(3).strip()
        goal = m.group(4).strip()
        conflict = m.group(5).strip()
        payoff = m.group(6).strip()
        foreshadowing = m.group(7).strip()
        status = m.group(8).strip()

        conn.execute("""INSERT INTO story_volumes
            (novel_id, vol_num, vol_name, word_range, goal, conflict, payoff, foreshadowing, status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (nid, vol_num, vol_name, word_range, goal, conflict, payoff, foreshadowing, status))
        created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} story volumes"}


def init_volume_plans_from_files(novel_name):
    """Parse volume_plan.md and volume_plan/vol-XX.md for detailed volume plans"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    vp_dir = os.path.join(novel_path, "volume_plan")
    if not os.path.exists(vp_dir):
        return {"created": 0, "message": "no volume_plan directory"}

    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    conn.execute("DELETE FROM volume_plans WHERE novel_id=?", (nid,))
    created = 0

    import glob
    for fpath in sorted(glob.glob(os.path.join(vp_dir, "vol-*.md"))):
        vol_match = re.search(r'vol-(\d+)', os.path.basename(fpath))
        vol_num = int(vol_match.group(1)) if vol_match else 0
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract title from first heading
        title = ""
        tm = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        if tm:
            title = tm.group(1).strip()

        conn.execute("""INSERT OR REPLACE INTO volume_plans
            (novel_id, vol_num, title, plan_content, word_count)
            VALUES (?,?,?,?,?)""",
            (nid, vol_num, title, content, len(content)))
        created += 1

    # Also parse the root volume_plan.md if exists
    root_plan = os.path.join(novel_path, "volume_plan.md")
    if os.path.exists(root_plan):
        with open(root_plan, 'r', encoding='utf-8') as f:
            content = f.read()
        conn.execute("""INSERT OR REPLACE INTO volume_plans
            (novel_id, vol_num, title, plan_content, word_count)
            VALUES (?,?,?,?,?)""",
            (nid, 0, "卷规划总览", content, len(content)))
        created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} volume plans"}


def init_alias_names_from_file(novel_name):
    """Parse alias_registry.md for alias names"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "alias_registry.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "alias_registry.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    conn.execute("DELETE FROM alias_names WHERE novel_id=?", (nid,))
    created = 0

    # Parse tables — rows like | category | alias | desc | scope | first_ch |
    for m in re.finditer(
        r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        text
    ):
        row = [m.group(i).strip() for i in range(1, 6)]
        if row[0] in ('类别', '---', ':---'): continue  # skip header/separator
        conn.execute("""INSERT INTO alias_names
            (novel_id, category, alias_name, description, scope, first_chapter)
            VALUES (?,?,?,?,?,?)""",
            (nid, row[0], row[1], row[2], row[3], row[4]))
        created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} alias names"}


def init_project_meta_from_file(novel_name):
    """Parse project.md for project metadata"""
    novel_path = os.path.join(NOVELS_ROOT, novel_name)
    fpath = os.path.join(novel_path, "project.md")
    if not os.path.exists(fpath):
        return {"created": 0, "message": "project.md not found"}

    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return {"created": 0}
    nid = novel["id"]

    conn.execute("DELETE FROM project_meta WHERE novel_id=?", (nid,))
    created = 0

    # Parse key: value lines from sections
    for m in re.finditer(r'^-\s*(.+?)[：:]\s*(.+)$', text, re.MULTILINE):
        key = m.group(1).strip()
        value = m.group(2).strip()
        conn.execute("INSERT INTO project_meta (novel_id, meta_key, meta_value) VALUES (?,?,?)",
                     (nid, key, value))
        created += 1

    conn.commit(); conn.close()
    return {"created": created, "message": f"Initialized {created} project meta entries"}


def init_all_from_files(novel_name):
    """Orchestrate full initialization from all files"""
    results = {
        'success': True,
        'tables': {},
        'errors': [],
    }
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
    for table_name, func in init_funcs.items():
        try:
            result = func(novel_name)
            # Report total count (not just newly created) for idempotency
            created = result.get('created', 0)
            if created == 0 and table_name != 'foreshadowing':
                # Check existing count
                c = get_db()
                novel = c.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
                if novel:
                    existing = c.execute(f"SELECT COUNT(*) FROM {table_name} WHERE novel_id=?", (novel["id"],)).fetchone()[0]
                    created = existing
                c.close()
            results['tables'][table_name] = created
        except Exception as e:
            results['errors'].append(f"{table_name}: {str(e)}")
            results['tables'][table_name] = 0

    results['success'] = len(results['errors']) == 0
    return results


def auto_update_after_save(novel_name, volume, chapter_num, content):
    """Auto-update state after a chapter is saved.
    Updates: character positions, foreshadowing status, chapter metadata."""
    import json as _json
    import re as _re
    conn = get_db()
    novel = conn.execute("SELECT id FROM novels WHERE name=?", (novel_name,)).fetchone()
    if not novel: conn.close(); return
    nid = novel["id"]
    volume_str = f"vol-{volume:02d}"

    # 1. Update characters: detect appearances from content
    characters = conn.execute(
        "SELECT id, name FROM characters WHERE novel_id=?", (nid,)).fetchall()
    appeared = []
    for c in characters:
        if c["name"] in content:
            appeared.append(c["name"])

    if appeared:
        ch_ref = f"{volume_str}/ch-{chapter_num:04d}"
        conn.execute("""UPDATE chapters SET characters_appeared=?
            WHERE novel_id=? AND volume=? AND chapter_num=?""",
            (_json.dumps(appeared), nid, volume_str, chapter_num))
        conn.commit()

    # 2. Check foreshadowing: note items whose target chapter is reached
    pending = conn.execute(
        """SELECT id, name, target_vol, target_ch FROM foreshadowing
           WHERE novel_id=? AND status='pending'
           AND target_vol>0 AND target_vol<=?""",
        (nid, volume)).fetchall()
    for f in pending:
        if f["target_vol"] == volume and f["target_ch"] > 0 and f["target_ch"] == chapter_num:
            conn.execute("""UPDATE foreshadowing SET
                resolution_note=resolution_note || ' [到达目标第' || ? || '卷第' || ? || '章，等待填坑]'
                WHERE id=?""", (volume, chapter_num, f["id"]))
            conn.commit()

    # 3. Mark foreshadowing as touched if referenced in content
    foreshadowings = conn.execute(
        "SELECT id, name FROM foreshadowing WHERE novel_id=? AND status='pending'",
        (nid,)).fetchall()
    touched = []
    for f in foreshadowings:
        if f["name"] in content or any(kw in content for kw in f["name"].split('：')[:1]):
            touched.append(f["id"])
    if touched:
        conn.execute("""UPDATE chapters SET foreshadowing_touched=?
            WHERE novel_id=? AND volume=? AND chapter_num=?""",
            (_json.dumps(touched), nid, volume_str, chapter_num))
        conn.commit()

    conn.close()
