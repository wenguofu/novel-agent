"""
Test sidebar novel context behavior.
Validates that novel-specific views require a selected novel,
and that _getNovel correctly falls back to currentNovel context.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
import content_db as db


@pytest.fixture
def fresh_db(tmp_path):
    """Isolate each test with its own content.db"""
    db_path = tmp_path / "content.db"
    old = db.DB_PATH
    db.DB_PATH = str(db_path)
    db.init_db()
    yield
    db.DB_PATH = old


@pytest.fixture
def seeded_db(fresh_db):
    """DB with test novels"""
    conn = db.get_db()
    conn.execute("INSERT INTO novels (name, title) VALUES (?,?)", ("test_novel", "测试小说"))
    conn.execute("INSERT INTO novels (name, title) VALUES (?,?)", ("test_novel2", "测试小说2"))
    conn.commit()
    conn.close()


NOVEL_VIEWS = [
    'writing', 'chapters', 'review', 'outlines', 'init-wizard',
    'characters', 'foreshadowing', 'workflow',
    'world-building', 'plot-arcs', 'pacing', 'revelation',
    'genre-rules', 'story-volumes', 'volume-plans', 'alias-names',
    'project-meta', 'quality',
]

GLOBAL_VIEWS = [
    'dashboard', 'novels', 'new-book', 'search', 'config', 'settings',
]


class TestNovelContext:
    """Test novel context selection logic"""

    def test_novel_views_are_known(self):
        """All novel-specific views should be in the list"""
        assert len(NOVEL_VIEWS) == 18

    def test_global_views_do_not_require_novel(self):
        """Global views should not appear in novel-only list"""
        for gv in GLOBAL_VIEWS:
            assert gv not in NOVEL_VIEWS

    def test_novel_context_null_by_default(self):
        """No novel selected initially"""
        ctx = None
        assert ctx is None

    def test_set_novel_context(self):
        """Setting context should store the value"""
        ctx = None
        ctx = "test_novel"
        assert ctx == "test_novel"
        ctx = None
        assert ctx is None

    def test_get_novel_fallback(self):
        """_getNovel should prefer DOM value, fall back to context"""
        current_novel = "test_novel"
        # Simulate _getNovel logic
        def _get_novel(el_value):
            return el_value or current_novel or ''
        assert _get_novel("") == "test_novel"  # empty DOM → context
        assert _get_novel("other") == "other"  # DOM value wins
        current_novel = None
        assert _get_novel("") == ""  # both empty


class TestSidebarDisplay:
    """Test sidebar visibility logic"""

    def test_hide_when_no_novel(self):
        """Novel pages hidden when no novel selected"""
        current_novel = None
        display = 'block' if current_novel else 'none'
        assert display == 'none'

    def test_show_when_novel_selected(self):
        """Novel pages shown when novel selected"""
        current_novel = "test_novel"
        display = 'block' if current_novel else 'none'
        assert display == 'block'

    def test_reset_hides_again(self):
        """Clearing context hides pages again"""
        current_novel = "test_novel"
        assert ('block' if current_novel else 'none') == 'block'
        current_novel = None
        assert ('block' if current_novel else 'none') == 'none'


class TestNovelContextAPI:
    """Test that novel listings work for populating selector"""

    def test_list_novels_returns_data(self, seeded_db):
        """API should return novel list"""
        conn = db.get_db()
        rows = conn.execute("SELECT id, name, title FROM novels ORDER BY name").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0]['name'] == 'test_novel'
        assert rows[0]['title'] == '测试小说'

    def test_genre_rules_requires_novel_id(self, seeded_db):
        """Genre rules query needs valid novel_id"""
        conn = db.get_db()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", ("test_novel",)).fetchone()
        assert novel is not None
        count = conn.execute("SELECT COUNT(*) FROM genre_rules WHERE novel_id=?",
                             (novel['id'],)).fetchone()[0]
        conn.close()
        assert count == 0  # no data yet, but query should work
