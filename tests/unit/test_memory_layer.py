"""Unit tests for portal/memory_layer.py (M3.1 W2 T2.7.5).

Targets line coverage 75% -> 90%+. Tests the multi-strategy RAG
memory layer's static strategies, cache, budget allocation, and
the formatted output. The actual ChromaDB / FTS5 backend paths
are mocked to keep tests fast and isolated.
"""
import time
from unittest.mock import patch, MagicMock

import pytest

import memory_layer
from memory_layer import (
    MemoryResult,
    MemoryQueryResult,
    MemoryContext,
    MemoryStrategies,
    MemoryLayer,
    get_memory_layer,
    retrieve_memory,
)


# ── MemoryResult / MemoryQueryResult dataclasses ───────────────────────

class TestDataclasses:
    def test_memory_result_defaults(self):
        r = MemoryResult(content="x", score=0.5, source="s", file_type="chapter")
        assert r.volume is None
        assert r.chapter is None
        assert r.title == ""
        assert r.characters == []
        assert r.char_count == 0

    def test_memory_result_full(self):
        r = MemoryResult(
            content="x", score=0.5, source="s", file_type="chapter",
            volume=2, chapter=10, title="t", characters=["A"], char_count=100
        )
        assert r.volume == 2
        assert r.chapter == 10
        assert r.title == "t"
        assert r.characters == ["A"]
        assert r.char_count == 100

    def test_memory_query_result(self):
        qr = MemoryQueryResult(
            strategy="plot_continuity",
            query_text="q",
            results=[],
            tokens_used=100,
            tokens_budget=500,
        )
        assert qr.strategy == "plot_continuity"
        assert qr.query_text == "q"
        assert qr.results == []
        assert qr.tokens_used == 100
        assert qr.tokens_budget == 500

    def test_memory_context(self):
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[], total_tokens=0, token_budget=1000,
        )
        assert ctx.novel_name == "n"
        assert ctx.volume == 1
        assert ctx.chapter_num == 1
        assert ctx.query_results == []
        assert ctx.total_tokens == 0
        assert ctx.token_budget == 1000


# ── MemoryStrategies (static methods) ──────────────────────────────────

class TestMemoryStrategies:
    def test_plot_continuity(self):
        q = MemoryStrategies.plot_continuity(volume=3, chapter_num=42)
        assert "第3卷" in q
        assert "第42章" in q
        assert "剧情" in q

    def test_character_state(self):
        q = MemoryStrategies.character_state(char_names=["主角", "女主"], volume=5)
        assert "主角" in q
        assert "女主" in q
        assert "第5卷" in q

    def test_character_state_truncates_to_8(self):
        names = [f"角色{i}" for i in range(20)]
        q = MemoryStrategies.character_state(char_names=names, volume=1)
        # Only first 8 should be in the query
        assert "角色7" in q
        assert "角色8" not in q
        assert "角色19" not in q

    def test_world_evolution(self):
        q = MemoryStrategies.world_evolution(volume=2)
        assert "第2卷" in q
        assert "世界观" in q

    def test_foreshadowing_status(self):
        q = MemoryStrategies.foreshadowing_status(volume=1)
        assert "第1卷" in q
        assert "伏笔" in q

    def test_similar_scenes_with_outline(self):
        q = MemoryStrategies.similar_scenes(outline_section="主角与反派决战", volume=3)
        # When outline is provided, it replaces the volume in the base
        assert "主角" in q
        assert "反派决战" in q
        assert "第3卷" not in q

    def test_similar_scenes_without_outline(self):
        q = MemoryStrategies.similar_scenes(outline_section="", volume=3)
        # Falls back to "第3卷" as base
        assert "第3卷" in q

    def test_similar_scenes_truncates_to_200(self):
        outline = "x" * 500
        q = MemoryStrategies.similar_scenes(outline_section=outline, volume=1)
        # Outline is truncated to 200 chars
        assert "x" * 200 in q
        assert "x" * 201 not in q

    def test_recent_events_default_lookback(self):
        q = MemoryStrategies.recent_events(volume=3, chapter_num=20)
        # Lookback=5 -> start_ch = 20-5 = 15
        assert "第15章" in q
        assert "第20章" in q

    def test_recent_events_min_chapter_1(self):
        q = MemoryStrategies.recent_events(volume=1, chapter_num=2)
        # max(1, 2-5) = 1
        assert "第1章" in q

    def test_recent_events_custom_lookback(self):
        q = MemoryStrategies.recent_events(volume=2, chapter_num=20, lookback=10)
        # 20-10 = 10
        assert "第10章" in q
        assert "第20章" in q

    def test_character_arc_progress(self):
        q = MemoryStrategies.character_arc_progress(char_name="林风", volume=5)
        assert "林风" in q
        assert "第5卷" in q
        assert "成长弧线" in q


# ── MemoryLayer basics ─────────────────────────────────────────────────

class TestMemoryLayerInit:
    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_init(self):
        ml = MemoryLayer()
        assert ml._cache == {}
        assert ml._cache_ttl == 120.0
        assert ml._cache_lock is not None

    def test_singleton(self):
        memory_layer.MemoryLayer._instance = None
        a = MemoryLayer.get_instance()
        b = MemoryLayer.get_instance()
        assert a is b
        # Reset for next test
        memory_layer.MemoryLayer._instance = None


# ── retrieve: cache ─────────────────────────────────────────────────────

class TestRetrieveCache:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_cache_hit_within_ttl(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            ctx1 = ml.retrieve("novel", 1, 1)
            # Second call should hit cache
            ctx2 = ml.retrieve("novel", 1, 1)
        assert ctx1 is ctx2

    def test_cache_miss_after_ttl(self):
        ml = MemoryLayer()
        ml._cache_ttl = 0.001
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }) as mock_fb:
            ml.retrieve("novel", 1, 1)
            time.sleep(0.01)
            ml.retrieve("novel", 1, 1)
        # Cache miss -> fallback called twice
        assert mock_fb.call_count == 2

    def test_cache_key_includes_character_names(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            ctx1 = ml.retrieve("novel", 1, 1, character_names=["A"])
            ctx2 = ml.retrieve("novel", 1, 1, character_names=["B"])
        # Different character names -> different cache key -> different contexts
        assert ctx1 is not ctx2

    def test_cache_key_uses_first_5_characters(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            # 6th+ characters should be ignored in the cache key
            ctx1 = ml.retrieve("novel", 1, 1, character_names=["A", "B", "C", "D", "E"])
            ctx2 = ml.retrieve("novel", 1, 1, character_names=["A", "B", "C", "D", "E", "F", "G"])
        # Same first 5 characters -> same cache key -> same context object
        assert ctx1 is ctx2


# ── retrieve: fallback path ────────────────────────────────────────────

class TestRetrieveFallback:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_uses_fallback_when_chroma_unavailable(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }) as mock_fb:
            ml.retrieve("novel", 1, 1)
        mock_fb.assert_called_once()

    def test_uses_rag_when_chroma_available(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=True), \
             patch("memory_layer._rag_query", return_value={
                 "results": [], "total_tokens": 0
             }) as mock_rag:
            ml.retrieve("novel", 1, 1)
        mock_rag.assert_called_once()

    def test_parses_results_into_memory_query_results(self):
        ml = MemoryLayer()
        raw = {
            "results": [{
                "category": "plot_continuity",
                "chunks": [{
                    "content": "chunk content",
                    "score": 0.8,
                    "source": "src",
                    "file_type": "chapter",
                    "volume": 1,
                    "chapter": 5,
                    "title": "t",
                    "characters": ["A"],
                    "char_count": 100,
                }],
                "tokens_used": 50,
                "tokens_requested": 100,
            }],
            "total_tokens": 50,
        }
        with patch("memory_layer._is_chroma_available", return_value=True), \
             patch("memory_layer._rag_query", return_value=raw):
            ctx = ml.retrieve("novel", 1, 1)
        assert len(ctx.query_results) == 1
        assert ctx.query_results[0].strategy == "plot_continuity"
        assert len(ctx.query_results[0].results) == 1
        assert ctx.query_results[0].results[0].content == "chunk content"
        assert ctx.query_results[0].results[0].score == 0.8
        assert ctx.query_results[0].tokens_used == 50
        assert ctx.query_results[0].tokens_budget == 100

    def test_parses_results_defaults(self):
        ml = MemoryLayer()
        # Result with minimal fields; many should default
        raw = {
            "results": [{
                "category": "unknown_strategy",
                "chunks": [{"content": "x"}],
            }],
            "total_tokens": 0,
        }
        with patch("memory_layer._is_chroma_available", return_value=True), \
             patch("memory_layer._rag_query", return_value=raw):
            ctx = ml.retrieve("novel", 1, 1)
        chunk = ctx.query_results[0].results[0]
        assert chunk.score == 0.0
        assert chunk.source == ""
        assert chunk.file_type == ""
        assert chunk.title == ""
        assert chunk.characters == []
        assert chunk.char_count == 0

    def test_default_strategies(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }) as mock_fb:
            ml.retrieve("novel", 1, 1)
        # Inspect the categories passed to fallback
        args = mock_fb.call_args
        categories = args[0][1]  # second positional arg
        strategies = [c["category"] for c in categories]
        assert "plot_continuity" in strategies
        assert "character_state" in strategies
        assert "world_evolution" in strategies
        assert "foreshadowing_status" in strategies
        assert "recent_events" in strategies

    def test_custom_strategies(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }) as mock_fb:
            ml.retrieve("novel", 1, 1, strategies=["plot_continuity"])
        args = mock_fb.call_args
        categories = args[0][1]
        assert len(categories) == 1
        assert categories[0]["category"] == "plot_continuity"

    def test_cache_prunes_above_50(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            for i in range(55):
                ml.retrieve("novel", 1, i)
        # Cache should be capped at 50
        assert len(ml._cache) <= 50

    def test_total_tokens_in_context(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 42, "max_tokens": 1000
             }):
            ctx = ml.retrieve("novel", 1, 1)
        assert ctx.total_tokens == 42
        assert ctx.token_budget == 3000  # default


# ── _build_query ───────────────────────────────────────────────────────

class TestBuildQuery:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_known_strategy(self):
        ml = MemoryLayer()
        q = ml._build_query("plot_continuity", 3, 10, [], "")
        assert "第3卷" in q
        assert "第10章" in q

    def test_similar_scenes_strategy(self):
        ml = MemoryLayer()
        q = ml._build_query("similar_scenes", 2, 5, [], "测试 outline")
        # When outline is provided, volume is NOT in the base
        assert "测试" in q
        assert "第2卷" not in q

    def test_recent_events_strategy(self):
        ml = MemoryLayer()
        q = ml._build_query("recent_events", 3, 20, [], "")
        assert "第15章" in q
        assert "第3卷" in q

    def test_character_state_strategy(self):
        ml = MemoryLayer()
        q = ml._build_query("character_state", 5, 10, ["林风"], "")
        assert "林风" in q
        assert "第5卷" in q

    def test_unknown_strategy(self):
        ml = MemoryLayer()
        q = ml._build_query("nonexistent_strategy", 1, 1, [], "")
        assert q == ""

    def test_character_arc_not_in_handlers(self):
        # character_arc_progress is defined as a strategy but not wired
        # into _build_query's dispatch table; should return "".
        ml = MemoryLayer()
        q = ml._build_query("character_arc_progress", 1, 1, [], "")
        assert q == ""


# ── _file_type_for_strategy ───────────────────────────────────────────

class TestFileTypeForStrategy:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_plot_continuity(self):
        assert MemoryLayer()._file_type_for_strategy("plot_continuity") == "chapter"

    def test_character_state(self):
        assert MemoryLayer()._file_type_for_strategy("character_state") == "chapter"

    def test_world_evolution(self):
        assert MemoryLayer()._file_type_for_strategy("world_evolution") == "world_building"

    def test_foreshadowing_status(self):
        assert MemoryLayer()._file_type_for_strategy("foreshadowing_status") == "plot_arc"

    def test_similar_scenes(self):
        assert MemoryLayer()._file_type_for_strategy("similar_scenes") == "chapter"

    def test_recent_events(self):
        assert MemoryLayer()._file_type_for_strategy("recent_events") == "chapter"

    def test_character_arc(self):
        assert MemoryLayer()._file_type_for_strategy("character_arc") == "chapter"

    def test_unknown_strategy(self):
        assert MemoryLayer()._file_type_for_strategy("unknown") is None


# ── _limit_for_strategy ────────────────────────────────────────────────

class TestLimitForStrategy:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_plot_continuity(self):
        assert MemoryLayer()._limit_for_strategy("plot_continuity") == 8

    def test_character_state(self):
        assert MemoryLayer()._limit_for_strategy("character_state") == 6

    def test_world_evolution(self):
        assert MemoryLayer()._limit_for_strategy("world_evolution") == 5

    def test_foreshadowing_status(self):
        assert MemoryLayer()._limit_for_strategy("foreshadowing_status") == 5

    def test_similar_scenes(self):
        assert MemoryLayer()._limit_for_strategy("similar_scenes") == 5

    def test_recent_events(self):
        assert MemoryLayer()._limit_for_strategy("recent_events") == 5

    def test_character_arc(self):
        assert MemoryLayer()._limit_for_strategy("character_arc") == 5

    def test_default_5(self):
        assert MemoryLayer()._limit_for_strategy("unknown") == 5


# ── _allocate_budgets ──────────────────────────────────────────────────

class TestAllocateBudgets:
    def test_known_strategy(self):
        ml = MemoryLayer()
        budgets = ml._allocate_budgets(["plot_continuity"], total_budget=1000)
        assert budgets["plot_continuity"] == 280  # 1000 * 0.28

    def test_unknown_strategy_uses_default_weight(self):
        ml = MemoryLayer()
        budgets = ml._allocate_budgets(["unknown"], total_budget=1000)
        assert budgets["unknown"] == 100  # 1000 * 0.1 (default)

    def test_multiple_strategies_sum(self):
        ml = MemoryLayer()
        budgets = ml._allocate_budgets(
            ["plot_continuity", "character_state", "world_evolution"],
            total_budget=1000,
        )
        # Allocations: 280 + 220 + 150 = 650
        assert budgets["plot_continuity"] == 280
        assert budgets["character_state"] == 220
        assert budgets["world_evolution"] == 150

    def test_empty_strategies(self):
        ml = MemoryLayer()
        budgets = ml._allocate_budgets([], total_budget=1000)
        assert budgets == {}

    def test_all_known_strategies(self):
        ml = MemoryLayer()
        strategies = [
            "plot_continuity", "character_state", "world_evolution",
            "foreshadowing_status", "recent_events", "similar_scenes",
        ]
        budgets = ml._allocate_budgets(strategies, total_budget=1000)
        # 280 + 220 + 150 + 150 + 120 + 80 = 1000
        assert budgets["plot_continuity"] == 280
        assert budgets["character_state"] == 220
        assert budgets["world_evolution"] == 150
        assert budgets["foreshadowing_status"] == 150
        assert budgets["recent_events"] == 120
        assert budgets["similar_scenes"] == 80


# ── _fallback_db_retrieval ─────────────────────────────────────────────

class TestFallbackDbRetrieval:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_empty_results(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [], "outlines": []
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 100, "limit": 5
            }])
        assert result["results"][0]["chunks"] == []

    def test_collects_chapter_chunks(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [
                {"snippet": "test content", "chapter_ref": "ch-001"},
                {"snippet": "more content", "chapter_ref": "ch-002"},
            ],
            "outlines": []
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 10000, "limit": 5
            }])
        chunks = result["results"][0]["chunks"]
        assert len(chunks) == 2
        assert chunks[0]["file_type"] == "chapter"
        assert chunks[0]["content"] == "test content"
        assert chunks[0]["source"] == "ch-001"
        assert chunks[0]["score"] == 0.5

    def test_collects_outline_chunks(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [],
            "outlines": [
                {"snippet": "outline content", "volume": "vol-01"},
            ],
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 10000, "limit": 5
            }])
        chunks = result["results"][0]["chunks"]
        assert len(chunks) == 1
        assert chunks[0]["file_type"] == "outline"
        assert chunks[0]["source"] == "vol-01"
        assert chunks[0]["score"] == 0.4

    def test_respects_token_budget(self):
        ml = MemoryLayer()
        # 10 Chinese chunks, each 100 chars. count_tokens("测"*100) = int(100*1.5) = 150.
        # Budget = 250. First chunk: 150. Second: 150+150=300 > 250. Stop.
        with patch("content_db.search_all", return_value={
            "chapters": [
                {"snippet": "测" * 100, "chapter_ref": f"ch-{i}"}
                for i in range(10)
            ],
            "outlines": []
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 250, "limit": 10
            }])
        chunks = result["results"][0]["chunks"]
        # Only the first chunk fits in 250 tokens
        assert len(chunks) == 1

    def test_chapter_content_truncated_to_800(self):
        ml = MemoryLayer()
        long_snippet = "y" * 2000
        with patch("content_db.search_all", return_value={
            "chapters": [{"snippet": long_snippet, "chapter_ref": "ch-1"}],
            "outlines": []
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 100000, "limit": 5
            }])
        chunk = result["results"][0]["chunks"][0]
        assert len(chunk["content"]) == 800

    def test_outline_content_truncated_to_500(self):
        ml = MemoryLayer()
        long_snippet = "z" * 2000
        with patch("content_db.search_all", return_value={
            "chapters": [],
            "outlines": [{"snippet": long_snippet, "volume": "v1"}],
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 100000, "limit": 5
            }])
        chunk = result["results"][0]["chunks"][0]
        assert len(chunk["content"]) == 500

    def test_outline_blocked_when_chapters_use_budget(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [{"snippet": "x" * 1000, "chapter_ref": "ch-1"}],
            "outlines": [{"snippet": "y" * 100, "volume": "v1"}],
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 500, "limit": 5
            }])
        # Chapter uses up most of the budget; outline may not fit
        chunks = result["results"][0]["chunks"]
        # At least the chapter is there
        assert any(c["file_type"] == "chapter" for c in chunks)

    def test_returns_correct_structure(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [], "outlines": []
        }):
            result = ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "q", "max_tokens": 100, "limit": 5
            }])
        assert "results" in result
        assert "total_tokens" in result
        assert "max_tokens" in result
        assert result["mode"] == "db-fts5-fallback"
        assert result["max_tokens"] == 100

    def test_total_tokens_accumulated(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [
                {"snippet": "a" * 100, "chapter_ref": "ch-1"},
            ],
            "outlines": [],
        }):
            result = ml._fallback_db_retrieval("novel", [
                {"category": "a", "query": "q", "max_tokens": 1000, "limit": 5},
                {"category": "b", "query": "q", "max_tokens": 1000, "limit": 5},
            ])
        # total_tokens = sum of tokens_used across categories
        assert result["total_tokens"] > 0
        assert result["max_tokens"] == 2000  # 1000 + 1000

    def test_search_passed_correct_args(self):
        ml = MemoryLayer()
        with patch("content_db.search_all", return_value={
            "chapters": [], "outlines": []
        }) as mock_search:
            ml._fallback_db_retrieval("novel", [{
                "category": "x", "query": "my query", "max_tokens": 500, "limit": 7
            }])
        mock_search.assert_called_once_with("my query", novel_name="novel", limit=7)


# ── clear_cache ────────────────────────────────────────────────────────

class TestClearCache:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_clears_cache(self):
        ml = MemoryLayer()
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch.object(ml, "_fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            ml.retrieve("novel", 1, 1)
        assert ml._cache != {}
        ml.clear_cache()
        assert ml._cache == {}


# ── MemoryContext.context_text ─────────────────────────────────────────

class TestContextText:
    def test_empty_results(self):
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[], total_tokens=0, token_budget=1000,
        )
        assert ctx.context_text == ""

    def test_all_query_results_empty(self):
        qr = MemoryQueryResult(
            strategy="plot_continuity", query_text="q", results=[],
            tokens_used=0, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=0, token_budget=1000,
        )
        # All query results are empty -> context_text should be ""
        assert ctx.context_text == ""

    def test_with_results(self):
        results = [MemoryResult(content="x", score=0.5, source="s", file_type="chapter")]
        qr = MemoryQueryResult(
            strategy="plot_continuity", query_text="q",
            results=results, tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        assert "长期记忆" in text
        assert "plot_continuity" in text or "剧情连续性" in text

    def test_skips_empty_query_results(self):
        # Mix of empty and non-empty query results
        qr_empty = MemoryQueryResult(
            strategy="a", query_text="q", results=[],
            tokens_used=0, tokens_budget=100,
        )
        qr_full = MemoryQueryResult(
            strategy="b", query_text="q",
            results=[MemoryResult(content="y", score=0.5, source="s", file_type="chapter")],
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr_empty, qr_full], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        # Should still produce text (non-empty qr exists)
        assert text != ""

    def test_truncates_long_content(self):
        long_content = "x" * 1000
        results = [MemoryResult(content=long_content, score=0.5, source="s", file_type="chapter")]
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=results,
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        # 1000-char content should be truncated to 600 + "..."
        assert "..." in text
        # The full 1000 chars should NOT appear consecutively in the output
        assert "x" * 1000 not in text

    def test_includes_volume_and_chapter(self):
        results = [MemoryResult(
            content="x", score=0.5, source="s", file_type="chapter",
            volume=3, chapter=42,
        )]
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=results,
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        assert "卷3" in text
        assert "ch-042" in text  # 3-digit padded (42 < 1000)

    def test_chapter_padded_to_4_digits(self):
        results = [MemoryResult(
            content="x", score=0.5, source="s", file_type="chapter",
            volume=1, chapter=1500,
        )]
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=results,
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        # chapter >= 1000 -> 4-digit padding
        assert "ch-1500" in text

    def test_includes_characters_in_meta(self):
        results = [MemoryResult(
            content="x", score=0.5, source="s", file_type="chapter",
            characters=["A", "B", "C", "D"],
        )]
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=results,
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        # First 3 characters should appear
        assert "A" in text
        assert "B" in text
        assert "C" in text
        # All 4 characters joined
        assert "A, B, C" in text

    def test_strategy_label_chinese(self):
        # Use a known strategy to get a Chinese label
        for strategy, expected_label in [
            ("character_state", "角色"),
            ("world_evolution", "世界观"),
            ("foreshadowing_status", "伏笔"),
            ("similar_scenes", "相似"),
            ("recent_events", "近期"),
        ]:
            results = [MemoryResult(content="x", score=0.5, source="s", file_type="chapter")]
            qr = MemoryQueryResult(
                strategy=strategy, query_text="q", results=results,
                tokens_used=10, tokens_budget=100,
            )
            ctx = MemoryContext(
                novel_name="n", volume=1, chapter_num=1,
                query_results=[qr], total_tokens=10, token_budget=1000,
            )
            assert expected_label in ctx.context_text

    def test_no_meta_when_no_volume_chapter_chars(self):
        results = [MemoryResult(content="x", score=0.5, source="s", file_type="chapter")]
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=results,
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        text = ctx.context_text
        # Should still have header and chunk info
        assert "长期记忆" in text
        assert "匹配度:0.50" in text


# ── MemoryContext properties ───────────────────────────────────────────

class TestMemoryContextProperties:
    def test_is_empty_no_results(self):
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[], total_tokens=0, token_budget=1000,
        )
        assert ctx.is_empty is True

    def test_is_empty_with_empty_query_results(self):
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=[],
            tokens_used=0, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=0, token_budget=1000,
        )
        assert ctx.is_empty is True

    def test_is_empty_with_results(self):
        qr = MemoryQueryResult(
            strategy="a", query_text="q",
            results=[MemoryResult(content="x", score=0.5, source="s", file_type="chapter")],
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=10, token_budget=1000,
        )
        assert ctx.is_empty is False

    def test_total_chunks(self):
        qr1 = MemoryQueryResult(
            strategy="a", query_text="q",
            results=[MemoryResult(content="x", score=0.5, source="s", file_type="chapter")],
            tokens_used=10, tokens_budget=100,
        )
        qr2 = MemoryQueryResult(
            strategy="b", query_text="q",
            results=[
                MemoryResult(content="x", score=0.5, source="s", file_type="chapter"),
                MemoryResult(content="y", score=0.5, source="s", file_type="chapter"),
            ],
            tokens_used=10, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr1, qr2], total_tokens=20, token_budget=1000,
        )
        assert ctx._total_chunks() == 3

    def test_to_dict(self):
        qr = MemoryQueryResult(
            strategy="plot_continuity", query_text="q",
            results=[
                MemoryResult(content="x", score=0.8, source="s", file_type="chapter"),
                MemoryResult(content="y", score=0.6, source="s", file_type="chapter"),
            ],
            tokens_used=50, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=50, token_budget=1000,
        )
        d = ctx.to_dict()
        assert d["novel"] == "n"
        assert d["volume"] == 1
        assert d["chapter"] == 1
        assert d["total_tokens"] == 50
        assert d["token_budget"] == 1000
        assert d["total_chunks"] == 2
        assert len(d["strategies"]) == 1
        assert d["strategies"][0]["name"] == "plot_continuity"
        assert d["strategies"][0]["chunks"] == 2
        assert d["strategies"][0]["tokens_used"] == 50
        assert d["strategies"][0]["top_score"] == 0.8

    def test_to_dict_empty_results(self):
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[], total_tokens=0, token_budget=1000,
        )
        d = ctx.to_dict()
        assert d["total_chunks"] == 0
        assert d["strategies"] == []

    def test_to_dict_with_empty_query_result(self):
        qr = MemoryQueryResult(
            strategy="a", query_text="q", results=[],
            tokens_used=0, tokens_budget=100,
        )
        ctx = MemoryContext(
            novel_name="n", volume=1, chapter_num=1,
            query_results=[qr], total_tokens=0, token_budget=1000,
        )
        d = ctx.to_dict()
        # Even with empty results, the strategy entry exists
        assert len(d["strategies"]) == 1
        assert d["strategies"][0]["chunks"] == 0
        # Default for max() with no values is 0
        assert d["strategies"][0]["top_score"] == 0


# ── Module functions ──────────────────────────────────────────────────

class TestModuleFunctions:
    def setup_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def teardown_method(self):
        memory_layer.MemoryLayer._instance = None
        memory_layer._ml = None

    def test_get_memory_layer(self):
        ml = get_memory_layer()
        assert isinstance(ml, MemoryLayer)

    def test_get_memory_layer_singleton(self):
        ml1 = get_memory_layer()
        ml2 = get_memory_layer()
        assert ml1 is ml2

    def test_retrieve_memory(self):
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch("memory_layer.MemoryLayer._fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            ctx = retrieve_memory("novel", 1, 1)
        assert isinstance(ctx, MemoryContext)
        assert ctx.novel_name == "novel"
        assert ctx.volume == 1
        assert ctx.chapter_num == 1

    def test_retrieve_memory_with_all_args(self):
        with patch("memory_layer._is_chroma_available", return_value=False), \
             patch("memory_layer.MemoryLayer._fallback_db_retrieval", return_value={
                 "results": [], "total_tokens": 0, "max_tokens": 1000
             }):
            ctx = retrieve_memory(
                "novel", 2, 5,
                character_names=["A", "B"],
                outline_section="测试 outline",
                total_token_budget=2000,
            )
        assert ctx.token_budget == 2000
