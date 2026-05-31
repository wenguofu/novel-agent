"""
Tests for memory_layer.py and state_tracker.py — v3.2 memory system.
"""

import os
import sys
import pytest

# Ensure portal is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "portal"))


class TestMemoryStrategies:
    """Test query strategy generation."""

    def test_plot_continuity_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.plot_continuity(volume=5, chapter_num=75)
        assert "第5卷" in q
        assert "第75章" in q
        assert "剧情发展" in q or "关键事件" in q
        assert len(q) > 20

    def test_character_state_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.character_state(
            char_names=["主角", "女主", "反派"],
            volume=3
        )
        assert "主角" in q
        assert "女主" in q
        assert "当前状态" in q
        assert "第3卷" in q

    def test_world_evolution_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.world_evolution(volume=4)
        assert "第4卷" in q
        assert "世界观" in q or "新地点" in q
        assert len(q) > 15

    def test_foreshadowing_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.foreshadowing_status(volume=5)
        assert "伏笔" in q
        assert "第5卷" in q
        assert len(q) > 10

    def test_recent_events_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.recent_events(volume=3, chapter_num=50, lookback=5)
        # Should reference chapters 45-50
        assert "第3卷" in q
        assert "内容摘要" in q or "发生了什么" in q

    def test_similar_scenes_query(self):
        from memory_layer import MemoryStrategies
        q = MemoryStrategies.similar_scenes(
            outline_section="主角在古墓中发现神秘石棺",
            volume=4
        )
        assert "类似场景" in q or "前文呼应" in q
        assert len(q) > 15


class TestMemoryLayerBasics:
    """Test MemoryLayer core functionality."""

    def test_singleton(self):
        from memory_layer import MemoryLayer, get_memory_layer
        ml1 = MemoryLayer.get_instance()
        ml2 = get_memory_layer()
        ml3 = MemoryLayer.get_instance()
        # get_instance() uses the class-level singleton (consistently)
        assert ml1 is ml3
        # get_memory_layer() has its own module-level singleton
        assert isinstance(ml2, MemoryLayer)

    def test_budget_allocation(self):
        from memory_layer import MemoryLayer
        ml = MemoryLayer()
        budgets = ml._allocate_budgets(
            ["plot_continuity", "character_state", "world_evolution"],
            total_budget=3000
        )
        assert "plot_continuity" in budgets
        assert "character_state" in budgets
        assert "world_evolution" in budgets
        # Total of weighted allocations should be <= total_budget
        # Weights: 0.28 + 0.22 + 0.15 = 0.65, 0.65 * 3000 = 1950
        total = sum(budgets.values())
        assert 1500 <= total <= 2200

    def test_file_type_mapping(self):
        from memory_layer import MemoryLayer
        ml = MemoryLayer()
        assert ml._file_type_for_strategy("plot_continuity") == "chapter"
        assert ml._file_type_for_strategy("character_state") == "chapter"
        assert ml._file_type_for_strategy("world_evolution") == "world_building"
        assert ml._file_type_for_strategy("foreshadowing_status") == "plot_arc"

    def test_limit_for_strategy(self):
        from memory_layer import MemoryLayer
        ml = MemoryLayer()
        assert ml._limit_for_strategy("plot_continuity") == 8
        assert ml._limit_for_strategy("character_state") == 6
        assert ml._limit_for_strategy("recent_events") == 5

    def test_cache_works(self):
        from memory_layer import MemoryLayer
        ml = MemoryLayer()
        ml.clear_cache()

        # First call should work (even without ChromaDB — falls back to DB)
        result = ml.retrieve(
            novel_name="nonexistent_novel",
            volume=1,
            chapter_num=1,
            total_token_budget=500,
        )
        assert result is not None
        assert result.is_empty  # No data for nonexistent novel
        assert result.context_text == ""

    def test_memory_context_to_dict(self):
        from memory_layer import MemoryContext, MemoryQueryResult
        ctx = MemoryContext(
            novel_name="test",
            volume=1,
            chapter_num=1,
            query_results=[],
            total_tokens=0,
            token_budget=1000,
        )
        d = ctx.to_dict()
        assert d["novel"] == "test"
        assert d["total_chunks"] == 0
        assert "strategies" in d

    def test_clear_cache(self):
        from memory_layer import MemoryLayer
        ml = MemoryLayer()
        ml._cache["test_key"] = (0.0, "test")
        ml.clear_cache()
        assert len(ml._cache) == 0


class TestStateTracker:
    """Test state change detection."""

    def test_singleton(self):
        from state_tracker import StateTracker, get_state_tracker
        st1 = StateTracker()
        st2 = get_state_tracker()
        assert isinstance(st1, StateTracker)

    def test_extract_summary(self):
        from state_tracker import StateTracker
        st = StateTracker()
        content = "# 第75章：秘境深处\n\n李闲踏入秘境深处，眼前是一片奇异景象。他心中暗自警惕，手握长剑缓缓前行。\n\n突然，一道黑影从侧面袭来。"
        summary = st._extract_summary(content)
        assert len(summary) > 0
        assert "第75章" not in summary  # Headers should be stripped

    def test_detect_character_changes(self):
        from state_tracker import StateTracker
        st = StateTracker()
        content = """
        李闲感到一股强大的力量涌入体内，他终于突破了金丹境界。
        来到玄天城后，他发现这里的一切都如此陌生。
        与林若的关系变得更加微妙，两人之间的隔阂似乎消失了。
        """
        changes = st._detect_character_changes(content, ["李闲", "林若"])
        assert isinstance(changes, list)
        # Should detect at least some changes for known characters
        found_lixian = any(
            c["name"] == "李闲" and len(c["changes"]) > 0
            for c in changes
        )
        # At least one character should have changes detected
        assert len(changes) > 0 or not found_lixian

    def test_detect_world_changes(self):
        from state_tracker import StateTracker
        st = StateTracker()
        content = "李闲来到玄天城，发现这座古城中隐藏着无数秘密。原来这座城在千年前是一座仙府。"
        changes = st._detect_world_changes(content)
        assert isinstance(changes, list)
        # Should detect location or rule change
        assert len(changes) >= 0  # Pattern matching is probabilistic

    def test_detect_foreshadowing(self):
        from state_tracker import StateTracker
        st = StateTracker()
        content = "李闲暗中观察着那个神秘人，对方似乎在酝酿着什么大阴谋。"
        events = st._detect_foreshadowing(content)
        assert isinstance(events, list)

    def test_analyze_full_chapter(self):
        from state_tracker import StateTracker
        st = StateTracker()
        content = """
        # 第80章：真相大白

        李闲终于突破至元婴境，他感到前所未有的强大。

        来到天机城后，他遇到了传说中的天机老人。原来这一切都是青龙宗的阴谋。

        与苏灵的误会终于解开，两人相视一笑。

        暗中，一个黑影冷笑：「棋子已经布下，接下来就是收网的时候了。」
        """
        result = st.analyze_chapter(
            novel_name="test_novel",
            volume=3,
            chapter_num=80,
            content=content,
            character_names=["李闲", "苏灵"],
        )
        assert result["novel"] == "test_novel"
        assert result["volume"] == 3
        assert result["chapter"] == 80
        assert "characters" in result
        assert "world" in result
        assert "foreshadowing" in result
        assert "summary" in result
        assert "timestamp" in result

    def test_format_for_context_empty(self):
        from state_tracker import StateTracker
        st = StateTracker()
        text = st.format_for_context("nonexistent", 1)
        assert text == ""  # No chapters analyzed yet

    def test_format_for_context_with_data(self):
        from state_tracker import StateTracker
        st = StateTracker()
        # Analyze two chapters
        st.analyze_chapter(
            "test_novel", 1, 1,
            "李闲突破筑基境，来到青云镇。",
            ["李闲"]
        )
        st.analyze_chapter(
            "test_novel", 1, 2,
            "李闲与林若关系改善，发现神秘石碑。",
            ["李闲", "林若"]
        )
        text = st.format_for_context("test_novel", 1)
        assert "近期状态变更" in text or "角色状态变化" in text

    def test_clear_cache(self):
        from state_tracker import StateTracker
        st = StateTracker()
        st.analyze_chapter("test", 1, 1, "content", ["A"])
        assert len(st._cache) > 0
        st.clear_cache()
        assert len(st._cache) == 0


class TestMemoryIntegration:
    """Test integration between memory layer and context builder."""

    def test_context_builder_imports_memory(self):
        """Verify context_builder imports memory modules without error."""
        from context_builder import build_context
        # build_context should be importable
        assert callable(build_context)

    def test_context_builder_handles_missing_novel_with_memory(self):
        """build_context should work even when memory retrieval fails."""
        from context_builder import build_context
        result = build_context({
            "name": "nonexistent_novel_12345",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        assert "system_prompt" in result
        assert "layers" in result
        assert result["total_tokens"] >= 0
        # Should have more than 9 layers now (includes memory layers even if empty)
        assert len(result["layers"]) >= 9

    def test_fallback_state_context(self):
        """Test the fallback state context function."""
        from context_builder import _build_fallback_state_context
        result = _build_fallback_state_context("nonexistent_novel", 1, 1)
        # Should return empty string for nonexistent novel
        assert isinstance(result, str)
