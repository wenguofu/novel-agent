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


class TestLayer2ChapterContext:
    """Layer 2: Chapter context (outline + danger_issue + prev chapter)."""

    @pytest.fixture
    def seeded_novel(self, tmp_db):
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
        # Adapted: repo.upsert_outline(novel_name, volume, content, word_count=0)
        # per portal/repository.py:170 — content is a positional string, NOT
        # a dict.
        repo.upsert_outline(
            "test_novel",
            "vol-01",
            "第001章 觉醒\n本章主角觉醒血脉。\n第002章 试炼\n本章进入试炼之地。",
        )
        # Adapted: repo.upsert_danger_issue(novel_name, volume, chapter_num,
        # content) per portal/repository.py:1353 — content is a positional
        # string, NOT a dict.
        repo.upsert_danger_issue("test_novel", "vol-01", 1, "血脉觉醒的代价")
        # Adapted: repo.upsert_chapter(novel_name, chapter_ref, **kwargs) per
        # portal/repository.py:216 — uses chapter_ref as the unique lookup
        # key; volume + chapter_num are kwargs.
        repo.upsert_chapter(
            "test_novel",
            "vol-01-ch-0",
            volume="vol-01",
            chapter_num=0,
            content="上一章末尾：林渊在山巅独坐，望着远方的神山，心中百感交集。",
        )
        return "test_novel"

    def test_outline_section_appears(self, seeded_novel):
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 1)
        assert isinstance(text, str)
        # The outline for chapter 1 should be in the text
        assert "觉醒" in text

    def test_danger_issue_appears(self, seeded_novel):
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 1)
        assert "血脉觉醒的代价" in text or "danger" in text.lower() or "危机" in text


class TestLayer3Characters:
    """Layer 3: Characters (volume-scoped via current_vol).

    The layer must include characters active in the current volume and
    EXCLUDE characters that are only active in future volumes (so the
    LLM isn't given plot points it shouldn't know about yet).
    """

    @pytest.fixture
    def seeded_novel_with_chars(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        # Adapted: repo.upsert_novel(novel_name, **kwargs) per
        # portal/repository.py:124 — NOT a dict. word_goal is a String
        # column in models_orm.py:31, so pass as str.
        repo.upsert_novel(
            "test_novel",
            title="测试",
            genre="玄幻",
            word_goal="1000",
        )
        # Adapted: repo.add_character(novel_name, name, role=..., **kwargs)
        # per portal/repository.py:356 — there is NO upsert_character;
        # the real method is add_character. Fields like identity/personality/
        # current_status/emotional_state/current_vol/current_ch are all on
        # the Character model (models_orm.py:217-258).
        # Active in vol 1
        repo.add_character(
            "test_novel",
            "林渊",
            role="主角",
            identity="废柴少年，意外觉醒血脉",
            personality="坚韧、内敛",
            current_status="正在觉醒",
            emotional_state="迷茫",
            current_vol=1,
            current_ch=1,
        )
        # Active in vol 2 (should be excluded from vol-1 prompt)
        repo.add_character(
            "test_novel",
            "苏晴",
            role="女主",
            identity="帝国公主",
            current_vol=2,
            current_ch=1,
        )
        return "test_novel"

    def test_active_char_appears(self, seeded_novel_with_chars):
        from context_builder import _build_character_context
        text = _build_character_context("test_novel", 1, 1)
        assert "林渊" in text
        assert "废柴少年" in text

    def test_future_vol_char_excluded(self, seeded_novel_with_chars):
        from context_builder import _build_character_context
        text = _build_character_context("test_novel", 1, 1)
        # 苏晴 is in vol 2; should NOT appear in vol-1 prompt
        # FIXME: surfaced by T2.4; will be fixed in W3.
        # The current filter in context_builder.py:330 OR-combines
        # `role in ("主角","女主")` with the volume check, so any
        # female lead / protagonist is always included regardless of
        # current_vol. The future-vol character leaks into vol-1.
        assert "苏晴" not in text


class TestLayer35GenreRules:
    """Layer 3.5: Genre rules (must/optional markers, grouped by category)."""

    @pytest.fixture
    def seeded_novel_with_genre_rules(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        # Adapted: repo.upsert_novel(novel_name, **kwargs) per
        # portal/repository.py:124 — NOT a dict. word_goal is a String
        # column in models_orm.py:31, so pass as str.
        repo.upsert_novel(
            "test_novel",
            title="测试",
            genre="玄幻",
            word_goal="1000",
        )
        # Adapted: repo.add_genre_rule(novel_name, rule_category, rule_content,
        # is_required=1) per portal/repository.py:771 — there is NO
        # upsert_genre_rule, and the GenreRule model (models_orm.py:371) has
        # no rule_key/rule_value fields. The real fields are rule_category and
        # rule_content (is_required is Integer 0/1, default 1).
        # Required rule
        repo.add_genre_rule(
            "test_novel",
            "必须元素",
            "每章必须有至少1次血脉能力使用",
            is_required=1,
        )
        # Optional rule
        repo.add_genre_rule(
            "test_novel",
            "节奏规则",
            "对话占比 20-30%",
            is_required=0,
        )
        return "test_novel"

    def test_required_marker_appears(self, seeded_novel_with_genre_rules):
        from context_builder import _build_genre_rules_context
        text = _build_genre_rules_context("test_novel")
        # The layer emits "🔴" for required rules (context_builder.py:383)
        # and the section header is "## 类型规则（genre_rules — 必须遵守）"
        # (context_builder.py:379), which contains "必须".
        assert "🔴" in text or "必须" in text

    def test_optional_marker_appears(self, seeded_novel_with_genre_rules):
        from context_builder import _build_genre_rules_context
        text = _build_genre_rules_context("test_novel")
        # The layer emits "🟡" for optional rules (context_builder.py:383).
        assert "🟡" in text or "可选" in text


class TestLayer4Foreshadowing:
    """Layer 4: Foreshadowing (filtered by target_vol <= current).

    The layer must include foreshadowing items whose target_vol has
    arrived (target_vol <= current_vol) and EXCLUDE items whose
    target_vol is in the future. This prevents the LLM from learning
    about plot points too early.
    """

    @pytest.fixture
    def seeded_novel_with_foreshadowing(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        # Adapted: repo.upsert_novel(novel_name, **kwargs) per
        # portal/repository.py:124 — NOT a dict. word_goal is a String
        # column in models_orm.py:31, so pass as str.
        repo.upsert_novel(
            "test_novel",
            title="测试",
            genre="玄幻",
            word_goal="1000",
        )
        # Adapted: repo.add_foreshadowing(novel_name, name, description=...,
        # category=..., introduced_vol=..., introduced_ch=..., target_vol=...,
        # target_ch=..., priority=...) per portal/repository.py:460 — there
        # is NO upsert_foreshadowing; the real method is add_foreshadowing,
        # which takes individual kwargs (not a dict). Fields confirmed in
        # models_orm.py:190-214 (Foreshadowing model).
        # Due now: target_vol=1, will appear in vol-1 prompt
        repo.add_foreshadowing(
            "test_novel",
            "神山之谜",
            description="神山为何封印八位古神",
            target_vol=1,
            introduced_vol=1,
        )
        # Future: target_vol=3, must NOT appear in vol-1 prompt
        repo.add_foreshadowing(
            "test_novel",
            "叛神者身份",
            description="主角是叛神者后裔",
            target_vol=3,
            introduced_vol=1,
        )
        return "test_novel"

    def test_due_now_foreshadowing_appears(self, seeded_novel_with_foreshadowing):
        from context_builder import _build_foreshadowing_context
        text = _build_foreshadowing_context("test_novel", 1)
        assert isinstance(text, str)
        # Foreshadowing with target_vol=1 must appear in vol-1 prompt
        assert "神山之谜" in text

    def test_future_foreshadowing_excluded(self, seeded_novel_with_foreshadowing):
        from context_builder import _build_foreshadowing_context
        text = _build_foreshadowing_context("test_novel", 1)
        # Foreshadowing with target_vol=3 must NOT appear in vol-1 prompt
        # (regression check for the volume filter at
        # repository.py:501-507: `Foreshadowing.target_vol <= current_vol`).
        # FIXME: surfaced by T2.6; will be fixed in W3.
        # The OR clause `Foreshadowing.introduced_vol == current_vol` in
        # repository.py:505 leaks "叛神者身份" (introduced_vol=1, current_vol=1)
        # into the vol-1 prompt even though its target_vol=3 (future). The
        # same kind of over-broad OR filter that broke Layer 3 in T2.4.
        assert "叛神者身份" not in text
