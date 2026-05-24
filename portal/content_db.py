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
"""

def init_db():
    """Create tables if not exist"""
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

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
                if not os.path.isdir(vol_path):
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
    """Full-text search across chapters, outlines, reviews"""
    conn = get_db()
    results = {"chapters": [], "outlines": [], "reviews": []}
    try:
        # Search chapters
        novel_filter = ""
        params = []
        if novel_name:
            novel_filter = "AND c.novel_id = (SELECT id FROM novels WHERE name=?)"
            params = [novel_name]
        rows = conn.execute(f"""
            SELECT c.chapter_ref, c.title, c.word_count, c.volume, n.name as novel_name,
                   snippet(chapters_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
            FROM chapters_fts f
            JOIN chapters c ON c.id = f.rowid
            JOIN novels n ON n.id = c.novel_id
            WHERE chapters_fts MATCH ? {novel_filter}
            ORDER BY rank LIMIT ?
        """, [query] + params + [limit]).fetchall()
        results["chapters"] = [dict(r) for r in rows]

        # Search outlines
        rows = conn.execute(f"""
            SELECT o.volume, n.name as novel_name,
                   snippet(outlines_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
            FROM outlines_fts f
            JOIN outlines o ON o.id = f.rowid
            JOIN novels n ON n.id = o.novel_id
            WHERE outlines_fts MATCH ? {novel_filter}
            ORDER BY rank LIMIT ?
        """, [query] + params + [limit]).fetchall()
        results["outlines"] = [dict(r) for r in rows]

        # Search reviews
        rows = conn.execute(f"""
            SELECT r.chapter_ref, n.name as novel_name, r.word_count,
                   snippet(reviews_fts, 2, '<mark>', '</mark>', '...', 40) as snippet
            FROM reviews_fts f
            JOIN reviews r ON r.id = f.rowid
            JOIN novels n ON n.id = r.novel_id
            WHERE reviews_fts MATCH ? {novel_filter}
            ORDER BY rank LIMIT ?
        """, [query] + params + [limit]).fetchall()
        results["reviews"] = [dict(r) for r in rows]
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
