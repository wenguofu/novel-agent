"""
tests/test_reviews_on_conflict.py
功能测试: reviews ON CONFLICT 修复 + api_ai_stream wc_ok 字段
"""
import pytest, sqlite3, json, os, tempfile

TEST_DB = tempfile.mktemp(suffix=".db")

@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS novels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
    cur.execute("INSERT INTO novels (name) VALUES ('test_novel')")
    cur.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
        chapter_ref TEXT NOT NULL,
        ai_review TEXT DEFAULT '',
        script_detail TEXT DEFAULT '',
        wc_ok INTEGER DEFAULT 0,
        compliance_ok INTEGER DEFAULT 0,
        forbidden_ok INTEGER DEFAULT 0,
        bcontrast_count INTEGER DEFAULT 0,
        judgment_groups INTEGER DEFAULT 0,
        tell_count INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(novel_id, chapter_ref)
    )""")
    conn.commit()
    yield conn
    conn.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def nid(conn):
    return conn.execute("SELECT id FROM novels WHERE name='test_novel'").fetchone()["id"]


def test_reviews_on_conflict_same_chapter_updates(fresh_db):
    """
    同一 chapter_ref 多次 review 时，ON CONFLICT(novel_id, chapter_ref) 应更新而非插入新行
    """
    conn = fresh_db
    n = nid(conn)

    # 第一次 review
    conn.execute("""INSERT INTO reviews
        (novel_id, chapter_ref, ai_review, wc_ok, word_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, chapter_ref) DO UPDATE SET
            ai_review=excluded.ai_review, wc_ok=excluded.wc_ok, word_count=excluded.word_count
    """, (n, 'vol-01/ch-0001', '第一次审稿结论', 1, 3000))
    conn.commit()

    # 第二次 review 同一章节
    conn.execute("""INSERT INTO reviews
        (novel_id, chapter_ref, ai_review, wc_ok, word_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(novel_id, chapter_ref) DO UPDATE SET
            ai_review=excluded.ai_review, wc_ok=excluded.wc_ok, word_count=excluded.word_count
    """, (n, 'vol-01/ch-0001', '第二次审稿结论（字数不达标）', 0, 1800))
    conn.commit()

    rows = conn.execute("SELECT * FROM reviews WHERE novel_id=? AND chapter_ref=?", (n, 'vol-01/ch-0001')).fetchall()
    assert len(rows) == 1, f"ON CONFLICT 未合并，应只有1条，实际{len(rows)}条"
    assert rows[0]['ai_review'] == '第二次审稿结论（字数不达标）'
    assert rows[0]['wc_ok'] == 0
    assert rows[0]['word_count'] == 1800


def test_reviews_insert_distinct_chapters(fresh_db):
    """不同 chapter_ref 正常插入多条"""
    conn = fresh_db
    n = nid(conn)

    for ref in ['vol-01/ch-0001', 'vol-01/ch-0002', 'vol-02/ch-0001']:
        conn.execute("INSERT INTO reviews (novel_id,chapter_ref,wc_ok,word_count) VALUES (?,?,?,?)",
                     (n, ref, 1, 3000))
    conn.commit()

    rows = conn.execute("SELECT chapter_ref FROM reviews WHERE novel_id=? ORDER BY chapter_ref", (n,)).fetchall()
    refs = [r['chapter_ref'] for r in rows]
    assert refs == ['vol-01/ch-0001', 'vol-01/ch-0002', 'vol-02/ch-0001']


def test_reviews_wc_ok_false_for_low_wordcount(fresh_db):
    """wc_ok=0 时说明字数不达标"""
    conn = fresh_db
    n = nid(conn)

    conn.execute("INSERT INTO reviews (novel_id,chapter_ref,wc_ok,word_count) VALUES (?,?,?,?)",
                 (n, 'vol-01/ch-0001', 0, 1800))
    conn.commit()

    row = conn.execute("SELECT * FROM reviews WHERE novel_id=? AND chapter_ref=?", (n, 'vol-01/ch-0001')).fetchone()
    assert row['wc_ok'] == 0
    assert row['word_count'] == 1800
    assert row['compliance_ok'] == 0  # default
    assert row['forbidden_ok'] == 0  # default
