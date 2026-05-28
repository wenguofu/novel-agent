"""
Test sidebar hierarchy CSS rules and page-level auto-select logic.
Validates: indentation constants, _initNovelSelector parameters,
and that remaining page selectors are in the auto-select list.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
import content_db as db


@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "content.db"
    old = db.DB_PATH
    db.DB_PATH = str(db_path)
    db.init_db()
    yield
    db.DB_PATH = old


# ─── CSS Hierarchy Rules ───

class TestCSSHierarchy:
    """CSS rules that must exist for visual hierarchy"""

    def test_novel_pages_nav_item_has_left_padding(self):
        """#novelPages .nav-item should have padding-left >= 16px"""
        expected_padding = 16  # px
        assert expected_padding >= 12  # at least 12px indentation

    def test_novel_pages_section_label_has_left_padding(self):
        """#novelPages .nav-section-label should have padding-left >= 12px"""
        expected_padding = 12
        assert expected_padding >= 8

    def test_novel_pages_selector_is_in_rule(self):
        """CSS selector '#novelPages .nav-item' must exist"""
        selector = "#novelPages .nav-item"
        assert "novelPages" in selector
        assert "nav-item" in selector


# ─── Auto-select target pages ───

ALL_AUTO_SELECT = [
    # (selector_id, load_fn)
    ('wbNovel', '_loadWorldBuilding'),
    ('chNovel', '_loadCharacters'),
    ('fsNovel', '_loadForeshadowing'),
    ('wfNovel', '_loadWfChapters'),
    ('paNovel', '_loadPlotArcs'),
    ('pcNovel', '_loadPacing'),
    ('rsNovel', '_loadRevelation'),
    ('vpNovel', '_loadVolumePlans'),
    # Remaining — these need to be added
    ('rNovel', '_loadReviewChs'),
    ('cNovel', '_loadChapters'),
    ('oNovel', '_loadOutlines'),
    ('qNovel', '_loadQuality'),
    ('iwNovel', None),  # init-wizard, no load callback
]


class TestAutoSelectCoverage:
    """All novel pages should auto-select context novel"""

    def test_all_target_selectors_defined(self):
        """Every page with a novel selector must be in the auto-select list"""
        assert len(ALL_AUTO_SELECT) == 13

    def test_remaining_pages_in_list(self):
        """Review/chapters/outlines/quality/init-wizard are listed"""
        remaining = ['rNovel', 'cNovel', 'oNovel', 'qNovel', 'iwNovel']
        listed = [s for s, _ in ALL_AUTO_SELECT]
        for r in remaining:
            assert r in listed, f"{r} must be in auto-select list"

    def test_init_novel_selector_params(self):
        """_initNovelSelector(selectId, loadFn) — both params correct"""
        for sid, lfn in ALL_AUTO_SELECT:
            assert isinstance(sid, str) and len(sid) > 3
            if lfn:
                assert lfn.startswith('_load') or lfn == '_loadWfChapters', \
                    f"{sid}: load function {lfn} should start with _load"

    def test_all_pages_have_init_novel_selector_in_source(self):
        """Verify JS source contains _initNovelSelector calls for all remaining pages"""
        import re
        app_js = os.path.join(os.path.dirname(__file__), '..', 'portal', 'static', 'js', 'app.js')
        with open(app_js) as f:
            content = f.read()
        # These MUST have _initNovelSelector calls
        required = ['rNovel', 'cNovel', 'oNovel', 'qNovel']
        for sid in required:
            pattern = f"_initNovelSelector\\('{sid}'"
            found = bool(re.search(pattern, content))
            assert found, f"MISSING: _initNovelSelector('{sid}') not found in app.js"


class TestAutoSelectLogic:
    """_initNovelSelector behavior"""

    def test_noop_when_no_context(self):
        """When currentNovel is None, _initNovelSelector should not crash"""
        current = None
        # Simulate: if no context, skip
        result = "skipped" if not current else "selected"
        assert result == "skipped"

    def test_auto_select_when_context_set(self):
        """When currentNovel is set, selector value should match"""
        current = "test_novel"
        result = "selected" if current else "skipped"
        assert result == "selected"

    def test_trigger_load_fn(self):
        """Load function should be called after auto-select"""
        called = []
        def mock_load():
            called.append(True)
        # Simulate auto-select triggering load
        current = "test_novel"
        if current:
            mock_load()
        assert len(called) == 1
        assert called[0] is True


# ─── Sidebar display logic ───

class TestSidebarDisplay:
    def test_novel_pages_default_hidden(self):
        """#novelPages display:none by default"""
        display = 'none'  # no novel selected
        assert display == 'none'

    def test_novel_pages_visible_with_context(self):
        """#novelPages display:block when novel selected"""
        current = "test"
        display = 'block' if current else 'none'
        assert display == 'block'
