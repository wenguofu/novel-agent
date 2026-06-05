"""Unit tests for portal/context_builder_v2.py (M3.1 W2 T2.7.8).

Targets line coverage 0% -> 90%+. Tests the 11-layer volume-scoped
context builder with mocked repo. Each layer builder is tested
independently; build_context_volume_scoped is tested end-to-end.
"""
import importlib
import os
import time
from unittest.mock import MagicMock, patch

import pytest


def _import_cb_v2():
    """Re-import context_builder_v2 to reset module-level state (cache)."""
    for m in list(__import__("sys").modules):
        if m in ("context_builder_v2",):
            del __import__("sys").modules[m]
    return importlib.import_module("context_builder_v2")


# ── _get_core_instructions ────────────────────────────────────────────

class TestCoreInstructions:
    def test_returns_string(self):
        cb = _import_cb_v2()
        with patch("context_builder_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "DEFAULT CORE INSTRUCTIONS"
            mock_pm_fn.return_value = mock_pm
            result = cb._get_core_instructions()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_falls_back_to_default(self):
        cb = _import_cb_v2()
        with patch("context_builder_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "DEFAULT TEXT"
            mock_pm_fn.return_value = mock_pm
            result = cb._get_core_instructions()
        assert result == "DEFAULT TEXT"
        # Verify it's called with the expected key + a default string fallback
        call_args = mock_pm.render_or_default.call_args
        assert call_args[0][0] == "core_instructions"
        # Second positional arg is the default string
        assert "网文" in call_args[0][1] or "Agent" in call_args[0][1]


# ── _read_outline_yaml_v2 ─────────────────────────────────────────────

class TestReadOutlineYamlV2:
    def _patch_dirname(self, monkeypatch, tmp_path):
        """Patch os.path.dirname so that the project root is tmp_path."""
        def mock_dirname(path):
            return str(tmp_path)
        monkeypatch.setattr("context_builder_v2.os.path.dirname", mock_dirname)

    def test_no_yaml_file_returns_empty(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("nonexistent", 1, 1)
        assert result == ""

    def test_yaml_chapter_match(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        yaml_content = (
            "volume_name: 玄幻卷\n"
            "chapters:\n"
            "  - number: 1\n"
            "    title: 第一章\n"
            "    function:\n"
            "      - 开端\n"
            "      - 引入\n"
            "    core_events:\n"
            "      - 主角出场\n"
            "      - 获得金手指\n"
            "    foreshadowing: 古神传说\n"
            "    ending_hook: 危机来临\n"
            "    style_hint: 慢节奏\n"
        )
        (novel_dir / "vol-01-chapters.yaml").write_text(yaml_content, encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)

        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "第一章" in result
        assert "开端" in result
        assert "引入" in result
        assert "主角出场" in result
        assert "获得金手指" in result
        assert "古神传说" in result
        assert "危机来临" in result
        assert "慢节奏" in result
        assert "玄幻卷" in result

    def test_yaml_no_matching_chapter_returns_volume_header(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "volume_name: 我的卷\nchapters:\n  - number: 99\n    title: Other\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "第1卷大纲" in result
        assert "我的卷" in result

    def test_invalid_yaml_returns_empty(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "not valid yaml or json{[", encoding="utf-8"
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert result == ""

    def test_json_fallback(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            '{"chapters": [{"number": 1, "title": "JSON章"}]}',
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "JSON章" in result

    def test_danger_scenes_marker(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        yaml_content = (
            "rhythm_rules:\n"
            "  danger_scenes: [1]\n"
            "  major_crises: [1]\n"
            "chapters:\n"
            "  - number: 1\n"
            "    title: 危险章\n"
        )
        (novel_dir / "vol-01-chapters.yaml").write_text(yaml_content, encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "高压章节" in result
        assert "重大危机章" in result

    def test_function_as_string(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n    function: 'single_func'\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "single_func" in result

    def test_yml_extension(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yml").write_text(
            "chapters:\n  - number: 1\n    title: 第二章\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "第二章" in result

    def test_foreshadowing_as_list(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n"
            "    foreshadowing:\n      - 推进伏笔A\n      - 推进伏笔B\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "推进伏笔A" in result
        assert "推进伏笔B" in result

    def test_non_dict_data_returns_empty(self, tmp_path, monkeypatch):
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "- just a list\n- not a dict\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert result == ""

    def test_open_raises_continues_to_yml(self, tmp_path, monkeypatch):
        """If .yaml open raises IOError, the function continues to try .yml."""
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        # Provide both files; .yaml will fail open, .yml will succeed
        (novel_dir / "vol-01-chapters.yaml").write_text("x", encoding="utf-8")
        (novel_dir / "vol-01-chapters.yml").write_text(
            "chapters:\n  - number: 1\n    title: Yml章\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)

        real_open = open
        def failing_open(path, *args, **kwargs):
            if str(path).endswith(".yaml"):
                raise IOError("disk error")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", failing_open):
            result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "Yml章" in result

    def test_yaml_exception_falls_back_to_json_failure(self, tmp_path, monkeypatch):
        """When yaml.safe_load raises and json.loads also fails -> return ''."""
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text("anything", encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)

        import yaml as real_yaml
        with patch.object(real_yaml, "safe_load", side_effect=Exception("yaml boom")):
            result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert result == ""

    def test_core_events_as_string(self, tmp_path, monkeypatch):
        """core_events can be a single string (not a list) — covers the else branch."""
        cb = _import_cb_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n    core_events: 单一事件\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = cb._read_outline_yaml_v2("my_novel", 1, 1)
        assert "单一事件" in result


# ── _build_project_meta_v2 ────────────────────────────────────────────

class TestBuildProjectMetaV2:
    def test_no_novel_returns_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_novel.return_value = None
        result = cb._build_project_meta_v2(repo, "nonexistent")
        assert result == ""

    def test_basic_meta(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_novel.return_value = {
            "title": "测试书", "genre": "玄幻", "word_goal": "100万"
        }
        result = cb._build_project_meta_v2(repo, "test_novel")
        assert "测试书" in result
        assert "玄幻" in result
        assert "100万" in result

    def test_missing_fields_use_defaults(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        # Empty/None fields trigger the default fallback strings
        repo.get_novel.return_value = {
            "title": None, "genre": None, "word_goal": None
        }
        result = cb._build_project_meta_v2(repo, "n")
        # Empty title -> falls back to novel_name
        assert "n" in result
        # Missing genre/word_goal -> '未设置'
        assert "未设置" in result


# ── _build_chapter_context_v2 ─────────────────────────────────────────

class TestBuildChapterContextV2:
    def test_with_yaml_outline(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_danger_issue.return_value = None
        repo.get_chapter_by_num.return_value = None
        with patch("context_builder_v2._read_outline_yaml_v2",
                   return_value="## 第1卷第1章 写作指令\n内容"):
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        assert "写作指令" in result

    def test_with_db_outline_match(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            # Use 3-digit padding "001" and "第" surrounding it
            repo.get_outline.return_value = {
                "content": "前言\n第 001 章 介绍\n详细描述...\n第 002 章 下一章"
            }
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        assert "卷纲要求" in result

    def test_db_outline_no_match_falls_back_to_full(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            repo.get_outline.return_value = {"content": "Just a summary."}
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        assert "本卷大纲" in result

    def test_db_outline_none(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        assert isinstance(result, str)

    def test_with_danger_issue(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = {"content": "危险！"}
            repo.get_chapter_by_num.return_value = None
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        assert "危机" in result or "关卡" in result

    def test_with_previous_chapter(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = {"content": "前章结尾内容"}
            result = cb._build_chapter_context_v2(repo, "n", 1, 2)
        assert "上一章" in result

    def test_chapter_1_no_previous(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        with patch("context_builder_v2._read_outline_yaml_v2", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = cb._build_chapter_context_v2(repo, "n", 1, 1)
        # Should not raise
        assert isinstance(result, str)


# ── _build_character_context_v2 ──────────────────────────────────────

class TestBuildCharacterContextV2:
    def test_no_active_chars(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = []
        result = cb._build_character_context_v2(repo, "n", 1)
        assert result == ""

    def test_basic_char(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "林风", "role": "主角", "current_vol": 1, "current_ch": 1}
        ]
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "林风" in result
        assert "主角" in result

    def test_character_with_all_fields(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {
                "name": "林风", "role": "主角",
                "identity": "剑客", "personality": "冷静",
                "current_status": "修炼中", "emotional_state": "平静",
                "current_vol": 1, "current_ch": 5,
            }
        ]
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "剑客" in result
        assert "冷静" in result
        assert "修炼中" in result
        assert "平静" in result
        assert "第1卷第5章" in result

    def test_character_limit_5(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": f"角色{i}", "role": "?", "current_vol": 1, "current_ch": 1}
            for i in range(10)
        ]
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "角色0" in result
        assert "角色4" in result
        assert "角色5" not in result

    def test_identity_in_future_vol_excluded(self):
        # context_builder_v2 identity filter: c.current_vol <= volume
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "future_id", "current_vol": 5}
        ]
        # current_vol=5 > volume=1 -> identity NOT included
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "future_id" not in result

    def test_identity_in_past_vol_included(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "past_id", "current_vol": 1}
        ]
        # current_vol=1 <= volume=2 -> identity included
        result = cb._build_character_context_v2(repo, "n", 2)
        assert "past_id" in result

    def test_identity_at_current_vol_included(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "current_id", "current_vol": 2}
        ]
        # current_vol=2 <= volume=2 -> identity included
        result = cb._build_character_context_v2(repo, "n", 2)
        assert "current_id" in result

    def test_no_role_uses_question_mark(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "NoRole", "current_vol": 1, "current_ch": 1}
        ]
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "NoRole" in result
        assert "(?)" in result

    def test_ending_and_arc_not_leaked(self):
        # context_builder_v2 explicitly excludes ending, arc, lifeline
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {
                "name": "X", "role": "?",
                "ending": "BAD FUTURE ENDING", "arc": "BAD ARC STORY",
                "lifeline": "BAD LIFELINE",
                "current_vol": 1, "current_ch": 1,
            }
        ]
        result = cb._build_character_context_v2(repo, "n", 1)
        assert "BAD FUTURE ENDING" not in result
        assert "BAD ARC STORY" not in result
        assert "BAD LIFELINE" not in result


# ── _build_foreshadowing_context_v2 ──────────────────────────────────

class TestBuildForeshadowingContextV2:
    def test_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [], "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert result == ""

    def test_due_now_tier(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{
                "name": "FS1", "category": "剧情",
                "description": "desc1", "target_vol": 1, "target_ch": 5
            }],
            "overdue": [], "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "FS1" in result
        assert "🔴" in result
        assert "必须解决" in result
        assert "desc1" in result
        assert "第1卷第5章" in result

    def test_due_now_no_description_no_target_ch(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "F", "category": "剧情"}],
            "overdue": [], "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "F" in result

    def test_overdue_tier(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [{"name": "FS2", "target_vol": 1, "description": "desc2"}],
            "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 2)
        assert "FS2" in result
        assert "⚠️" in result
        assert "逾期" in result
        assert "desc2" in result

    def test_overdue_no_description(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [{"name": "OD"}],  # no target_vol, no description
            "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 2)
        assert "OD" in result
        assert "?" in result  # default for missing target_vol

    def test_recent_tier(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [],
            "recent": [{"name": "FS3", "introduced_vol": 1}]
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "FS3" in result
        assert "🟡" in result
        assert "近期" in result

    def test_recent_no_introduced_vol(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [],
            "recent": [{"name": "R"}]  # no introduced_vol
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "R" in result
        assert "?" in result

    def test_overdue_limit_3(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [{"name": f"O{i}", "target_vol": 1} for i in range(10)],
            "recent": []
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 2)
        assert "O0" in result
        assert "O1" in result
        assert "O2" in result
        assert "O3" not in result

    def test_recent_limit_2(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [],
            "recent": [{"name": f"R{i}", "introduced_vol": 1} for i in range(5)]
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "R0" in result
        assert "R1" in result
        assert "R2" not in result

    def test_all_three_tiers(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "NOW", "category": "剧情", "description": "d1"}],
            "overdue": [{"name": "OD", "target_vol": 1, "description": "d2"}],
            "recent": [{"name": "REC", "introduced_vol": 1}],
        }
        result = cb._build_foreshadowing_context_v2(repo, "n", 1)
        assert "NOW" in result
        assert "OD" in result
        assert "REC" in result


# ── _build_world_context_v2 ───────────────────────────────────────────

class TestBuildWorldContextV2:
    def test_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = []
        result = cb._build_world_context_v2(repo, "n", 1)
        assert result == ""

    def test_basic_entries(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = [
            {"domain": "地理", "name": "青云山", "content": "修仙门派所在地"},
        ]
        result = cb._build_world_context_v2(repo, "n", 1)
        assert "青云山" in result
        assert "地理" in result
        assert "修仙门派所在地" in result

    def test_passes_limit_5(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = []
        cb._build_world_context_v2(repo, "n", 1)
        repo.get_world_building_for_volume.assert_called_with("n", 1, limit=5)

    def test_content_truncation(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        long_content = "X" * 500
        repo.get_world_building_for_volume.return_value = [
            {"domain": "d", "name": "n", "content": long_content}
        ]
        result = cb._build_world_context_v2(repo, "n", 1)
        # Content should be truncated to 250 chars
        # "X" * 250 = 250 chars; truncation drops the rest
        assert "X" * 250 in result
        assert "X" * 251 not in result


# ── _build_pacing_context_v2 ──────────────────────────────────────────

class TestBuildPacingContextV2:
    def test_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = None
        result = cb._build_pacing_context_v2(repo, "n", 1, 1)
        assert result == ""

    def test_basic_pacing(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "紧张", "intensity": 8,
            "emotion_target": "压抑", "word_budget_min": 2500, "word_budget_max": 3500
        }
        result = cb._build_pacing_context_v2(repo, "n", 1, 1)
        assert "紧张" in result
        assert "8" in result
        assert "压抑" in result
        assert "2500" in result
        assert "3500" in result

    def test_no_emotion_target_uses_unset(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "缓", "intensity": 3,
            "word_budget_min": 2500, "word_budget_max": 3500
        }
        result = cb._build_pacing_context_v2(repo, "n", 1, 1)
        assert "未设定" in result

    def test_default_word_budgets(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "快", "intensity": 5,
        }
        result = cb._build_pacing_context_v2(repo, "n", 1, 1)
        # Defaults: 2500-3500
        assert "2500" in result
        assert "3500" in result


# ── _build_revelation_context_v2 ──────────────────────────────────────

class TestBuildRevelationContextV2:
    def test_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = []
        result = cb._build_revelation_context_v2(repo, "n", 1)
        assert result == ""

    def test_basic_revelations(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "身份", "name": "主角身份", "content": "实际上是大能转世"},
        ]
        result = cb._build_revelation_context_v2(repo, "n", 1)
        assert "主角身份" in result
        assert "身份" in result
        assert "实际上是大能转世" in result

    def test_content_truncated_to_200(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        long_content = "A" * 500
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "t", "name": "n", "content": long_content}
        ]
        result = cb._build_revelation_context_v2(repo, "n", 1)
        assert "A" * 200 in result
        assert "A" * 201 not in result

    def test_multiple_revelations(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "身份", "name": "A", "content": "a"},
            {"info_type": "关系", "name": "B", "content": "b"},
        ]
        result = cb._build_revelation_context_v2(repo, "n", 1)
        assert "A" in result
        assert "B" in result


# ── _build_plot_arc_context_v2 ────────────────────────────────────────

class TestBuildPlotArcContextV2:
    def test_empty(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = []
        result = cb._build_plot_arc_context_v2(repo, "n", 1)
        assert result == ""

    def test_basic_arcs(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "主线", "name": "复仇", "summary": "主角为家人复仇"},
        ]
        result = cb._build_plot_arc_context_v2(repo, "n", 1)
        assert "复仇" in result
        assert "主线" in result
        assert "主角为家人复仇" in result

    def test_summary_truncated_to_300(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        long_summary = "S" * 500
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "主线", "name": "A", "summary": long_summary}
        ]
        result = cb._build_plot_arc_context_v2(repo, "n", 1)
        assert "S" * 300 in result
        assert "S" * 301 not in result

    def test_multiple_arcs(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "主线", "name": "A", "summary": "sa"},
            {"type": "支线", "name": "B", "summary": "sb"},
        ]
        result = cb._build_plot_arc_context_v2(repo, "n", 1)
        assert "A" in result
        assert "B" in result


# ── _build_memory_context_v2 ──────────────────────────────────────────

class TestBuildMemoryContextV2:
    def test_returns_context_text(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "X"}]
        mock_ctx = MagicMock()
        mock_ctx.context_text = "memory text"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx):
            result = cb._build_memory_context_v2(repo, "n", 1, 1)
        assert result == "memory text"

    def test_returns_empty_when_no_context(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "X"}]
        with patch("memory_layer.retrieve_memory", return_value=None):
            result = cb._build_memory_context_v2(repo, "n", 1, 1)
        assert result == ""

    def test_handles_exception(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters.return_value = []
        with patch("memory_layer.retrieve_memory", side_effect=Exception("boom")):
            result = cb._build_memory_context_v2(repo, "n", 1, 1)
        assert result == ""

    def test_no_characters_uses_default(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters.return_value = None
        mock_ctx = MagicMock()
        mock_ctx.context_text = "memory"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx) as mock_rm:
            cb._build_memory_context_v2(repo, "n", 1, 1)
        call_kwargs = mock_rm.call_args.kwargs
        assert call_kwargs["character_names"] == ["主角"]
        assert call_kwargs["total_token_budget"] == 2000

    def test_passes_correct_params(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "A"}, {"name": "B"}]
        mock_ctx = MagicMock()
        mock_ctx.context_text = "mem"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx) as mock_rm:
            cb._build_memory_context_v2(repo, "novel_x", 3, 7)
        call_kwargs = mock_rm.call_args.kwargs
        assert call_kwargs["novel_name"] == "novel_x"
        assert call_kwargs["volume"] == 3
        assert call_kwargs["chapter_num"] == 7
        assert call_kwargs["character_names"] == ["A", "B"]


# ── _build_state_context_v2 ───────────────────────────────────────────

class TestBuildStateContextV2:
    def test_no_events_no_recent(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = []
        result = cb._build_state_context_v2(repo, "n", 1)
        assert result == ""

    def test_with_events(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = [
            {"vol": 1, "ch": 1, "event_type": "觉醒", "description": "主角觉醒了"}
        ]
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "觉醒" in result
        assert "主角" in result

    def test_event_description_truncated_to_120(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        long_desc = "D" * 500
        repo.get_recent_character_events.return_value = [
            {"vol": 1, "ch": 1, "event_type": "e", "description": long_desc}
        ]
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "D" * 120 in result
        assert "D" * 121 not in result

    def test_with_recent_chapters_fallback(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "第一章", "word_count": 3000}
        ]
        repo.list_characters.return_value = []
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "ch-001" in result
        assert "第一章" in result

    def test_with_recent_chapters_no_title(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-002", "word_count": 1500}  # no title
        ]
        repo.list_characters.return_value = []
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "ch-002" in result

    def test_with_active_characters(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        repo.list_characters.return_value = [
            {"name": "林风", "role": "主角", "current_vol": 1, "current_ch": 5,
             "current_status": "修炼"}
        ]
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "林风" in result
        assert "修炼" in result

    def test_active_chars_filtered_by_vol_range(self):
        # range: max(1, vol-2) <= current_vol <= vol
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        repo.list_characters.return_value = [
            {"name": "InRange", "current_vol": 5, "current_ch": 1, "current_status": "ok"},
            {"name": "TooOld", "current_vol": 1, "current_ch": 1},  # vol 5, range [3,5] -> excluded
        ]
        result = cb._build_state_context_v2(repo, "n", 5)
        assert "InRange" in result
        assert "TooOld" not in result

    def test_active_chars_5_limit(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        repo.list_characters.return_value = [
            {"name": f"C{i}", "current_vol": 5, "current_ch": 1, "current_status": "s"}
            for i in range(10)
        ]
        result = cb._build_state_context_v2(repo, "n", 5)
        assert "C0" in result
        assert "C4" in result
        assert "C5" not in result

    def test_character_at_volume_minus_2_included(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # vol 8, target 10 -> vol -2 included
        repo.list_characters.return_value = [
            {"name": "Boundary", "current_vol": 8, "current_ch": 1, "current_status": "s"}
        ]
        result = cb._build_state_context_v2(repo, "n", 10)
        assert "Boundary" in result

    def test_character_at_volume_minus_3_excluded(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # vol 7, target 10 -> vol -3 excluded
        repo.list_characters.return_value = [
            {"name": "FarOld", "current_vol": 7, "current_ch": 1, "current_status": "s"}
        ]
        result = cb._build_state_context_v2(repo, "n", 10)
        assert "FarOld" not in result

    def test_fallback_no_active_chars(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # Characters with no current_vol -> current_vol defaults to 0
        # 0 < max(1, 1-2) = 1 -> excluded
        repo.list_characters.return_value = [
            {"name": "NoVol", "current_vol": 0}
        ]
        result = cb._build_state_context_v2(repo, "n", 1)
        assert "NoVol" not in result

    def test_recent_chapters_passes_limit_10(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = []
        cb._build_state_context_v2(repo, "n", 1)
        repo.get_recent_chapters.assert_called_with("n", limit=10)

    def test_events_passes_max_chapters_15(self):
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        cb._build_state_context_v2(repo, "n", 1)
        repo.get_recent_character_events.assert_called_with("n", 1, max_chapters=15)

    def test_active_chars_missing_fields(self):
        """Missing role/current_vol/current_ch/current_status use defaults."""
        cb = _import_cb_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # No role, no current_vol, etc. — all use defaults
        repo.list_characters.return_value = [
            {"name": "Bare"}
        ]
        result = cb._build_state_context_v2(repo, "n", 1)
        # current_vol defaults to 0 < 1 -> excluded
        assert "Bare" not in result


# ── _build_style_context_simple ──────────────────────────────────────

class TestBuildStyleContextSimple:
    def test_empty(self):
        cb = _import_cb_v2()
        result = cb._build_style_context_simple("", "", "n")
        assert result == ""

    def test_style_only(self):
        cb = _import_cb_v2()
        result = cb._build_style_context_simple("辰东风", "", "n")
        assert "辰东风" in result

    def test_instructions_only(self):
        cb = _import_cb_v2()
        result = cb._build_style_context_simple("", "注重人物心理", "n")
        assert "注重人物心理" in result

    def test_both(self):
        cb = _import_cb_v2()
        result = cb._build_style_context_simple("辰东风", "注重人物心理", "n")
        assert "辰东风" in result
        assert "注重人物心理" in result


# ── build_context_volume_scoped ──────────────────────────────────────

class TestBuildContextVolumeScoped:
    def _mock_repo(self):
        repo = MagicMock()
        repo.get_novel.return_value = {"title": "测试", "genre": "玄幻", "word_goal": "100万"}
        repo.get_outline.return_value = None
        repo.get_danger_issue.return_value = None
        repo.get_chapter_by_num.return_value = None
        repo.list_characters_active_in_volume.return_value = []
        repo.get_foreshadowing_for_volume.return_value = {"due_now": [], "overdue": [], "recent": []}
        repo.get_world_building_for_volume.return_value = []
        repo.get_pacing.return_value = None
        repo.get_revelations_for_volume.return_value = []
        repo.get_plot_arcs_for_volume.return_value = []
        repo.list_characters.return_value = []
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = []
        return repo

    def _setup_patches(self):
        """Return a context manager stack of all needed patches."""
        from contextlib import ExitStack
        stack = ExitStack()
        repo = self._mock_repo()
        stack.enter_context(patch("context_builder_v2.get_repo", return_value=repo))
        stack.enter_context(patch("context_builder_v2._read_outline_yaml_v2", return_value=""))
        stack.enter_context(patch("memory_layer.retrieve_memory",
                                    return_value=MagicMock(context_text="")))
        # Mock get_prompt_manager so _get_core_instructions() and footer render return strings
        mock_pm = MagicMock()
        mock_pm.render_or_default.return_value = "CORE INSTRUCTIONS"
        mock_pm.render.return_value = ""
        stack.enter_context(patch("context_builder_v2.get_prompt_manager", return_value=mock_pm))
        return stack, repo

    def test_basic(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        assert "system_prompt" in result
        assert "layers" in result
        assert "total_tokens" in result
        assert "max_tokens" in result
        assert len(result["layers"]) == 12

    def test_layer_names_in_order(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        expected = [
            "核心指令", "项目元信息", "章节上下文", "角色上下文",
            "伏笔待办", "世界观", "节奏情感", "信息释放",
            "剧情弧线", "RAG记忆检索", "状态演化", "写作风格",
        ]
        actual = [l["name"] for l in result["layers"]]
        assert actual == expected

    def test_volume_string_parsing_vol_n(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": "vol-05", "chapter_num": 1}
            )
        assert result["max_tokens"] > 0

    def test_volume_plain_string_parsing(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": "3", "chapter_num": 1}
            )
        assert result["max_tokens"] > 0

    def test_no_novel_returns_empty_meta(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        repo = self._mock_repo()
        repo.get_novel.return_value = None
        with patch("context_builder_v2.get_repo", return_value=repo), \
             patch("context_builder_v2._read_outline_yaml_v2", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="")), \
             patch("context_builder_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "CORE"
            mock_pm.render.return_value = ""
            mock_pm_fn.return_value = mock_pm
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        meta_layer = next(l for l in result["layers"] if l["name"] == "项目元信息")
        assert meta_layer["content"] == ""

    def test_with_style_and_instructions(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped({
                "name": "test", "volume": 1, "chapter_num": 1,
                "style": "辰东风", "instructions": "注重人物"
            })
        style_layer = next(l for l in result["layers"] if l["name"] == "写作风格")
        assert "辰东风" in style_layer["content"]
        # Full instructions appear in the untruncated footer
        assert "注重人物" in result["system_prompt"]

    def test_cache_hit(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        params = {"name": "test", "volume": 1, "chapter_num": 1}
        repo = self._mock_repo()
        with patch("context_builder_v2.get_repo", return_value=repo), \
             patch("context_builder_v2._read_outline_yaml_v2", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="")), \
             patch("context_builder_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "CORE"
            mock_pm.render.return_value = ""
            mock_pm_fn.return_value = mock_pm
            r1 = cb.build_context_volume_scoped(params)
            r2 = cb.build_context_volume_scoped(params)
        assert r1 is r2

    def test_cache_key_includes_style(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            r1 = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1, "style": "A"}
            )
            r2 = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1, "style": "B"}
            )
        assert r1 is not r2

    def test_cache_key_includes_instructions(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            r1 = cb.build_context_volume_scoped({
                "name": "test", "volume": 1, "chapter_num": 1, "instructions": "X"
            })
            r2 = cb.build_context_volume_scoped({
                "name": "test", "volume": 1, "chapter_num": 1, "instructions": "Y"
            })
        assert r1 is not r2

    def test_cache_miss_after_ttl(self, monkeypatch):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        monkeypatch.setattr(cb, "_CONTEXT_CACHE_V2_TTL", 0.001)
        stack, _ = self._setup_patches()
        with stack:
            r1 = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
            time.sleep(0.05)
            r2 = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        assert r1 is not r2

    def test_cache_prunes_above_max(self, monkeypatch):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        monkeypatch.setattr(cb, "_CONTEXT_CACHE_V2_MAX", 3)
        stack, _ = self._setup_patches()
        with stack:
            for i in range(10):
                cb.build_context_volume_scoped(
                    {"name": "test", "volume": 1, "chapter_num": i}
                )
        assert len(cb._CONTEXT_CACHE_V2) <= 3

    def test_footer_from_prompt_manager(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        repo = self._mock_repo()
        mock_pm = MagicMock()
        mock_pm.render_or_default.return_value = "CORE"
        mock_pm.render.side_effect = lambda name, vars: (
            "CUSTOM FOOTER" if name == "chapter_context_footer" else ""
        )
        with patch("context_builder_v2.get_repo", return_value=repo), \
             patch("context_builder_v2._read_outline_yaml_v2", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="")), \
             patch("context_builder_v2.get_prompt_manager", return_value=mock_pm):
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        assert "CUSTOM FOOTER" in result["system_prompt"]

    def test_footer_default_when_empty(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        # Default footer includes volume and chapter
        assert "第1卷" in result["system_prompt"]
        assert "第1章" in result["system_prompt"]

    def test_footer_default_with_style(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped({
                "name": "test", "volume": 1, "chapter_num": 1,
                "style": "X", "instructions": "Y"
            })
        assert "风格：X" in result["system_prompt"]
        assert "用户指示：Y" in result["system_prompt"]

    def test_default_max_tokens(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        assert result["max_tokens"] == 12000

    def test_custom_max_tokens(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = cb.build_context_volume_scoped({
                "name": "test", "volume": 1, "chapter_num": 1, "max_tokens": 5000
            })
        assert result["max_tokens"] == 5000

    def test_default_chapter_num(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No chapter_num -> defaults to 1
            result = cb.build_context_volume_scoped({"name": "test", "volume": 1})
        assert "第1章" in result["system_prompt"]

    def test_default_volume(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No volume -> defaults to 1
            result = cb.build_context_volume_scoped({"name": "test", "chapter_num": 1})
        assert "第1卷" in result["system_prompt"]

    def test_default_name(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No name -> empty string (should not crash)
            result = cb.build_context_volume_scoped({"volume": 1, "chapter_num": 1})
        assert "system_prompt" in result

    def test_layers_with_data(self):
        cb = _import_cb_v2()
        cb._CONTEXT_CACHE_V2.clear()
        repo = self._mock_repo()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "current_vol": 1, "current_ch": 1}
        ]
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "FS", "category": "剧情"}],
            "overdue": [], "recent": []
        }
        repo.get_world_building_for_volume.return_value = [
            {"domain": "d", "name": "n", "content": "c"}
        ]
        repo.get_pacing.return_value = {
            "pace_type": "快", "intensity": 5,
            "word_budget_min": 2500, "word_budget_max": 3500
        }
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "t", "name": "n", "content": "c"}
        ]
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "t", "name": "n", "summary": "s"}
        ]
        repo.get_recent_character_events.return_value = [
            {"vol": 1, "ch": 1, "event_type": "e", "description": "d"}
        ]
        with patch("context_builder_v2.get_repo", return_value=repo), \
             patch("context_builder_v2._read_outline_yaml_v2", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="mem")), \
             patch("context_builder_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "CORE"
            mock_pm.render.return_value = ""
            mock_pm_fn.return_value = mock_pm
            result = cb.build_context_volume_scoped(
                {"name": "test", "volume": 1, "chapter_num": 1}
            )
        non_empty_layers = [l for l in result["layers"] if l["content"]]
        assert len(non_empty_layers) > 5
