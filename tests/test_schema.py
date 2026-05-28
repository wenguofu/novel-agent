"""
Phase 1: Schema Tests — RED phase
Tests that new tables DON'T exist yet (current v2 state).
After implementation, these same tests will verify they DO exist.
"""

import sqlite3
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import content_db as db


@pytest.fixture
def fresh_db(tmp_path):
    """Create a fresh content.db for testing"""
    db_path = tmp_path / "content.db"
    # Override DB_PATH temporarily
    old_path = db.DB_PATH
    db.DB_PATH = str(db_path)
    db.init_db()
    yield
    db.DB_PATH = old_path


class TestNewTables:
    """Test that all v3 tables can be created with correct schema"""

    def test_world_building_table_exists(self, fresh_db):
        """world_building table should exist after init_db"""
        conn = sqlite3.connect(db.DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'world_building' in tables, "world_building table missing"

    def test_world_building_columns(self, fresh_db):
        """world_building should have correct columns"""
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(world_building)").fetchall()]
        conn.close()
        required = ['id', 'novel_id', 'domain', 'name', 'content',
                     'related_vol', 'related_ch', 'tags']
        for col in required:
            assert col in cols, f"Missing column: {col}"

    def test_plot_arcs_table_exists(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'plot_arcs' in tables

    def test_plot_arcs_columns(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(plot_arcs)").fetchall()]
        conn.close()
        for col in ['name', 'type', 'volume_start', 'chapter_start',
                     'volume_end', 'chapter_end', 'summary', 'milestones',
                     'status', 'priority']:
            assert col in cols, f"Missing: {col}"

    def test_pacing_control_table_exists(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'pacing_control' in tables

    def test_pacing_control_columns(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(pacing_control)").fetchall()]
        conn.close()
        for col in ['volume', 'chapter_start', 'chapter_end', 'pace_type',
                     'intensity', 'emotion_target', 'word_budget_min',
                     'word_budget_max']:
            assert col in cols, f"Missing: {col}"

    def test_revelation_schedule_table_exists(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert 'revelation_schedule' in tables

    def test_revelation_schedule_columns(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(revelation_schedule)").fetchall()]
        conn.close()
        for col in ['name', 'info_type', 'reveal_volume', 'reveal_chapter',
                     'content', 'audience_knows', 'protagonist_knows', 'priority']:
            assert col in cols, f"Missing: {col}"

    def test_characters_extended_columns(self, fresh_db):
        """characters should have v3 extended columns"""
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(characters)").fetchall()]
        conn.close()
        for col in ['emotional_state', 'ability_level', 'relationship_map']:
            assert col in cols, f"Missing character column: {col}"

    def test_foreshadowing_extended_columns(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(foreshadowing)").fetchall()]
        conn.close()
        for col in ['hint_method', 'reveal_method', 'is_dark']:
            assert col in cols, f"Missing foreshadowing column: {col}"

    def test_chapters_extended_columns(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(chapters)").fetchall()]
        conn.close()
        for col in ['pace_type', 'emotional_beat', 'foreshadowing_touched',
                     'characters_appeared']:
            assert col in cols, f"Missing chapter column: {col}"


class TestCRUD:
    """Test CRUD operations for new tables"""

    def _setup_novel(self, conn):
        conn.execute("INSERT INTO novels (name, title) VALUES ('test', 'Test Novel')")
        return 1  # novel_id

    def test_world_building_crud(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        nid = self._setup_novel(conn)

        # CREATE
        conn.execute("""INSERT INTO world_building
            (novel_id, domain, name, content, related_vol, related_ch, tags)
            VALUES (?, '力量体系', '斗气等级', '斗者→斗师→大斗师...', 1, 0, 'power')""",
            (nid,))
        conn.commit()

        # READ
        row = conn.execute(
            "SELECT * FROM world_building WHERE novel_id=?", (nid,)).fetchone()
        assert row is not None
        assert row[2] == '力量体系'  # domain column

        # UPDATE
        conn.execute(
            "UPDATE world_building SET content=? WHERE id=?",
            ('updated content', row[0]))
        conn.commit()
        row2 = conn.execute(
            "SELECT content FROM world_building WHERE id=?", (row[0],)).fetchone()
        assert row2[0] == 'updated content'

        # DELETE
        conn.execute("DELETE FROM world_building WHERE id=?", (row[0],))
        conn.commit()
        row3 = conn.execute(
            "SELECT id FROM world_building WHERE id=?", (row[0],)).fetchone()
        assert row3 is None
        conn.close()

    def test_plot_arcs_crud(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        nid = self._setup_novel(conn)

        conn.execute("""INSERT INTO plot_arcs
            (novel_id, name, type, volume_start, chapter_start,
             volume_end, chapter_end, summary, milestones, status, priority)
            VALUES (?, '主线-成神之路', '主线', 1, 1, 7, 0,
             '付大强从普通人到成神', '[]', 'active', 'high')""",
            (nid,))
        conn.commit()

        row = conn.execute(
            "SELECT name, type, status FROM plot_arcs WHERE novel_id=?",
            (nid,)).fetchone()
        assert row[0] == '主线-成神之路'
        assert row[1] == '主线'
        conn.close()

    def test_pacing_control_crud(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        nid = self._setup_novel(conn)

        conn.execute("""INSERT INTO pacing_control
            (novel_id, volume, chapter_start, chapter_end, pace_type,
             intensity, emotion_target, word_budget_min, word_budget_max)
            VALUES (?, 1, 1, 5, '铺垫', 5, '悬', 2500, 3000)""",
            (nid,))
        conn.commit()

        row = conn.execute(
            "SELECT pace_type, intensity, emotion_target FROM pacing_control WHERE novel_id=?",
            (nid,)).fetchone()
        assert row[0] == '铺垫'
        assert row[1] == 5
        conn.close()

    def test_revelation_schedule_crud(self, fresh_db):
        conn = sqlite3.connect(db.DB_PATH)
        nid = self._setup_novel(conn)

        conn.execute("""INSERT INTO revelation_schedule
            (novel_id, name, info_type, reveal_volume, reveal_chapter,
             content, audience_knows, protagonist_knows, priority)
            VALUES (?, '系统真相', '角色秘密', 7, 0,
             '系统是叛神的神格残魂', 0, 0, 'high')""",
            (nid,))
        conn.commit()

        row = conn.execute(
            "SELECT name, audience_knows, protagonist_knows FROM revelation_schedule WHERE novel_id=?",
            (nid,)).fetchone()
        assert row[0] == '系统真相'
        assert row[1] == 0  # audience doesn't know yet
        assert row[2] == 0  # protagonist doesn't know yet
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
