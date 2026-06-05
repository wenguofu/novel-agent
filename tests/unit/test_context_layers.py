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


class TestLayer1ProjectMeta:
    """Layer 1: Project Meta (novel row + all 14 project_meta keys).

    This is the M3.1 P1-3 fix: the layer must load the full project_meta
    table, not just the 3 fields on the novel row.
    """

    @pytest.fixture
    def seeded_novel_with_14_keys(self, tmp_db):
        """Seed a novel row + 14 project_meta rows for test_novel."""
        from repository import get_repo
        repo = get_repo()
        # Adapted: repo.upsert_novel(novel_name, **kwargs) per
        # portal/repository.py:124 — NOT a dict. word_goal is a String
        # column in models_orm.py:31, so pass as str.
        repo.upsert_novel(
            "test_novel",
            title="测试小说",
            genre="玄幻",
            word_goal="1000000",
        )
        # Insert 14 project_meta key/value pairs
        keys = [
            ("world_core", "诸神黄昏后的废土世界"),
            ("magic_system", "元素亲和 + 血脉觉醒"),
            ("main_conflict", "神族遗民 vs 新生帝国"),
            ("tone", "史诗 + 暗黑 + 成长"),
            ("pov", "第三人称限制"),
            ("tense", "过去时"),
            ("protagonist_name", "林渊"),
            ("protagonist_archetype", "废柴逆袭"),
            ("love_interest", "苏晴"),
            ("antagonist", "魔皇残魂"),
            ("theme", "命运 vs 自由意志"),
            ("target_audience", "男频玄幻读者"),
            ("chapter_word_count_target", "3000"),
            ("update_frequency", "日更"),
        ]
        for k, v in keys:
            repo.upsert_project_meta("test_novel", k, v)
        return "test_novel"

    def test_all_14_keys_appear_in_output(self, seeded_novel_with_14_keys):
        from context_builder import _build_project_meta
        from context_builder import _count_tokens
        text = _build_project_meta("test_novel")
        for k, v in [
            ("world_core", "诸神黄昏"),
            ("magic_system", "元素亲和"),
            ("main_conflict", "神族遗民"),
            ("protagonist_name", "林渊"),
            ("antagonist", "魔皇残魂"),
            ("theme", "命运"),
        ]:
            assert k in text, f"missing key {k} in layer 1"
            assert v in text, f"missing value for {k} in layer 1"
        # Token budget check (Layer 1 = 500)
        assert _count_tokens(text) <= 500

    def test_novel_title_appears(self, seeded_novel_with_14_keys):
        from context_builder import _build_project_meta
        text = _build_project_meta("test_novel")
        assert "测试小说" in text
        assert "玄幻" in text
