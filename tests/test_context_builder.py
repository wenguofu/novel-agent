"""
Phase 4: Context Builder Tests — RED phase
Tests the 9-layer context assembly engine.
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))


@pytest.fixture
def sample_novel():
    """Return minimal novel context for testing"""
    return {
        "name": "test_novel",
        "volume": 1,
        "chapter_num": 1,
        "style": "",
        "instructions": "",
    }


class TestContextBuilder:
    """Test the context builder module"""

    def test_context_builder_imports(self):
        from context_builder import build_context
        assert callable(build_context)

    def test_build_context_returns_structure(self, sample_novel):
        from context_builder import build_context
        result = build_context(sample_novel)
        assert "system_prompt" in result
        assert "layers" in result
        assert "total_tokens" in result
        assert isinstance(result["layers"], list)
        assert len(result["layers"]) >= 8

    def test_build_context_layers_have_names(self, sample_novel):
        from context_builder import build_context
        result = build_context(sample_novel)
        layer_names = [l["name"] for l in result["layers"]]
        required = ["核心指令", "项目元信息", "章节上下文"]
        for name in required:
            assert any(name in ln for ln in layer_names), \
                f"Layer '{name}' not found in {layer_names}"

    def test_build_context_respects_max_tokens(self, sample_novel):
        from context_builder import build_context
        result = build_context({"name": "test_novel", "volume": 1,
                                "chapter_num": 1, "style": "", "instructions": "",
                                "max_tokens": 3000})
        assert result["total_tokens"] <= 3000 + 500  # allow small overhead

    def test_build_context_layer_order(self, sample_novel):
        """Layers should be in priority order: core → meta → chapter → ..."""
        from context_builder import build_context
        result = build_context(sample_novel)
        layers = result["layers"]
        # Core should come first
        assert "核心指令" in layers[0]["name"]
        # Chapter context should be early
        early = [l["name"] for l in layers[:4]]
        assert any("章节" in n for n in early)

    def test_layer_has_tokens_field(self, sample_novel):
        from context_builder import build_context
        result = build_context(sample_novel)
        for layer in result["layers"]:
            assert "tokens_used" in layer, f"Layer {layer['name']} missing tokens_used"
            assert "content" in layer, f"Layer {layer['name']} missing content"

    def test_build_context_handles_missing_novel(self):
        from context_builder import build_context
        result = build_context({"name": "nonexistent_xyz_123", "volume": 1,
                                "chapter_num": 1, "style": "", "instructions": ""})
        # Should not crash, return minimal context
        assert "system_prompt" in result
        assert result["total_tokens"] < 2000  # minimal

    def test_build_context_token_limit_hard(self, sample_novel):
        """Even with very low max_tokens, should not exceed"""
        from context_builder import build_context
        result = build_context({"name": "test_novel", "volume": 1,
                                "chapter_num": 1, "style": "", "instructions": "",
                                "max_tokens": 500})
        assert result["total_tokens"] <= 800  # reasonable buffer


class TestContextStats:
    """Test /api/context/stats endpoint simulation"""

    def test_context_stats_structure(self):
        """Stats should return available data counts"""
        from context_builder import get_context_stats
        stats = get_context_stats("test_novel", 1, 1)
        assert "layers" in stats
        assert isinstance(stats["layers"], list)
        for layer in stats["layers"]:
            assert "name" in layer
            assert "available" in layer


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
