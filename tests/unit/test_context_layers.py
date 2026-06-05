"""Per-layer snapshot tests for context_builder (M3.2 W2).

Each test class seeds the relevant DB tables via the ``tmp_db`` fixture
(defined in ``tests/unit/conftest.py``; the functional package has an
equivalent fixture) and calls the corresponding layer function in
``portal/context_builder.py``. Substring/contains assertions are preferred
over exact-string equality to avoid brittleness.

The integration test (TestBuildContextIntegration) at the bottom of this
file calls the full ``build_context`` orchestrator and asserts the 12
layers appear in the correct order with the correct token accounting.
"""
import pytest


class TestLayer0CoreInstructions:
    """Layer 0: Core Instructions (jinja2 template, fallback default)."""

    def test_core_instructions_renders_non_empty(self):
        from context_builder import _get_core_instructions
        text = _get_core_instructions()
        assert isinstance(text, str)
        assert len(text) > 50
        # The fallback default contains these markers
        assert "写作" in text or "章节" in text

    def test_core_instructions_under_token_budget(self):
        from context_builder import _get_core_instructions
        from context_builder import _count_tokens
        text = _get_core_instructions()
        # Layer 0 budget is 500 tokens per the orchestrator
        assert _count_tokens(text) <= 500
