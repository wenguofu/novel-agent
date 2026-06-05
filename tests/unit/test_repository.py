"""Unit tests for portal/repository.py (M3.1 W2 Task 2.2).

Targets line coverage 52% -> 90% on Repository. We use the ``tmp_db``
fixture (declared in ``tests/unit/conftest.py``) to spin up a fresh
SQLite DB and exercise the real repository code path.

Tests are grouped by entity. We avoid asserting on internal SQLAlchemy
state — only on the dict shape that callers see.
"""
import pytest


@pytest.fixture
def repo(tmp_db):
    """Get a Repository singleton bound to the tmp DB.

    The import MUST happen inside the fixture body — at this point
    ``tmp_db`` has already reloaded the ``repository`` module so the
    fresh ``get_repo`` resolves to a Repository bound to the tmp DB.
    Importing at module scope would pin us to the original (real) DB.
    """
    from repository import get_repo
    return get_repo()


@pytest.fixture
def repo_with_novel(repo):
    """Repository with a single seeded novel named ``n1``."""
    repo.upsert_novel("n1", title="N1 Title", genre="xianxia")
    return repo


# ─── Novels ──────────────────────────────────────────────────────────────

class TestNovels:
    def test_upsert_creates(self, repo):
        out = repo.upsert_novel("n1", title="Hello", genre="xianxia")
        assert out is not None
        assert out["name"] == "n1"
        assert out["title"] == "Hello"

    def test_upsert_updates_existing(self, repo):
        repo.upsert_novel("n1", title="Old")
        repo.upsert_novel("n1", title="New")
        n = repo.get_novel("n1")
        assert n["title"] == "New"

    def test_get_novel_missing(self, repo):
        assert repo.get_novel("does-not-exist") is None

    def test_get_novel_by_id(self, repo):
        repo.upsert_novel("n1")
        n = repo.get_novel("n1")
        again = repo.get_novel_by_id(n["id"])
        assert again is not None
        assert again["name"] == "n1"

    def test_get_novel_by_id_missing(self, repo):
        assert repo.get_novel_by_id(999999) is None

    def test_list_novels(self, repo):
        repo.upsert_novel("a")
        repo.upsert_novel("b")
        names = [n["name"] for n in repo.list_novels()]
        assert "a" in names and "b" in names

    def test_delete_novel(self, repo):
        repo.upsert_novel("temp")
        assert repo.get_novel("temp") is not None
        repo.delete_novel("temp")
        assert repo.get_novel("temp") is None

    def test_delete_novel_missing(self, repo):
        # No-op: should not raise
        repo.delete_novel("ghost")


# ─── Outline ─────────────────────────────────────────────────────────────

class TestOutline:
    def test_upsert_and_get(self, repo_with_novel):
        repo = repo_with_novel
        out = repo.upsert_outline("n1", "vol-01", "outline content", word_count=120)
        assert out["volume"] == "vol-01"
        got = repo.get_outline("n1", "vol-01")
        assert got["content"] == "outline content"
        assert got["word_count"] == 120

    def test_upsert_updates_existing(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_outline("n1", "vol-01", "v1")
        repo.upsert_outline("n1", "vol-01", "v2", word_count=10)
        got = repo.get_outline("n1", "vol-01")
        assert got["content"] == "v2"
        assert got["word_count"] == 10

    def test_list_outlines(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_outline("n1", "vol-01", "a")
        repo.upsert_outline("n1", "vol-02", "b")
        items = repo.list_outlines("n1")
        assert len(items) == 2

    def test_delete_outline(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_outline("n1", "vol-01", "a")
        repo.delete_outline("n1", "vol-01")
        assert repo.get_outline("n1", "vol-01") is None

    def test_missing_novel_branches(self, repo):
        # All these should hit the `if not nid: return ...` branch.
        assert repo.get_outline("ghost", "v") is None
        assert repo.list_outlines("ghost") == []
        assert repo.upsert_outline("ghost", "v", "x") == {}
        repo.delete_outline("ghost", "v")  # no-op


# ─── Chapter ─────────────────────────────────────────────────────────────

class TestChapter:
    def test_upsert_and_get(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter(
            "n1", "v1-c1", volume="vol-01", chapter_num=1,
            title="第一章", content="text", word_count=100, content_hash="hash1",
        )
        ch = repo.get_chapter("n1", "v1-c1")
        assert ch["title"] == "第一章"
        assert ch["word_count"] == 100

    def test_upsert_updates(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "ref1", volume="vol-01", chapter_num=1,
                            content="x", title="A")
        repo.upsert_chapter("n1", "ref1", title="B")
        ch = repo.get_chapter("n1", "ref1")
        assert ch["title"] == "B"

    def test_get_chapter_by_num(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "ref-2", volume="vol-01", chapter_num=2, content="x")
        ch = repo.get_chapter_by_num("n1", "vol-01", 2)
        assert ch is not None
        assert ch["chapter_num"] == 2

    def test_get_chapter_by_num_missing(self, repo_with_novel):
        assert repo_with_novel.get_chapter_by_num("n1", "vol-01", 999) is None

    def test_list_chapters_all_and_filtered(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "r1", volume="vol-01", chapter_num=1, content="x")
        repo.upsert_chapter("n1", "r2", volume="vol-01", chapter_num=2, content="x")
        repo.upsert_chapter("n1", "r3", volume="vol-02", chapter_num=1, content="x")
        assert len(repo.list_chapters("n1")) == 3
        assert len(repo.list_chapters("n1", volume="vol-01")) == 2

    def test_get_previous_chapter(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "r1", volume="vol-01", chapter_num=1,
                            content="x", title="prev")
        repo.upsert_chapter("n1", "r2", volume="vol-01", chapter_num=2, content="x")
        prev = repo.get_previous_chapter("n1", "vol-01", 2)
        assert prev is not None
        assert prev["title"] == "prev"

    def test_get_chapter_content_hash(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "h1", volume="vol-01", chapter_num=1,
                            content="x", content_hash="abcd")
        assert repo.get_chapter_content_hash("n1", "h1") == "abcd"
        assert repo.get_chapter_content_hash("n1", "missing") is None

    def test_get_recent_chapters(self, repo_with_novel):
        repo = repo_with_novel
        for i in range(5):
            repo.upsert_chapter("n1", f"ref-{i}", volume="vol-01",
                                chapter_num=i, content="x")
        recent = repo.get_recent_chapters("n1", limit=3)
        assert len(recent) == 3

    def test_update_chapter_metadata(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "ref-1", volume="vol-01", chapter_num=1, content="x")
        repo.update_chapter_metadata("n1", "vol-01", 1, pace_type="fast", emotional_beat="climax")
        ch = repo.get_chapter("n1", "ref-1")
        assert ch["pace_type"] == "fast"
        assert ch["emotional_beat"] == "climax"

    def test_missing_novel_branches(self, repo):
        assert repo.get_chapter("ghost", "ref") is None
        assert repo.get_chapter_by_num("ghost", "v", 1) is None
        assert repo.list_chapters("ghost") == []
        assert repo.upsert_chapter("ghost", "ref") == {}
        assert repo.get_chapter_content_hash("ghost", "ref") is None
        assert repo.get_recent_chapters("ghost") == []
        repo.update_chapter_metadata("ghost", "v", 1, pace_type="x")  # no-op


# ─── Review ──────────────────────────────────────────────────────────────

class TestReview:
    def test_upsert_create_and_get(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_review("n1", "v1-c1", ai_review="good",
                           script_analyze_ok=1, word_count=100)
        r = repo.get_review("n1", "v1-c1")
        assert r["ai_review"] == "good"
        assert r["script_analyze_ok"] == 1

    def test_upsert_updates_when_ai_review_present(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_review("n1", "ref-1", ai_review="v1")
        repo.upsert_review("n1", "ref-1", ai_review="v2")
        r = repo.get_review("n1", "ref-1")
        assert r["ai_review"] == "v2"

    def test_list_reviews(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_review("n1", "r1", ai_review="a")
        repo.upsert_review("n1", "r2", ai_review="b")
        items = repo.list_reviews("n1")
        assert len(items) == 2

    def test_review_count(self, repo_with_novel):
        repo = repo_with_novel
        assert repo.get_review_count("n1") == 0
        repo.upsert_review("n1", "ref-1", ai_review="x")
        assert repo.get_review_count("n1") == 1

    def test_missing_novel_branches(self, repo):
        assert repo.get_review("ghost", "ref") is None
        assert repo.list_reviews("ghost") == []
        assert repo.upsert_review("ghost", "ref", ai_review="x") == {}
        assert repo.get_review_count("ghost") == 0


# ─── DangerIssue ─────────────────────────────────────────────────────────

class TestDangerIssue:
    def test_upsert_and_get(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_danger_issue("n1", "vol-01", 1, "暴恐内容")
        di = repo.get_danger_issue("n1", "vol-01", 1)
        assert di["content"] == "暴恐内容"

    def test_upsert_updates(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_danger_issue("n1", "vol-01", 1, "v1")
        repo.upsert_danger_issue("n1", "vol-01", 1, "v2")
        di = repo.get_danger_issue("n1", "vol-01", 1)
        assert di["content"] == "v2"

    def test_missing_novel_branches(self, repo):
        assert repo.get_danger_issue("ghost", "v", 1) is None
        assert repo.upsert_danger_issue("ghost", "v", 1, "x") == {}


# ─── Character ───────────────────────────────────────────────────────────

class TestCharacter:
    def test_add_and_get(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "李闲", role="主角", desire="求道", fear="心魔")
        assert cid is not None
        c = repo.get_character("n1", cid)
        assert c["name"] == "李闲"
        assert c["role"] == "主角"
        assert c["desire"] == "求道"

    def test_list_characters_orders_main_first(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_character("n1", "配角1", role="配角")
        repo.add_character("n1", "主角1", role="主角")
        repo.add_character("n1", "女主1", role="女主")
        names = [c["name"] for c in repo.list_characters("n1")]
        assert names[0] == "主角1"
        assert names[1] == "女主1"

    def test_list_characters_filter_by_role(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_character("n1", "甲", role="配角")
        repo.add_character("n1", "乙", role="主角")
        mains = repo.list_characters("n1", role="主角")
        assert len(mains) == 1
        assert mains[0]["name"] == "乙"

    def test_update_character(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "甲", role="配角")
        assert repo.update_character(cid, role="主角", desire="新欲望") is True
        c = repo.get_character("n1", cid)
        assert c["role"] == "主角"
        assert c["desire"] == "新欲望"

    def test_update_character_no_valid_fields(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "甲")
        # Only unknown keys -> nothing updated -> returns False
        assert repo.update_character(cid, bogus="x") is False

    def test_delete_character(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "甲")
        repo.delete_character(cid)
        assert repo.get_character("n1", cid) is None

    def test_list_characters_active_in_volume(self, repo_with_novel):
        repo = repo_with_novel
        # Main characters in current/past volume — included
        repo.add_character("n1", "主", role="主角", current_vol=1)
        repo.add_character("n1", "女主", role="女主", current_vol=2)
        # Side character in current volume — included
        repo.add_character("n1", "侧", role="配角", current_vol=2)
        # Future-volume character (vol=10) — must be excluded
        repo.add_character("n1", "远", role="配角", current_vol=10)
        actives = repo.list_characters_active_in_volume("n1", 2)
        names = [c["name"] for c in actives]
        assert "主" in names
        assert "女主" in names
        assert "侧" in names
        assert "远" not in names

    def test_list_characters_active_in_volume_excludes_future(self, repo_with_novel):
        """Regression for M3.2 W3 Bug #1: mains in future vol must be excluded."""
        repo = repo_with_novel
        # Main character in FUTURE vol — must NOT leak into current prompt
        repo.add_character("n1", "未来主角", role="主角", current_vol=10)
        # Villain active in current vol — included
        repo.add_character("n1", "当前反派", role="反派", current_vol=1)
        actives = repo.list_characters_active_in_volume("n1", 1)
        names = [c["name"] for c in actives]
        assert "未来主角" not in names
        assert "当前反派" in names

    def test_missing_novel_branches(self, repo):
        assert repo.get_character("ghost", 1) is None
        assert repo.list_characters("ghost") == []
        assert repo.add_character("ghost", "x") is None
        assert repo.list_characters_active_in_volume("ghost", 1) == []


# ─── CharacterEvent ──────────────────────────────────────────────────────

class TestCharacterEvent:
    def test_add_and_list(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "甲")
        eid = repo.add_character_event("n1", cid, "事件描述",
                                       event_type="状态变更", vol=1, ch=2)
        assert eid is not None
        events = repo.list_character_events(cid)
        assert len(events) == 1
        assert events[0]["description"] == "事件描述"

    def test_get_recent_character_events(self, repo_with_novel):
        repo = repo_with_novel
        cid = repo.add_character("n1", "甲")
        repo.add_character_event("n1", cid, "e1", vol=1, ch=1)
        repo.add_character_event("n1", cid, "e2", vol=2, ch=3)
        recent = repo.get_recent_character_events("n1", volume=2)
        assert len(recent) >= 1

    def test_missing_novel_branches(self, repo):
        assert repo.add_character_event("ghost", 1, "x") is None
        assert repo.get_recent_character_events("ghost", 1) == []


# ─── Foreshadowing ───────────────────────────────────────────────────────

class TestForeshadowing:
    def test_add_and_list(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing(
            "n1", "伏笔A", description="desc", introduced_vol=1,
            target_vol=3, priority="high",
        )
        assert fid is not None
        items = repo.list_foreshadowing("n1")
        assert any(f["name"] == "伏笔A" for f in items)

    def test_list_filter_status_and_volume(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing("n1", "f1", target_vol=2)
        repo.add_foreshadowing("n1", "f2", target_vol=5)
        items = repo.list_foreshadowing("n1", volume=2)
        names = [f["name"] for f in items]
        assert "f1" in names
        # Update one to resolved status, then filter
        repo.update_foreshadowing(fid, status="resolved")
        resolved = repo.list_foreshadowing("n1", status="resolved")
        assert len(resolved) == 1

    def test_get_unresolved(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_foreshadowing("n1", "f1", target_vol=2, introduced_vol=1)
        repo.add_foreshadowing("n1", "f2", target_vol=5)
        unresolved = repo.get_unresolved_foreshadowing("n1", current_vol=2)
        assert len(unresolved) >= 1

    def test_get_unresolved_no_volume(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_foreshadowing("n1", "fA")
        items = repo.get_unresolved_foreshadowing("n1")
        assert len(items) == 1

    def test_get_foreshadowing_for_volume(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_foreshadowing("n1", "due", target_vol=3, introduced_vol=1)
        repo.add_foreshadowing("n1", "overdue", target_vol=2, introduced_vol=1)
        repo.add_foreshadowing("n1", "recent", introduced_vol=3, target_vol=10)
        result = repo.get_foreshadowing_for_volume("n1", 3)
        assert "due_now" in result and "overdue" in result and "recent" in result
        assert any(d["name"] == "due" for d in result["due_now"])

    def test_update(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing("n1", "f")
        assert repo.update_foreshadowing(fid, description="updated") is True

    def test_update_no_valid_fields(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing("n1", "f")
        assert repo.update_foreshadowing(fid, bogus="x") is False

    def test_resolve_and_pending(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing("n1", "f", target_vol=2)
        repo.update_foreshadowing(fid, status="pending")
        pending = repo.list_pending_foreshadowing("n1")
        assert any(p["name"] == "f" for p in pending)
        repo.resolve_foreshadowing(fid, vol=2, ch=10, note="resolved by chapter 10")
        f_list = repo.list_foreshadowing("n1", status="resolved")
        assert any(f["id"] == fid for f in f_list)

    def test_resolve_missing(self, repo_with_novel):
        # No-op when fid not found
        repo_with_novel.resolve_foreshadowing(999999, 1, 1, note="x")

    def test_delete(self, repo_with_novel):
        repo = repo_with_novel
        fid = repo.add_foreshadowing("n1", "ftbd")
        repo.delete_foreshadowing(fid)
        assert not any(f["id"] == fid for f in repo.list_foreshadowing("n1"))

    def test_missing_novel_branches(self, repo):
        assert repo.add_foreshadowing("ghost", "x") is None
        assert repo.list_foreshadowing("ghost") == []
        assert repo.get_unresolved_foreshadowing("ghost") == []
        result = repo.get_foreshadowing_for_volume("ghost", 1)
        assert result == {"due_now": [], "overdue": [], "recent": []}


# ─── WorldBuilding ───────────────────────────────────────────────────────

class TestWorldBuilding:
    def test_add_and_list(self, repo_with_novel):
        repo = repo_with_novel
        wid = repo.add_world_building("n1", domain="power", name="灵力",
                                       content="灵力体系", related_vol=1)
        assert wid is not None
        items = repo.list_world_building("n1")
        assert any(w["name"] == "灵力" for w in items)

    def test_list_filter_domain(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_world_building("n1", "power", "灵力", "...", related_vol=1)
        repo.add_world_building("n1", "geo", "北域", "...", related_vol=1)
        power = repo.list_world_building("n1", domain="power")
        assert len(power) == 1 and power[0]["domain"] == "power"

    def test_get_for_volume(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_world_building("n1", "power", "灵力", "...", related_vol=2)
        items = repo.get_world_building_for_volume("n1", 2)
        assert len(items) >= 1

    def test_get_volume_plus_global(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_world_building("n1", "power", "近域", "...", related_vol=2)
        repo.add_world_building("n1", "power", "远域", "...", related_vol=10)
        items = repo.get_world_building_volume_plus_global("n1", 2)
        names = {w["name"] for w in items}
        assert "近域" in names
        assert "远域" in names

    def test_clear(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_world_building("n1", "power", "x", "...")
        repo.clear_world_building("n1")
        assert repo.list_world_building("n1") == []

    def test_missing_novel_branches(self, repo):
        assert repo.list_world_building("ghost") == []
        assert repo.add_world_building("ghost", "d", "n", "c") is None
        assert repo.get_world_building_for_volume("ghost", 1) == []
        assert repo.get_world_building_volume_plus_global("ghost", 1) == []
        repo.clear_world_building("ghost")  # no-op


# ─── PlotArc ─────────────────────────────────────────────────────────────

class TestPlotArc:
    def test_add_and_list(self, repo_with_novel):
        repo = repo_with_novel
        aid = repo.add_plot_arc("n1", "主线", arc_type="主线",
                                volume_start=1, volume_end=10, status="active")
        assert aid is not None
        items = repo.list_plot_arcs("n1")
        assert any(a["name"] == "主线" for a in items)

    def test_list_filter_status(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_plot_arc("n1", "active1", status="active")
        repo.add_plot_arc("n1", "done1", status="completed")
        actives = repo.list_plot_arcs("n1", status="active")
        assert len(actives) == 1

    def test_get_for_volume(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_plot_arc("n1", "arc", volume_start=1, volume_end=5, status="active")
        repo.add_plot_arc("n1", "later", volume_start=10, volume_end=20, status="active")
        items = repo.get_plot_arcs_for_volume("n1", 3)
        names = [a["name"] for a in items]
        assert "arc" in names
        assert "later" not in names

    def test_missing_novel_branches(self, repo):
        assert repo.list_plot_arcs("ghost") == []
        assert repo.get_plot_arcs_for_volume("ghost", 1) == []
        assert repo.add_plot_arc("ghost", "x") is None


# ─── PacingControl ───────────────────────────────────────────────────────

class TestPacingControl:
    def test_add_and_get(self, repo_with_novel):
        repo = repo_with_novel
        pid = repo.add_pacing("n1", volume=1, chapter_start=1, chapter_end=5,
                              pace_type="fast", notes="开局快节奏")
        assert pid is not None
        got = repo.get_pacing("n1", 1, 3)
        assert got is not None
        assert got["pace_type"] == "fast"

    def test_add_pacing_duplicate_is_noop(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_pacing("n1", volume=1, chapter_start=1, chapter_end=5, pace_type="fast")
        # Second insert with same key returns None and does not duplicate
        assert repo.add_pacing("n1", volume=1, chapter_start=1, chapter_end=10) is None

    def test_get_pacing_out_of_range(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_pacing("n1", volume=1, chapter_start=1, chapter_end=2)
        assert repo.get_pacing("n1", 1, 99) is None

    def test_missing_novel_branches(self, repo):
        assert repo.get_pacing("ghost", 1, 1) is None
        assert repo.add_pacing("ghost", 1, 1, 5) is None


# ─── RevelationSchedule ──────────────────────────────────────────────────

class TestRevelation:
    def test_add_and_get(self, repo_with_novel):
        repo = repo_with_novel
        rid = repo.add_revelation("n1", "真相", info_type="世界观",
                                  reveal_volume=3, reveal_chapter=5, content="...")
        assert rid is not None
        items = repo.get_revelations_for_volume("n1", 3)
        assert any(r["name"] == "真相" for r in items)

    def test_missing_novel_branches(self, repo):
        assert repo.get_revelations_for_volume("ghost", 1) == []
        assert repo.add_revelation("ghost", "x") is None


# ─── GenreRule ───────────────────────────────────────────────────────────

class TestGenreRule:
    def test_add_and_list(self, repo_with_novel):
        repo = repo_with_novel
        gid = repo.add_genre_rule("n1", "must_have", "金手指开局")
        assert gid is not None
        items = repo.list_genre_rules("n1")
        assert any(r["rule_category"] == "must_have" for r in items)

    def test_clear(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_genre_rule("n1", "x", "y")
        repo.clear_genre_rules("n1")
        assert repo.list_genre_rules("n1") == []

    def test_missing_novel_branches(self, repo):
        assert repo.list_genre_rules("ghost") == []
        assert repo.add_genre_rule("ghost", "x", "y") is None
        repo.clear_genre_rules("ghost")  # no-op


# ─── StoryVolume ─────────────────────────────────────────────────────────

class TestStoryVolume:
    def test_add_list_get(self, repo_with_novel):
        repo = repo_with_novel
        sid = repo.add_story_volume("n1", 1, vol_name="开篇", goal="出场",
                                    conflict="试炼", payoff="升级")
        assert sid is not None
        items = repo.list_story_volumes("n1")
        assert len(items) == 1
        got = repo.get_story_volume("n1", 1)
        assert got["vol_name"] == "开篇"

    def test_get_missing(self, repo_with_novel):
        assert repo_with_novel.get_story_volume("n1", 999) is None

    def test_clear(self, repo_with_novel):
        repo = repo_with_novel
        repo.add_story_volume("n1", 1)
        repo.clear_story_volumes("n1")
        assert repo.list_story_volumes("n1") == []

    def test_missing_novel_branches(self, repo):
        assert repo.add_story_volume("ghost", 1) is None
        assert repo.list_story_volumes("ghost") == []
        assert repo.get_story_volume("ghost", 1) is None
        repo.clear_story_volumes("ghost")  # no-op


# ─── VolumePlan ──────────────────────────────────────────────────────────

class TestVolumePlan:
    def test_upsert_and_get(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_volume_plan("n1", 1, title="开篇卷", plan_content="目标-冲突-收获")
        got = repo.get_volume_plan("n1", 1)
        assert got["title"] == "开篇卷"
        assert got["plan_content"] == "目标-冲突-收获"

    def test_upsert_updates(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_volume_plan("n1", 1, plan_content="v1")
        repo.upsert_volume_plan("n1", 1, plan_content="v2")
        assert repo.get_volume_plan("n1", 1)["plan_content"] == "v2"

    def test_list_and_clear(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_volume_plan("n1", 1)
        repo.upsert_volume_plan("n1", 2)
        assert len(repo.list_volume_plans("n1")) == 2
        repo.clear_volume_plans("n1")
        assert repo.list_volume_plans("n1") == []

    def test_missing_novel_branches(self, repo):
        assert repo.get_volume_plan("ghost", 1) is None
        assert repo.list_volume_plans("ghost") == []
        assert repo.upsert_volume_plan("ghost", 1, plan_content="x") == {}
        repo.clear_volume_plans("ghost")  # no-op


# ─── AliasName (novel-level) ────────────────────────────────────────────

class TestAliasName:
    def test_add_list_clear(self, repo_with_novel):
        repo = repo_with_novel
        aid = repo.add_alias_name("n1", "person", "李闲", description="主角别名")
        assert aid is not None
        assert len(repo.list_alias_names("n1")) == 1
        repo.clear_alias_names("n1")
        assert repo.list_alias_names("n1") == []

    def test_missing_novel_branches(self, repo):
        assert repo.list_alias_names("ghost") == []
        assert repo.add_alias_name("ghost", "x", "y") is None
        repo.clear_alias_names("ghost")  # no-op


# ─── ProjectMeta ─────────────────────────────────────────────────────────

class TestProjectMeta:
    def test_upsert_and_get(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_project_meta("n1", "tone", "凉冷")
        assert repo.get_project_meta("n1", "tone") == "凉冷"
        # Update path
        repo.upsert_project_meta("n1", "tone", "炽热")
        assert repo.get_project_meta("n1", "tone") == "炽热"

    def test_list_and_clear(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_project_meta("n1", "a", "1")
        repo.upsert_project_meta("n1", "b", "2")
        # Note: list_project_meta is defined twice in repository.py;
        # the second definition (the standard _row_to_dict shape) wins.
        items = repo.list_project_meta("n1")
        assert len(items) == 2
        repo.clear_project_meta("n1")
        assert repo.list_project_meta("n1") == []

    def test_get_missing(self, repo_with_novel):
        assert repo_with_novel.get_project_meta("n1", "nope") is None

    def test_missing_novel_branches(self, repo):
        assert repo.get_project_meta("ghost", "k") is None
        assert repo.list_project_meta("ghost") == []
        repo.upsert_project_meta("ghost", "k", "v")  # no-op
        repo.clear_project_meta("ghost")  # no-op


# ─── Search ──────────────────────────────────────────────────────────────

class TestSearch:
    def _seed(self, repo):
        repo.upsert_novel("n1")
        repo.upsert_chapter("n1", "c1", volume="vol-01", chapter_num=1,
                           title="第一章", content="李闲修仙路上遇到了同门", word_count=20)
        repo.upsert_outline("n1", "vol-01", "关于李闲的开篇大纲")
        repo.upsert_review("n1", "c1", ai_review="李闲风格独特", word_count=10)

    def test_search_chapters(self, repo):
        self._seed(repo)
        hits = repo.search_chapters("n1", "李闲")
        assert len(hits) == 1
        assert hits[0]["chapter_ref"] == "c1"

    def test_search_outlines(self, repo):
        self._seed(repo)
        hits = repo.search_outlines("n1", "大纲")
        assert len(hits) == 1
        assert hits[0]["volume"] == "vol-01"

    def test_search_reviews(self, repo):
        self._seed(repo)
        hits = repo.search_reviews("n1", "李闲")
        assert len(hits) == 1
        assert hits[0]["chapter_ref"] == "c1"

    def test_search_all_with_novel(self, repo):
        self._seed(repo)
        result = repo.search_all("李闲", novel_name="n1")
        assert len(result["chapters"]) == 1
        assert len(result["outlines"]) == 1  # outline mentions 李闲
        assert len(result["reviews"]) == 1

    def test_search_all_no_novel(self, repo):
        self._seed(repo)
        result = repo.search_all("李闲")
        assert len(result["chapters"]) == 1

    def test_search_all_missing_novel(self, repo):
        result = repo.search_all("anything", novel_name="ghost")
        assert result == {"chapters": [], "outlines": [], "reviews": []}

    def test_missing_novel_branches(self, repo):
        assert repo.search_chapters("ghost", "x") == []
        assert repo.search_outlines("ghost", "x") == []
        assert repo.search_reviews("ghost", "x") == []


# ─── Config / DeepSeekConfig ─────────────────────────────────────────────

class TestConfig:
    def test_set_get(self, repo):
        repo.set_config("k1", "v1")
        assert repo.get_config("k1") == "v1"

    def test_set_updates(self, repo):
        repo.set_config("k1", "v1")
        repo.set_config("k1", "v2")
        assert repo.get_config("k1") == "v2"

    def test_get_missing(self, repo):
        assert repo.get_config("nope") is None

    def test_load_all(self, repo):
        repo.set_config("a", "1")
        repo.set_config("b", "2")
        cfg = repo.load_all_config()
        assert cfg["a"] == "1" and cfg["b"] == "2"


# ─── Seeded Tables ───────────────────────────────────────────────────────

class TestSeededTables:
    def test_list_banned_words(self, repo):
        items = repo.list_banned_words()
        assert isinstance(items, list)
        assert len(items) >= 20  # init_config_seed inserts 20 default rows

    def test_list_compliance_rules(self, repo):
        items = repo.list_compliance_rules()
        assert isinstance(items, list)
        assert len(items) >= 4

    def test_list_style_presets(self, repo):
        items = repo.list_style_presets()
        names = [s["name"] for s in items]
        assert "金庸风" in names
        assert "辰东风" in names

    def test_get_style_preset_by_name(self, repo):
        s = repo.get_style_preset_by_name("金庸风")
        assert s is not None
        assert s["name"] == "金庸风"

    def test_get_style_preset_missing(self, repo):
        assert repo.get_style_preset_by_name("不存在") is None


# ─── Usage / DailyStat ───────────────────────────────────────────────────

class TestUsage:
    def test_log_usage_and_recent(self, repo):
        rid = repo.log_usage("deepseek-chat", "write", prompt_tokens=100,
                             completion_tokens=200, novel="n1", cost=0.05)
        assert rid is not None
        recent = repo.list_recent_usage(limit=10)
        assert len(recent) == 1
        assert recent[0]["model"] == "deepseek-chat"
        assert recent[0]["total_tokens"] == 300

    def test_get_total_usage_empty(self, repo):
        total = repo.get_total_usage()
        assert total["total_calls"] == 0
        assert total["total_tokens"] == 0

    def test_get_total_usage_after_logs(self, repo):
        repo.log_usage("m1", "op", 10, 20, cost=0.01)
        repo.log_usage("m1", "op", 5, 5, cost=0.005)
        total = repo.get_total_usage()
        assert total["total_calls"] == 2
        assert total["total_tokens"] == 40

    def test_upsert_daily_stats_insert_then_update(self, repo):
        repo.upsert_daily_stats("m1", "op", 100, 50, 0.01)
        stats = repo.get_usage_stats(days=5)
        assert len(stats) == 1
        first = stats[0]
        assert first["total_calls"] == 1
        assert first["total_tokens"] == 150
        # Second call updates the existing row
        repo.upsert_daily_stats("m1", "op", 10, 10, 0.005)
        stats2 = repo.get_usage_stats(days=5)
        assert stats2[0]["total_calls"] == 2
        assert stats2[0]["total_tokens"] == 170

    def test_upsert_daily_stats_multiple_models(self, repo):
        repo.upsert_daily_stats("m1", "op", 10, 10, 0.01)
        repo.upsert_daily_stats("m2", "op", 10, 10, 0.02)
        stats = repo.get_usage_stats(days=5)
        # All collapses to one row keyed by date
        assert len(stats) == 1
        assert stats[0]["total_calls"] == 2

    def test_get_usage_breakdown(self, repo):
        repo.log_usage("m1", "write", 10, 20)
        repo.log_usage("m2", "write", 5, 5)
        repo.log_usage("m1", "review", 1, 1)
        bd = repo.get_usage_breakdown(days=5)
        assert "total" in bd and "by_model" in bd and "by_operation" in bd
        assert bd["by_model"]["m1"]["calls"] == 2
        assert bd["by_operation"]["write"]["calls"] == 2


# ─── Stats / Aggregation ─────────────────────────────────────────────────

class TestNovelStats:
    def test_get_novel_stats(self, repo_with_novel):
        repo = repo_with_novel
        repo.upsert_chapter("n1", "c1", volume="vol-01", chapter_num=1,
                            content="x", word_count=100)
        repo.upsert_chapter("n1", "c2", volume="vol-01", chapter_num=2,
                            content="x", word_count=200)
        repo.upsert_outline("n1", "vol-01", "content")
        repo.upsert_review("n1", "c1", ai_review="ok")
        stats = repo.get_novel_stats("n1")
        assert stats["total_chapters"] == 2
        assert stats["total_words"] == 300
        assert stats["total_outlines"] == 1
        assert stats["total_reviews"] == 1
        assert len(stats["recent_chapters"]) == 2

    def test_get_novel_stats_missing(self, repo):
        assert repo.get_novel_stats("ghost") is None


# ─── Config CRUD: BannedWord / ComplianceRule / StylePreset / AliasReg ──

class TestConfigCRUD:
    def test_banned_word_lifecycle(self, repo):
        bid = repo.add_banned_word("禁词", category="测试", replacement="替换", severity="warn")
        assert bid is not None
        assert repo.update_banned_word(bid, replacement="新替换") is True
        words = repo.list_banned_words()
        assert any(w["id"] == bid and w["replacement"] == "新替换" for w in words)
        repo.delete_banned_word(bid)
        assert not any(w["id"] == bid for w in repo.list_banned_words())

    def test_update_banned_word_missing(self, repo):
        # Missing id -> _update_config_row returns False
        assert repo.update_banned_word(999999, replacement="x") is False

    def test_update_banned_word_no_valid_fields(self, repo):
        bid = repo.add_banned_word("a")
        # Filtered to empty kwargs -> still returns True per _update_config_row
        # (only updated_at touched). But banned_words doesn't have updated_at, so
        # this just exercises the early-return branch on empty allowed kwargs.
        result = repo.update_banned_word(bid, bogus="x")
        assert result is True

    def test_compliance_rule_lifecycle(self, repo):
        rid = repo.add_compliance_rule("custom_key", "custom_value",
                                       description="d", category="general")
        assert rid is not None
        assert repo.update_compliance_rule(rid, rule_value="updated") is True
        rules = repo.list_compliance_rules()
        assert any(r["id"] == rid and r["rule_value"] == "updated" for r in rules)
        repo.delete_compliance_rule(rid)
        assert not any(r["id"] == rid for r in repo.list_compliance_rules())

    def test_update_compliance_rule_missing(self, repo):
        assert repo.update_compliance_rule(999999, rule_value="x") is False

    def test_style_preset_lifecycle(self, repo):
        sid = repo.add_style_preset("自定义风", description="desc", prompt="prompt")
        assert sid is not None
        assert repo.update_style_preset(sid, description="新描述") is True
        presets = repo.list_style_presets()
        assert any(s["id"] == sid and s["description"] == "新描述" for s in presets)
        repo.delete_style_preset(sid)
        assert not any(s["id"] == sid for s in repo.list_style_presets())

    def test_update_style_preset_missing(self, repo):
        assert repo.update_style_preset(999999, name="x") is False


# ─── AliasRegistry ───────────────────────────────────────────────────────

class TestAliasRegistry:
    def test_lifecycle(self, repo):
        assert repo.list_alias_registry() == []
        aid = repo.add_alias_registry("北京", "上京", category="地名", notes="首都")
        assert aid is not None
        assert len(repo.list_alias_registry()) == 1
        assert repo.update_alias_registry(aid, alias="上京新") is True
        items = repo.list_alias_registry()
        assert items[0]["alias"] == "上京新"
        repo.delete_alias_registry(aid)
        assert repo.list_alias_registry() == []

    def test_update_missing(self, repo):
        assert repo.update_alias_registry(999999, alias="x") is False


# ─── Init seed (idempotency) ─────────────────────────────────────────────

class TestInitConfigSeed:
    def test_seed_is_idempotent(self, repo):
        # Fixture already calls init_config_seed once. Re-run to exercise
        # the "already exists, skip" branches.
        before = len(repo.list_banned_words())
        repo.init_config_seed()
        after = len(repo.list_banned_words())
        assert before == after
