"""tests/test_story_tracking.py - story_tracking + danger_issues extended fields"""
import pytest, sqlite3, json, os, tempfile

DB = tempfile.mktemp(suffix=".db")

@pytest.fixture(autouse=True)
def conn():
    if os.path.exists(DB):
        os.remove(DB)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS novels (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)")
    c.execute("INSERT INTO novels (name) VALUES ('test_novel')")
    c.execute("CREATE TABLE IF NOT EXISTS danger_issues ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " novel_id INTEGER NOT NULL REFERENCES novels(id),"
        " volume TEXT NOT NULL, chapter_num INTEGER,"
        " danger_level TEXT DEFAULT 'low', core_danger TEXT DEFAULT '',"
        " content TEXT NOT NULL,"
        " rhythm_data TEXT DEFAULT '{}',"
        " foreshadowing_data TEXT DEFAULT '[]',"
        " UNIQUE(novel_id, volume, chapter_num))")
    c.execute("CREATE TABLE IF NOT EXISTS story_tracking ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " novel_id INTEGER NOT NULL REFERENCES novels(id),"
        " record_type TEXT NOT NULL,"
        " record_key TEXT NOT NULL,"
        " record_value TEXT NOT NULL,"
        " updated_at TEXT,"
        " UNIQUE(novel_id, record_type, record_key))")
    c.commit()
    yield c
    c.close()
    if os.path.exists(DB):
        os.remove(DB)


def nid(c):
    return c.execute('SELECT id FROM novels WHERE name=?', ('test_novel',)).fetchone()['id']


# danger_issues

def test_danger_issue_upsert(conn):
    n = nid(conn)
    conn.execute(
        "INSERT INTO danger_issues (novel_id,volume,chapter_num,danger_level,core_danger,content,rhythm_data,foreshadowing_data) "
        "VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(novel_id,volume,chapter_num) DO UPDATE SET "
        "danger_level=excluded.danger_level,core_danger=excluded.core_danger,"
        "content=excluded.content,rhythm_data=excluded.rhythm_data,foreshadowing_data=excluded.foreshadowing_data",
        (n, 'vol-01', 1, 'low', 'weird', 'content here',
         json.dumps({'tension': 1}),
         json.dumps([{"id": "FP001", "desc": "ancient text"}])))
    conn.commit()
    row = conn.execute("SELECT * FROM danger_issues WHERE novel_id=? AND chapter_num=1", (n,)).fetchone()
    assert row['danger_level'] == 'low'
    assert json.loads(row['rhythm_data']) == {'tension': 1}
    # upsert update
    conn.execute(
        "INSERT INTO danger_issues (novel_id,volume,chapter_num,danger_level,core_danger,content,rhythm_data,foreshadowing_data) "
        "VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(novel_id,volume,chapter_num) DO UPDATE SET danger_level=excluded.danger_level",
        (n, 'vol-01', 1, 'high', 'level up', '', json.dumps({}), json.dumps([])))
    conn.commit()
    rows = conn.execute("SELECT * FROM danger_issues WHERE novel_id=? AND chapter_num=1", (n,)).fetchall()
    assert len(rows) == 1
    assert rows[0]['danger_level'] == 'high'


def test_danger_level_three_levels(conn):
    n = nid(conn)
    mp = {'low': 1, 'medium': 2, 'high': 3}
    for lvl, ch in mp.items():
        conn.execute(
            "INSERT INTO danger_issues (novel_id,volume,chapter_num,danger_level,content) VALUES (?,?,?,?,?)",
            (n, 'vol-01', ch, lvl, 'content ' + lvl))
    conn.commit()
    rows = conn.execute(
        "SELECT danger_level FROM danger_issues WHERE novel_id=? ORDER BY chapter_num", (n,)).fetchall()
    got = [r['danger_level'] for r in rows]
    assert got == ['low', 'medium', 'high']


# story_tracking

def test_story_tracking_basic(conn):
    n = nid(conn)
    conn.execute(
        "INSERT OR REPLACE INTO story_tracking (novel_id,record_type,record_key,record_value) VALUES (?,?,?,?)",
        (n, 'project_overview', 'target_length', '150-200w chars'))
    conn.execute(
        "INSERT OR REPLACE INTO story_tracking (novel_id,record_type,record_key,record_value) VALUES (?,?,?,?)",
        (n, 'character_state', 'Fu_Daqiang', json.dumps({'state': 'Lv.1', 'pos': 'blood town'})))
    conn.commit()
    r1 = conn.execute(
        "SELECT record_value FROM story_tracking WHERE novel_id=? AND record_type=? AND record_key=?",
        (n, 'project_overview', 'target_length')).fetchone()
    assert r1['record_value'] == '150-200w chars'
    r2 = conn.execute(
        "SELECT record_value FROM story_tracking WHERE novel_id=? AND record_type=? AND record_key=?",
        (n, 'character_state', 'Fu_Daqiang')).fetchone()
    assert json.loads(r2['record_value']) == {'state': 'Lv.1', 'pos': 'blood town'}


def test_story_tracking_update_same_key(conn):
    n = nid(conn)
    conn.execute(
        "INSERT OR REPLACE INTO story_tracking (novel_id,record_type,record_key,record_value) VALUES (?,?,?,?)",
        (n, 'writing_progress', 'ch-001', json.dumps({'status': 'saved'})))
    conn.commit()
    conn.execute(
        "INSERT OR REPLACE INTO story_tracking (novel_id,record_type,record_key,record_value) VALUES (?,?,?,?)",
        (n, 'writing_progress', 'ch-001', json.dumps({'status': 'reviewed'})))
    conn.commit()
    row = conn.execute(
        "SELECT record_value FROM story_tracking WHERE novel_id=? AND record_key=?",
        (n, 'ch-001')).fetchone()
    assert json.loads(row['record_value'])['status'] == 'reviewed'


def test_story_tracking_six_types(conn):
    n = nid(conn)
    data = [
        ('project_overview', 'target_length', '200w chars'),
        ('writing_progress', 'ch-001', '{"title":"ch1"}'),
        ('character_state', 'Fu_Daqiang', '{"state":"Lv.1"}'),
        ('volume_plan', 'vol-01', '{"name":"lost ones"}'),
        ('god_challenge', 'god_1', '{"god_name":"god of lost"}'),
        ('foreshadowing_tracking', 'FP001', '{"description":"mystery"}'),
    ]
    for rt, rk, rv in data:
        conn.execute(
            "INSERT OR REPLACE INTO story_tracking (novel_id,record_type,record_key,record_value) VALUES (?,?,?,?)",
            (n, rt, rk, rv))
    conn.commit()
    rows = conn.execute(
        "SELECT record_type FROM story_tracking WHERE novel_id=? ORDER BY record_type", (n,)).fetchall()
    types = list({r['record_type'] for r in rows})
    assert len(types) == 6, f"expected 6 types, got {types}"