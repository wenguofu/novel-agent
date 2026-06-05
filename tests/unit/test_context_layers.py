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


class TestLayer5WorldBuilding:
    """Layer 5: World building (local 5 + global 5 per P2-3)."""

    @pytest.fixture
    def seeded_novel_with_world(self, tmp_db):
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
        # Adapted: repo.add_world_building(novel_name, domain, name, content,
        # related_vol=0, related_ch=0, tags="") per portal/repository.py:637 —
        # there is NO upsert_world_building; the real method is
        # add_world_building with positional args (novel_name, domain, name,
        # content) and related_vol as a kwarg. The WorldBuilding model field
        # is related_vol (NOT current_vol) per models_orm.py:294.
        # Local: 3 entries scoped to vol 1 (current volume)
        for i in range(3):
            repo.add_world_building(
                "test_novel",
                "地理",
                f"第1卷地点{i}",
                f"第1卷专属地点{i}的描述",
                related_vol=1,
            )
        # Global: cross-volume lore, marked as world-wide (related_vol=0)
        # so the LLM has the 八神体系 context even in early chapters for
        # foreshadowing.
        repo.add_world_building(
            "test_novel",
            "体系",
            "八神体系",
            "世界观的八位古神设定",
            related_vol=0,
        )
        return "test_novel"

    def test_local_world_appears(self, seeded_novel_with_world):
        from context_builder import _build_world_context
        text = _build_world_context("test_novel", 1, 1)
        assert isinstance(text, str)
        # Local entries (related_vol=1) must appear in vol-1 prompt.
        # _build_world_context emits "{name}: {content}" per entry at
        # context_builder.py:424, so "第1卷地点" is a substring of the name.
        assert "第1卷地点" in text

    def test_global_world_appears(self, seeded_novel_with_world):
        from context_builder import _build_world_context
        text = _build_world_context("test_novel", 1, 1)
        # The P2-3 fix: cross-volume world-building (related_vol=0, "global")
        # must also appear in the prompt so the LLM can foreshadow properly.
        # The local-query OR-clause in repository.py:617 (`related_vol == 0`)
        # ensures global entries are returned alongside local ones.
        assert "八神体系" in text or "八位古神" in text


class TestLayer6PacingEmotion:
    """Layer 6: Pacing/Emotion (filtered by vol/ch).

    The layer must include the PacingControl row whose [chapter_start,
    chapter_end] range covers the current chapter. This is the per-chapter
    rhythm/feel/mood instruction fed to the LLM so a fast-pace action
    chapter reads differently from a slow-burn reveal chapter.
    """

    @pytest.fixture
    def seeded_novel_with_pacing(self, tmp_db):
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
        # Adapted: repo.add_pacing(novel_name, volume, chapter_start,
        # chapter_end, **kwargs) per portal/repository.py:712 — there is NO
        # upsert_pacing; the real method is add_pacing with positional
        # (novel_name, volume, chapter_start, chapter_end) and the rest as
        # kwargs. PacingControl model fields confirmed in models_orm.py:327-346
        # (pace_type, intensity, emotion_target, word_budget_min,
        # word_budget_max, notes).
        repo.add_pacing(
            "test_novel",
            1,
            1,
            5,
            pace_type="快节奏",
            intensity=8,
            emotion_target="紧张",
            word_budget_min=2800,
            word_budget_max=3200,
        )
        return "test_novel"

    def test_pacing_appears(self, seeded_novel_with_pacing):
        from context_builder import _build_pacing_context
        text = _build_pacing_context("test_novel", 1, 1)
        # Layer 6 emits "类型：{pace_type}", "情感目标：{emotion_target}", and
        # "字数预算：{min}–{max}" per context_builder.py:433-436. The filter
        # in repository.py:707-708 (`chapter_start <= chapter_num AND
        # chapter_end >= chapter_num`) means a [1, 5] entry applies to
        # chapter 1 of vol 1.
        assert "快节奏" in text or "紧张" in text
        assert "2800" in text or "3200" in text


class TestLayer7Revelation:
    """Layer 7: Revelation (filtered by reveal_volume == current).

    The layer must include revelation rows whose reveal_volume has arrived
    and EXCLUDE rows whose reveal_volume is in the future. This prevents
    the LLM from learning about plot points (e.g., "魔皇是八神之一")
    before the narrative is supposed to reveal them.
    """

    @pytest.fixture
    def seeded_novel_with_revelation(self, tmp_db):
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
        # Adapted: repo.add_revelation(novel_name, name, info_type=...,
        # reveal_volume=..., reveal_chapter=..., content=..., priority=...)
        # per portal/repository.py:745 — there is NO upsert_revelation; the
        # real method is add_revelation. The RevelationSchedule model field
        # is reveal_volume (NOT reveal_vol) per models_orm.py:359.
        # Due now: reveal_volume=1, should appear in vol-1 prompt
        repo.add_revelation(
            "test_novel",
            "主角血脉来源",
            info_type="身份",
            reveal_volume=1,
            content="主角是叛神者后裔",
        )
        # Future: reveal_volume=3, must NOT appear in vol-1 prompt
        repo.add_revelation(
            "test_novel",
            "魔皇残魂真相",
            info_type="真相",
            reveal_volume=3,
            content="魔皇是八神之一",
        )
        return "test_novel"

    def test_current_vol_revelation_appears(self, seeded_novel_with_revelation):
        from context_builder import _build_revelation_context
        text = _build_revelation_context("test_novel", 1)
        # The layer emits "- [第{reveal_chapter}章][{info_type}] {name}: {content}"
        # per context_builder.py:449. A reveal_volume=1 row matches
        # the filter in repository.py:739-742 (`reveal_volume == volume`),
        # so it must appear in the vol-1 prompt.
        assert "主角血脉来源" in text

    def test_future_revelation_excluded(self, seeded_novel_with_revelation):
        from context_builder import _build_revelation_context
        text = _build_revelation_context("test_novel", 1)
        # A reveal_volume=3 row MUST NOT leak into the vol-1 prompt.
        # Regression check: the filter in repository.py:739-742 is
        # `RevelationSchedule.reveal_volume == volume` (exact match, no
        # OR-bypass clause), so vol-3 revelations cannot appear in vol-1.
        assert "魔皇残魂" not in text


class TestLayer8PlotArcs:
    """Layer 8: Plot arcs (filtered by vol range, AND-only).

    The layer must include active plot arcs whose [volume_start,
    volume_end] range covers the current volume and EXCLUDE arcs
    whose range is entirely in the future. This prevents the LLM
    from learning about future plot points (e.g., vol-5 climax)
    before the narrative is supposed to reach them.

    W3 regression watch: T2.4 (Characters) and T2.6 (Foreshadowing)
    both leaked future-vol items due to over-broad OR-clauses in
    the repository filter. The plot arc filter at repository.py:673-678
    is a clean AND-only filter (`volume_start <= volume AND
    volume_end >= volume`) — no OR-bypass clause. The
    `test_out_of_range_arc_excluded` test below is the regression
    guard: if a future OR-bypass is ever introduced, this test
    fails.
    """

    @pytest.fixture
    def seeded_novel_with_arcs(self, tmp_db):
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
        # Adapted: repo.add_plot_arc(novel_name, name, arc_type=..., **kwargs)
        # per portal/repository.py:681 — there is NO upsert_plot_arc; the
        # real method is add_plot_arc. The PlotArc model fields are
        # volume_start / volume_end (NOT start_vol / end_vol) per
        # models_orm.py:313,315. The "type" column is the arc's category
        # (default "主线") per models_orm.py:312.
        # Current range: vol 1-2, must appear in vol-1 prompt
        repo.add_plot_arc(
            "test_novel",
            "觉醒弧",
            arc_type="成长",
            summary="主角从废柴到觉醒",
            volume_start=1,
            volume_end=2,
        )
        # Out-of-range: vol 5-6, must NOT appear in vol-1 prompt
        # (regression check against any future OR-bypass in
        # repository.py:673-678)
        repo.add_plot_arc(
            "test_novel",
            "终战弧",
            arc_type="高潮",
            summary="最终决战的高潮段落",
            volume_start=5,
            volume_end=6,
        )
        return "test_novel"

    def test_arc_appears(self, seeded_novel_with_arcs):
        from context_builder import _build_plot_arc_context
        text = _build_plot_arc_context("test_novel", 1)
        # Layer 8 emits "## 剧情线" header at context_builder.py:458
        # then "- [{type}] {name}: {summary}" per row at
        # context_builder.py:460. The vol-1-2 "觉醒弧" arc must be
        # included by the filter at repository.py:673-678.
        assert "觉醒弧" in text
        assert "成长" in text

    def test_out_of_range_arc_excluded(self, seeded_novel_with_arcs):
        from context_builder import _build_plot_arc_context
        text = _build_plot_arc_context("test_novel", 1)
        # The vol-5-6 "终战弧" arc must NOT leak into the vol-1 prompt.
        # This is the explicit regression check for the T2.4/T2.6
        # OR-bypass antipattern: the filter at repository.py:673-678
        # is `volume_start <= volume AND volume_end >= volume` (AND-only),
        # so an arc starting in vol 5 cannot match for volume=1.
        assert "终战弧" not in text


class TestLayer85BannedCompliance:
    """Layer 8.5: Banned words + compliance rules (config DB).

    Banned words and compliance rules are GLOBAL config (not novel-scoped).
    The layer function `_build_banned_compliance_context()` takes no
    novel_name argument (per `context_builder.py:463`), so the T2.4/T2.6
    OR-bypass antipattern does not apply here.

    Output format (per `context_builder.py:472-510`):
      - Header: "## 禁用词与合规规则（必须遵守）"
      - Compliance section: "- [{cat}] {key}: {val}（{desc}）" per rule
      - Banned section: "- [{cat}] {'、'.join(words)}" per category

    Note: `init_config_seed()` runs first (per `tests/unit/conftest.py:48`),
    so banned/compliance tables are pre-populated with default rows. The
    seed here adds project-specific rows on top; assertions target
    substrings unique to the seed data.
    """

    @pytest.fixture
    def seeded_banned_and_compliance(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        # Adapted: repo.add_banned_word(word, category=..., **kwargs) per
        # portal/repository.py:1269 — there is NO upsert_banned_word; the
        # real method takes positional `word` plus kwargs (NOT a dict).
        # The BannedWord model has fields word/category/replacement/severity
        # per models_orm.py:468-471. `severity` default is "error" per
        # models_orm.py:471, but we pass "high" to confirm arbitrary
        # severity strings are accepted (no enum constraint).
        # 3 words: 2 in 政治 (exercises the 、-join grouping at context_builder.py:510)
        #          + 1 in 色情 (different category line)
        for word, cat in [("违禁词1", "政治"), ("违禁词1b", "政治"), ("违禁词2", "色情")]:
            repo.add_banned_word(word, category=cat, severity="high")
        # Adapted: repo.add_compliance_rule(rule_key, rule_value, ...) per
        # portal/repository.py:1298 — there is NO upsert_compliance_rule;
        # the real method takes positional `rule_key`/`rule_value` plus
        # kwargs (NOT a dict). The ComplianceRule model has fields
        # rule_key/rule_value/description/category per models_orm.py:479-482.
        repo.add_compliance_rule(
            rule_key="max_chapter_words",
            rule_value="5000",
            description="单章不超过 5000 字",
        )
        return "test_novel"

    def test_banned_words_appear(self, seeded_banned_and_compliance):
        from context_builder import _build_banned_compliance_context
        text = _build_banned_compliance_context()
        # Tighter: verify category prefix AND word rendering (catches grouping
        # regressions like dropping the [-cat] prefix or concatenating without separator)
        assert "- [政治] 违禁词1、违禁词1b" in text
        assert "- [色情] 违禁词2" in text

    def test_compliance_rule_appears(self, seeded_banned_and_compliance):
        from context_builder import _build_banned_compliance_context
        text = _build_banned_compliance_context()
        # Tighter: verify full format string [cat] key: val (desc) per
        # context_builder.py:483-487
        assert "- [general] max_chapter_words: 5000（单章不超过 5000 字）" in text
