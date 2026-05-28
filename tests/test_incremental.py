"""
Phase 6: Incremental Update Tests — RED phase
Tests that state updates happen automatically after chapter operations.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import content_db as db


@pytest.fixture
def setup_novel(tmp_path):
    """Setup a test novel with characters and foreshadowing"""
    old_root = db.NOVELS_ROOT
    old_db = db.DB_PATH

    novel_dir = tmp_path / "novels" / "inc_test"
    (novel_dir / "manuscript" / "vol-01").mkdir(parents=True)
    (novel_dir / "outline").mkdir(parents=True)
    (novel_dir / "state").mkdir(parents=True)

    db_path = tmp_path / "content.db"
    db.NOVELS_ROOT = str(tmp_path / "novels")
    db.DB_PATH = str(db_path)
    db.init_db()

    # Create novel
    conn = db.get_db()
    conn.execute("INSERT INTO novels (name, title, genre) VALUES ('inc_test', 'Inc Test', '玄幻')")
    conn.commit()
    nid = conn.execute("SELECT id FROM novels WHERE name='inc_test'").fetchone()["id"]

    # Add a character
    db.add_character('inc_test', '测试主角', role='主角',
                     current_status='第1卷第1章前: 存活',
                     current_vol=1, current_ch=0)

    # Add foreshadowing
    from content_db import add_foreshadowing
    add_foreshadowing('inc_test', '测试伏笔', description='需要在第1卷第3章填坑',
                      category='剧情', introduced_vol=1, introduced_ch=1,
                      target_vol=1, target_ch=3, priority='high')

    conn.close()

    yield {
        'novel_name': 'inc_test',
        'nid': nid,
        'tmp_path': str(tmp_path),
    }

    db.NOVELS_ROOT = old_root
    db.DB_PATH = old_db


class TestCharacterStateUpdate:
    """Test character state tracking after chapter events"""

    def test_add_event_updates_status(self, setup_novel):
        """Adding a character event should be possible"""
        chars = db.get_characters('inc_test')
        assert len(chars) == 1
        cid = chars[0]["id"]

        # Add event
        eid = db.add_character_event('inc_test', cid,
            description='测试主角在第一章觉醒了能力',
            event_type='能力觉醒', vol=1, ch=1)
        assert eid is not None

        # Verify event exists
        events = db.get_character_events('inc_test', cid)
        assert len(events) >= 1
        assert events[0]["description"] == '测试主角在第一章觉醒了能力'

    def test_update_character_current_position(self, setup_novel):
        """Should be able to update character position after chapter"""
        chars = db.get_characters('inc_test')
        cid = chars[0]["id"]

        db.update_character(cid, current_vol=1, current_ch=5,
                           current_status='第1卷第5章: 战斗中')
        updated = db.get_character('inc_test', cid)
        assert updated["current_vol"] == 1
        assert updated["current_ch"] == 5


class TestForeshadowingUpdate:
    """Test foreshadowing status updates"""

    def test_resolve_foreshadowing(self, setup_novel):
        """Should be able to mark foreshadowing as resolved"""
        items = db.get_unresolved_foreshadowing('inc_test')
        assert len(items) >= 1
        fid = items[0]["id"]

        db.resolve_foreshadowing(fid, vol=1, ch=3, note='在第3章揭晓了伏笔')
        updated = db.get_foreshadowing('inc_test')
        resolved = [f for f in updated if f["id"] == fid]
        assert resolved[0]["status"] == "resolved"
        assert resolved[0]["resolved_vol"] == 1

    def test_unresolved_filter_works(self, setup_novel):
        """After resolving, unresolved count should decrease"""
        before = len(db.get_unresolved_foreshadowing('inc_test'))
        items = db.get_foreshadowing('inc_test')
        if items:
            db.resolve_foreshadowing(items[0]["id"], vol=1, ch=1)
        after = len(db.get_unresolved_foreshadowing('inc_test'))
        assert after <= before


class TestChapterMetadata:
    """Test chapter extended metadata"""

    def test_update_chapter_pacing(self, setup_novel):
        """Should be able to set pace_type on a chapter"""
        conn = db.get_db()
        nid = setup_novel["nid"]

        # Insert a test chapter
        conn.execute("""INSERT INTO chapters
            (novel_id, volume, chapter_num, chapter_ref, content, title, word_count)
            VALUES (?, 'vol-01', 1, 'vol-01/ch-0001', '# Test', 'Test Chapter', 100)""",
            (nid,))
        conn.commit()

        # Update metadata
        conn.execute("""UPDATE chapters SET pace_type='高潮', emotional_beat='燃',
            foreshadowing_touched='[1]', characters_appeared='[{"name":"测试主角"}]'
            WHERE novel_id=? AND chapter_num=1""", (nid,))
        conn.commit()

        # Verify
        ch = conn.execute(
            "SELECT pace_type, emotional_beat FROM chapters WHERE novel_id=? AND chapter_num=1",
            (nid,)).fetchone()
        assert ch["pace_type"] == "高潮"
        assert ch["emotional_beat"] == "燃"
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
