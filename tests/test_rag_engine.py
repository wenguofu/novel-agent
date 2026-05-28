"""
Phase 3: RAG Engine Tests — RED phase
Tests category-aware vector queries with token budgets.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))


class TestTokenBudget:
    """Test token budget allocation logic"""

    def test_token_budget_module_imports(self):
        """token_budget module should exist"""
        from token_budget import TokenBudget
        budget = TokenBudget(max_tokens=10000)
        assert budget.max_tokens == 10000
        assert budget.used == 0
        assert budget.remaining == 10000

    def test_allocate_within_budget(self):
        from token_budget import TokenBudget
        budget = TokenBudget(max_tokens=10000)
        result = budget.allocate("characters", 2000)
        assert result == 2000
        assert budget.used == 2000
        assert budget.remaining == 8000

    def test_allocate_exceeds_budget(self):
        from token_budget import TokenBudget
        budget = TokenBudget(max_tokens=3000)
        budget.allocate("world", 2500)
        # Request 2000 but only 500 remaining
        result = budget.allocate("characters", 2000)
        assert result is not True  # should return allocated amount or False
        # Should have used at most 3000 total
        assert budget.used <= 3000

    def test_allocate_priority_order(self):
        from token_budget import TokenBudget
        budget = TokenBudget(max_tokens=5000)
        # Allocate in priority order
        budget.allocate("core", 500)       # always gets
        budget.allocate("characters", 2000) # priority 1
        budget.allocate("foreshadowing", 1500) # priority 2
        budget.allocate("world", 1000)     # priority 3
        assert budget.remaining >= 0
        assert budget.used <= 5000

    def test_remaining_goes_to_last(self):
        from token_budget import TokenBudget
        budget = TokenBudget(max_tokens=5000)
        budget.allocate("core", 500)
        budget.allocate("characters", 2000)
        budget.allocate("foreshadowing", 1500)
        # Should have ~1000 left for world + style
        remaining = budget.remaining
        assert remaining > 0
        budget.allocate("world", remaining)
        assert budget.remaining == 0


class TestRagEngine:
    """Test RAG engine with mock/fallback behavior"""

    def test_rag_engine_imports(self):
        """rag_engine module should exist and expose query function"""
        from rag_engine import query_categories
        assert callable(query_categories)

    def test_query_categories_structure(self):
        """query_categories should return structured results"""
        from rag_engine import query_categories
        categories = [
            {"category": "character", "query": "付大强", "max_tokens": 1000},
            {"category": "world", "query": "乐园规则", "max_tokens": 1000},
        ]
        result = query_categories("test_novel", categories, total_max_tokens=3000)
        assert "results" in result
        assert "total_tokens" in result
        assert isinstance(result["results"], list)
        # Each result should have category, chunks, tokens_used
        for r in result["results"]:
            assert "category" in r
            assert "tokens_used" in r
            assert "chunks" in r

    def test_query_respects_max_tokens(self):
        from rag_engine import query_categories
        categories = [
            {"category": "test", "query": "test query", "max_tokens": 500},
        ]
        result = query_categories("test_novel", categories, total_max_tokens=1000)
        assert result["total_tokens"] <= 1000

    def test_query_empty_categories(self):
        from rag_engine import query_categories
        result = query_categories("test_novel", [], total_max_tokens=5000)
        assert result["total_tokens"] == 0
        assert result["results"] == []

    def test_fallback_to_db(self):
        """When chromadb unavailable, should not crash, return empty"""
        from rag_engine import query_categories
        result = query_categories("nonexistent_novel_12345", [
            {"category": "test", "query": "test", "max_tokens": 500}
        ], total_max_tokens=1000)
        # Should still return valid structure (empty chunks, no crash)
        assert "results" in result
        assert "total_tokens" in result
        # All chunks should be empty (no vector results)
        for r in result["results"]:
            assert len(r["chunks"]) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
