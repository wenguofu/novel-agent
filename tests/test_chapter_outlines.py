"""
tests/test_chapter_outlines.py
功能测试: chapter_outlines 表 + API endpoints
"""
import pytest
import sqlite3, json, os, tempfile

TEST_DB = tempfile.mktemp(suffix=".db")

@pytest.fixture(autouse=True)
def fresh_db():
    """每个测试用干净的空数据库"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS novels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
    cur.execute("INSERT INTO novels (name) VALUES ('test_novel')")
    cur.execute("""CREATE TABLE IF NOT EXISTS chapter_outlines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
        volume TEXT NOT NULL, chapter_num INTEGER NOT NULL,
        title TEXT DEFAULT '',
        function TEXT DEFAULT '[]',
        core_events TEXT DEFAULT '',
        foreshadowing TEXT DEFAULT '[]',
        ending_hook TEXT DEFAULT '',
        is_danger_scene INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(novel_id, volume, chapter_num)
    )""")
    conn.commit()
    yield conn
    conn.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def _get_nid(conn):
    return conn.execute("SELECT id FROM novels WHERE name='test_novel'").fetchone()["id"]


def test_chapter_outline_upsert_and_get(fresh_db):
    """chapter_outlines 表的 upsert + get 接口"""
    conn = fresh_db
    nid = _get_nid(conn)

    # 第一次插入
    conn.execute("""INSERT INTO chapter_outlines
        (novel_id, volume, chapter_num, title, function, core_events, foreshadowing, ending_hook, is_danger_scene, word_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, volume, chapter_num) DO UPDATE SET
            title=excluded.title, function=excluded.function, core_events=excluded.core_events,
            foreshadowing=excluded.foreshadowing, ending_hook=excluded.ending_hook,
            is_danger_scene=excluded.is_danger_scene, word_count=excluded.word_count
    """,
        (nid, 'vol-01', 1, '第一章', '["开篇","悬念"]',
         '测试事件内容', '["线索1"]', '章节钩子', 0, 3000))
    conn.commit()

    rows = conn.execute(
        "SELECT * FROM chapter_outlines WHERE novel_id=? AND volume=? ORDER BY chapter_num",
        (nid, 'vol-01')).fetchall()
    assert len(rows) == 1
    assert rows[0]['title'] == '第一章'
    assert json.loads(rows[0]['function']) == ['开篇','悬念']
    assert json.loads(rows[0]['foreshadowing']) == ['线索1']
    assert rows[0]['is_danger_scene'] == 0
    assert rows[0]['word_count'] == 3000

    # 更新已有记录（upsert 路径）
    conn.execute("""INSERT INTO chapter_outlines
        (novel_id, volume, chapter_num, title, function, core_events, foreshadowing, ending_hook, is_danger_scene, word_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, volume, chapter_num) DO UPDATE SET
            title=excluded.title, function=excluded.function, core_events=excluded.core_events,
            foreshadowing=excluded.foreshadowing, ending_hook=excluded.ending_hook,
            is_danger_scene=excluded.is_danger_scene, word_count=excluded.word_count
    """,
        (nid, 'vol-01', 1, '第一章（更新版）', '["开篇"]',
         '更新后事件', '["线索2"]', '更新钩子', 1, 3500))
    conn.commit()

    rows = conn.execute(
        "SELECT * FROM chapter_outlines WHERE novel_id=? AND volume=? AND chapter_num=1",
        (nid, 'vol-01')).fetchall()
    assert len(rows) == 1
    assert rows[0]['title'] == '第一章（更新版）'
    assert rows[0]['word_count'] == 3500
    assert rows[0]['is_danger_scene'] == 1

    # 统计总章节数
    count = conn.execute(
        "SELECT COUNT(*) as c FROM chapter_outlines WHERE novel_id=? AND volume=?",
        (nid, 'vol-01')).fetchone()['c']
    assert count == 1


def test_chapter_outline_unique_constraint(fresh_db):
    """UNIQUE(novel_id, volume, chapter_num) 防止同一章节重复"""
    conn = fresh_db
    nid = _get_nid(conn)

    conn.execute("INSERT INTO chapter_outlines (novel_id,volume,chapter_num,title,word_count) VALUES (?,?,?,?,?)",
                 (nid, 'vol-01', 1, '第一章', 3000))
    conn.commit()

    # 再次插入同一章节使用 ON CONFLICT 进行 upsert
    conn.execute("""INSERT INTO chapter_outlines (novel_id,volume,chapter_num,title,word_count)
        VALUES (?,?,?,?,?)
        ON CONFLICT(novel_id,volume,chapter_num) DO UPDATE SET title=excluded.title""",
                 (nid, 'vol-01', 1, 'Chapter 1 updated', 3000))
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM chapter_outlines WHERE novel_id=? AND volume=? AND chapter_num=1",
        (nid, 'vol-01')).fetchone()['c']
    assert count == 1, "UNIQUE constraint upsert should keep exactly one record"


def test_multiple_chapters_order(fresh_db):
    """多章节按 chapter_num 排序正确"""
    conn = fresh_db
    nid = _get_nid(conn)

    for ch in [5, 2, 8, 1]:
        conn.execute("INSERT INTO chapter_outlines (novel_id,volume,chapter_num,title,word_count) VALUES (?,?,?,?,?)",
                    (nid, 'vol-01', ch, f'第{ch}章', 3000))
    conn.commit()

    rows = conn.execute(
        "SELECT chapter_num FROM chapter_outlines WHERE novel_id=? AND volume=? ORDER BY chapter_num",
        (nid, 'vol-01')).fetchall()
    chapters = [r['chapter_num'] for r in rows]
    assert chapters == [1, 2, 5, 8], f"ORDER BY chapter_num failed: {chapters}"


def test_chapter_outline_json_fields(fresh_db):
    """function/foreshadowing JSON 字段存取正确"""
    conn = fresh_db
    nid = _get_nid(conn)

    conn.execute("INSERT INTO chapter_outlines (novel_id,volume,chapter_num,function,foreshadowing) VALUES (?,?,?,?,?)",
                 (nid, 'vol-01', 1,
                  '["开篇", "笑点"]',
                  '["伏笔A", "伏笔B"]'))
    conn.commit()

    row = conn.execute("SELECT * FROM chapter_outlines WHERE novel_id=? AND chapter_num=1",
                       (nid,)).fetchone()
    assert json.loads(row['function']) == ["开篇", "笑点"]
    assert json.loads(row['foreshadowing']) == ["伏笔A", "伏笔B"]
