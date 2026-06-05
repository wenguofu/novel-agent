"""Unit tests for portal/prompt_manager.py (M3.1 W2 T2.7.3).

Targets line coverage 63% -> 90%+. Tests the Jinja2 template engine,
caching with TTL, fallback to static files, and schema validation.
"""
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from jinja2 import TemplateNotFound
from pydantic import ValidationError

from prompt_manager import (
    PROMPTS_DIR,
    ChapterFooterVars,
    CoreInstructionsVars,
    CreateNovelUserVars,
    PromptManager,
    ReviewSystemVars,
    _SCHEMA_MAP,
    _quick_hash,
    get_prompt_manager,
    render_prompt,
)


# ── Schemas ─────────────────────────────────────────────────────────────

class TestSchemas:
    def test_core_instructions_empty(self):
        v = CoreInstructionsVars()
        assert v is not None

    def test_create_novel_user_defaults(self):
        v = CreateNovelUserVars()
        assert v.word_goal == "100万"
        assert v.perspective == "第三人称"
        # Other fields default to empty string
        assert v.genre == ""
        assert v.protagonist == ""
        assert v.selling_point == ""
        assert v.references == ""

    def test_create_novel_user_custom(self):
        v = CreateNovelUserVars(genre="玄幻", protagonist="林风")
        assert v.genre == "玄幻"
        assert v.protagonist == "林风"

    def test_chapter_footer_required(self):
        # volume and chapter_num have no defaults
        with pytest.raises(ValidationError):
            ChapterFooterVars()

    def test_chapter_footer_valid(self):
        v = ChapterFooterVars(volume=1, chapter_num=1)
        assert v.volume == 1
        assert v.chapter_num == 1

    def test_chapter_footer_defaults(self):
        v = ChapterFooterVars(volume=2, chapter_num=5)
        assert v.style == ""
        assert v.instructions == ""

    def test_chapter_footer_with_optional_fields(self):
        v = ChapterFooterVars(
            volume=1, chapter_num=2, style="热血", instructions="打斗"
        )
        assert v.style == "热血"
        assert v.instructions == "打斗"

    def test_chapter_footer_type_coercion(self):
        # Pydantic v1 coerces "1" -> 1 for int fields
        v = ChapterFooterVars(volume="1", chapter_num="2")
        assert v.volume == 1
        assert v.chapter_num == 2

    def test_review_system_empty(self):
        v = ReviewSystemVars()
        assert v is not None

    def test_schema_map_contains_expected_keys(self):
        assert "core_instructions" in _SCHEMA_MAP
        assert "create_novel_user" in _SCHEMA_MAP
        assert "chapter_context_footer" in _SCHEMA_MAP
        assert "review_system" in _SCHEMA_MAP
        assert _SCHEMA_MAP["core_instructions"] is CoreInstructionsVars
        assert _SCHEMA_MAP["create_novel_user"] is CreateNovelUserVars
        assert _SCHEMA_MAP["chapter_context_footer"] is ChapterFooterVars
        assert _SCHEMA_MAP["review_system"] is ReviewSystemVars


# ── _quick_hash ─────────────────────────────────────────────────────────

class TestQuickHash:
    def test_returns_string(self):
        h = _quick_hash({"a": 1})
        assert isinstance(h, str)

    def test_same_input_same_hash(self):
        h1 = _quick_hash({"a": 1, "b": 2})
        h2 = _quick_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = _quick_hash({"a": 1})
        h2 = _quick_hash({"a": 2})
        assert h1 != h2

    def test_order_independent(self):
        # sort_keys=True means order does not matter
        h1 = _quick_hash({"a": 1, "b": 2})
        h2 = _quick_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_handles_non_json_serializable(self):
        # default=str fallback handles non-serializable objects
        h = _quick_hash({"obj": object()})
        assert isinstance(h, str)

    def test_handles_nested_dict(self):
        h = _quick_hash({"outer": {"inner": 1}})
        assert isinstance(h, str)

    def test_falls_back_when_json_dumps_fails(self):
        # Force the json.dumps path to raise so the except branch is exercised
        with patch("json.dumps", side_effect=ValueError("boom")):
            h = _quick_hash({"a": 1})
        assert isinstance(h, str)


# ── PromptManager init ─────────────────────────────────────────────────

class TestPromptManagerInit:
    def setup_method(self):
        # Always reset singleton before each init test
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_default_prompts_dir(self):
        pm = PromptManager()
        assert pm._prompts_dir == PROMPTS_DIR

    def test_custom_prompts_dir(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._prompts_dir == tmp_path

    def test_prompts_dir_coerced_to_path(self):
        # If user passes a string, it should be coerced to Path
        pm = PromptManager(prompts_dir="/tmp")  # type: ignore[arg-type]
        assert isinstance(pm._prompts_dir, Path)
        assert pm._prompts_dir == Path("/tmp")

    def test_nonexistent_dir_no_env(self, tmp_path):
        nonexistent = tmp_path / "nope"
        pm = PromptManager(prompts_dir=nonexistent)
        assert pm._env is None

    def test_existing_dir_has_env(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._env is not None

    def test_initial_cache_empty(self):
        pm = PromptManager()
        assert pm._cache == {}

    def test_default_cache_ttl(self):
        pm = PromptManager()
        assert pm._cache_ttl == 300.0


# ── Singleton ──────────────────────────────────────────────────────────

class TestGetInstance:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_returns_instance(self):
        pm = PromptManager.get_instance()
        assert isinstance(pm, PromptManager)

    def test_returns_same_instance(self):
        pm1 = PromptManager.get_instance()
        pm2 = PromptManager.get_instance()
        assert pm1 is pm2

    def test_get_instance_uses_default_prompts_dir(self):
        pm = PromptManager.get_instance()
        assert pm._prompts_dir == PROMPTS_DIR


# ── render: basic ───────────────────────────────────────────────────────

class TestRender:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_render_with_existing_template_in_default_dir(self):
        # core_instructions.j2 exists in portal/prompts/
        pm = PromptManager()
        result = pm.render("core_instructions")
        assert isinstance(result, str)
        # The default template has substantial content
        assert len(result) > 0

    def test_render_with_variables(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello {{ name }}!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test", {"name": "World"})
        assert result == "Hello World!"

    def test_render_variables_default_to_empty_dict(self, tmp_path):
        (tmp_path / "test.j2").write_text("Static", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        # No variables argument at all
        result = pm.render("test")
        assert result == "Static"

    def test_render_caches_result_when_cache_true(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render("test", cache=True)
        assert "test" in pm._cache
        # The cached value is (timestamp, result) tuple
        ts, value = pm._cache["test"]
        assert value == "Hello!"

    def test_render_no_cache(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render("test", cache=False)
        assert pm._cache == {}

    def test_render_missing_template_returns_empty_string(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("nonexistent_template")
        assert result == ""

    def test_render_no_template_no_static_returns_empty(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("totally_missing")
        assert result == ""

    def test_render_no_dir_at_all_returns_empty(self, tmp_path):
        nonexistent = tmp_path / "missing"
        pm = PromptManager(prompts_dir=nonexistent)
        result = pm.render("anything")
        assert result == ""


# ── render: cache TTL ───────────────────────────────────────────────────

class TestRenderCacheTTL:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_cache_hit_within_ttl(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm._cache_ttl = 60.0
        # First render populates the cache
        pm.render("test", cache=True)
        # Advance "time" by 10s, well within TTL
        with patch("prompt_manager.time.time", return_value=time.time() + 10):
            result = pm.render("test", cache=True)
        assert result == "Hello!"

    def test_cache_miss_after_ttl(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm._cache_ttl = 0.001
        pm.render("test", cache=True)
        time.sleep(0.05)  # Wait past TTL
        result = pm.render("test", cache=True)
        # Cache missed, re-rendered; result should still be the same content
        assert result == "Hello!"

    def test_cache_key_for_no_variables(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render("test", cache=True)
        # With no variables, cache_key is just template_name
        assert "test" in pm._cache

    def test_cache_key_includes_variables_hash(self, tmp_path):
        (tmp_path / "test.j2").write_text("{{ x }}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render("test", {"x": 1}, cache=True)
        # Cache key should include hash of variables, not just the name
        assert "test" not in pm._cache
        # The key is "test:<hash>"
        cache_keys = list(pm._cache.keys())
        assert any(k.startswith("test:") for k in cache_keys)

    def test_cache_disabled_skips_cache_check(self, tmp_path):
        (tmp_path / "test.j2").write_text("Hello!", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        # Prime the cache
        pm.render("test", cache=True)
        assert "test" in pm._cache
        # Now render with cache=False -- it should still produce correct output
        # but the render method should not check the cache
        result = pm.render("test", cache=False)
        assert result == "Hello!"


# ── render: schema validation ───────────────────────────────────────────

class TestRenderValidation:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_invalid_chapter_footer_missing_required(self):
        pm = PromptManager()
        with pytest.raises(ValueError, match="variable validation failed"):
            pm.render("chapter_context_footer", {})

    def test_invalid_chapter_footer_wrong_type(self):
        pm = PromptManager()
        with pytest.raises(ValueError, match="variable validation failed"):
            pm.render("chapter_context_footer", {"volume": "not_an_int"})

    def test_valid_chapter_footer(self, tmp_path):
        (tmp_path / "chapter_context_footer.j2").write_text(
            "V{{ volume }}C{{ chapter_num }}", encoding="utf-8"
        )
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render(
            "chapter_context_footer", {"volume": 1, "chapter_num": 2}
        )
        assert result == "V1C2"

    def test_unknown_template_no_schema(self, tmp_path):
        # No schema in _SCHEMA_MAP for "unknown"
        (tmp_path / "unknown.j2").write_text("X", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        # Should not raise -- no schema means no validation
        result = pm.render("unknown", {"anything": "goes"})
        assert result == "X"

    def test_create_novel_user_with_no_vars_uses_defaults(self, tmp_path):
        (tmp_path / "create_novel_user.j2").write_text(
            "Genre: {{ genre }}", encoding="utf-8"
        )
        pm = PromptManager(prompts_dir=tmp_path)
        # Empty vars dict -- schema has all defaults, so validation passes
        result = pm.render("create_novel_user", {})
        assert result == "Genre: "  # genre defaults to ""

    def test_create_novel_user_invalid_type(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        with pytest.raises(ValueError, match="variable validation failed"):
            pm.render("create_novel_user", {"genre": 12345})  # int not str

    def test_core_instructions_takes_no_vars(self, tmp_path):
        (tmp_path / "core_instructions.j2").write_text("STATIC", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        # CoreInstructionsVars has no fields, so empty dict passes
        result = pm.render("core_instructions", {})
        assert result == "STATIC"


# ── render: fallback to static ──────────────────────────────────────────

class TestRenderFallback:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_fallback_to_md(self, tmp_path):
        (tmp_path / "test.md").write_text("Static MD content", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test")
        assert result == "Static MD content"

    def test_fallback_to_txt(self, tmp_path):
        (tmp_path / "test.txt").write_text("Plain text content", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test")
        assert result == "Plain text content"

    def test_md_preferred_over_txt(self, tmp_path):
        # When both exist, .md should be returned (it's tried first)
        (tmp_path / "test.md").write_text("MD", encoding="utf-8")
        (tmp_path / "test.txt").write_text("TXT", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test")
        assert result == "MD"

    def test_no_fallback_returns_empty(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("totally_missing")
        assert result == ""

    def test_jinja_takes_precedence_over_static(self, tmp_path):
        # If .j2 exists, static files are not used
        (tmp_path / "test.j2").write_text("JINJA", encoding="utf-8")
        (tmp_path / "test.md").write_text("STATIC", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test")
        assert result == "JINJA"


# ── _render_jinja2 ──────────────────────────────────────────────────────

class TestRenderJinja2:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_returns_none_when_no_env(self, tmp_path):
        nonexistent = tmp_path / "nope"
        pm = PromptManager(prompts_dir=nonexistent)
        result = pm._render_jinja2("anything", {})
        assert result is None

    def test_returns_none_on_template_not_found(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm._render_jinja2("missing", {})
        assert result is None

    def test_renders_existing_template(self, tmp_path):
        (tmp_path / "x.j2").write_text("Value: {{ v }}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm._render_jinja2("x", {"v": 42})
        assert result == "Value: 42"

    def test_returns_none_on_template_error(self, tmp_path):
        # Create a template that references an undefined variable
        # Jinja2 will raise UndefinedError on render
        (tmp_path / "bad.j2").write_text("{{ undefined_var.field }}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        # undefined_var.field should raise UndefinedError, not TemplateNotFound
        result = pm._render_jinja2("bad", {})
        assert result is None

    def test_template_not_found_is_handled_specifically(self, tmp_path):
        # Verify that TemplateNotFound is caught explicitly
        pm = PromptManager(prompts_dir=tmp_path)
        # Patch get_template to raise TemplateNotFound explicitly
        from jinja2 import Environment

        with patch.object(pm._env, "get_template", side_effect=TemplateNotFound("x.j2")):
            result = pm._render_jinja2("x", {})
        assert result is None


# ── _read_static ────────────────────────────────────────────────────────

class TestReadStatic:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_reads_md(self, tmp_path):
        (tmp_path / "x.md").write_text("MD content", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._read_static("x") == "MD content"

    def test_reads_txt(self, tmp_path):
        (tmp_path / "x.txt").write_text("TXT content", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._read_static("x") == "TXT content"

    def test_returns_none_for_missing(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._read_static("nope") is None

    def test_md_takes_precedence(self, tmp_path):
        (tmp_path / "x.md").write_text("MD", encoding="utf-8")
        (tmp_path / "x.txt").write_text("TXT", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._read_static("x") == "MD"

    def test_reads_utf8(self, tmp_path):
        (tmp_path / "x.md").write_text("中文内容", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm._read_static("x") == "中文内容"


# ── render_or_default ──────────────────────────────────────────────────

class TestRenderOrDefault:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_returns_rendered_when_template_exists(self, tmp_path):
        (tmp_path / "x.j2").write_text("Rendered", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render_or_default("x", default="DEFAULT")
        assert result == "Rendered"

    def test_returns_default_on_missing(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render_or_default("missing", default="DEFAULT")
        assert result == "DEFAULT"

    def test_passes_variables(self, tmp_path):
        (tmp_path / "x.j2").write_text("Hello {{ name }}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render_or_default("x", default="DEFAULT", variables={"name": "X"})
        assert result == "Hello X"

    def test_render_or_default_does_not_cache(self, tmp_path):
        # render_or_default calls render with cache=False
        (tmp_path / "x.j2").write_text("Hi", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render_or_default("x", default="DEFAULT")
        assert pm._cache == {}


# ── clear_cache ─────────────────────────────────────────────────────────

class TestClearCache:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_clears_cache(self, tmp_path):
        (tmp_path / "x.j2").write_text("Hi", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        pm.render("x", cache=True)
        assert pm._cache != {}
        pm.clear_cache()
        assert pm._cache == {}

    def test_clear_cache_on_empty_cache(self):
        pm = PromptManager()
        pm.clear_cache()
        assert pm._cache == {}


# ── list_templates ─────────────────────────────────────────────────────

class TestListTemplates:
    def setup_method(self):
        PromptManager._instance = None

    def teardown_method(self):
        PromptManager._instance = None

    def test_empty_dir(self, tmp_path):
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm.list_templates() == []

    def test_nonexistent_dir(self, tmp_path):
        nonexistent = tmp_path / "nope"
        pm = PromptManager(prompts_dir=nonexistent)
        assert pm.list_templates() == []

    def test_lists_j2_files_by_stem(self, tmp_path):
        (tmp_path / "a.j2").write_text("A", encoding="utf-8")
        (tmp_path / "b.j2").write_text("B", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        names = pm.list_templates()
        assert "a" in names
        assert "b" in names
        # For .j2 we return stem (no extension)
        assert "a.j2" not in names

    def test_lists_md_files(self, tmp_path):
        (tmp_path / "x.md").write_text("X", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        names = pm.list_templates()
        # For .md we return name without extension
        assert "x" in names

    def test_lists_txt_files(self, tmp_path):
        (tmp_path / "y.txt").write_text("Y", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        names = pm.list_templates()
        assert "y" in names

    def test_ignores_other_files(self, tmp_path):
        (tmp_path / "ignore.py").write_text("x", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm.list_templates() == []

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "z.j2").write_text("Z", encoding="utf-8")
        (tmp_path / "a.j2").write_text("A", encoding="utf-8")
        (tmp_path / "m.j2").write_text("M", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm.list_templates() == ["a", "m", "z"]


# ── Module singletons ──────────────────────────────────────────────────

class TestModuleSingletons:
    def setup_method(self):
        import prompt_manager
        prompt_manager._pm = None
        PromptManager._instance = None

    def teardown_method(self):
        import prompt_manager
        prompt_manager._pm = None
        PromptManager._instance = None

    def test_get_prompt_manager_returns_instance(self):
        pm = get_prompt_manager()
        assert isinstance(pm, PromptManager)

    def test_get_prompt_manager_returns_same(self):
        pm1 = get_prompt_manager()
        pm2 = get_prompt_manager()
        assert pm1 is pm2

    def test_render_prompt_convenience(self, tmp_path):
        import prompt_manager
        (tmp_path / "test.j2").write_text("Conv: {{ msg }}", encoding="utf-8")
        prompt_manager._pm = PromptManager(prompts_dir=tmp_path)
        result = render_prompt("test", msg="hi")
        assert result == "Conv: hi"

    def test_render_prompt_with_no_kwargs(self, tmp_path):
        import prompt_manager
        (tmp_path / "static.j2").write_text("STATIC", encoding="utf-8")
        prompt_manager._pm = PromptManager(prompts_dir=tmp_path)
        result = render_prompt("static")
        assert result == "STATIC"
