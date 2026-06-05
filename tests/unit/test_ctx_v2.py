"""Unit tests for portal/ctx_v2.py (M3.1 W2 T2.7.7).

Targets line coverage 8% -> 90%+. Tests the 12-layer context builder
with mocked repo. Each layer builder is tested independently;
build_context is tested end-to-end with all layers.
"""
import importlib
import os
import time
from unittest.mock import MagicMock, patch

import pytest


def _import_ctx_v2():
    """Re-import ctx_v2 to reset module-level state (cache)."""
    # Drop cached modules so the per-test tmp_db / re-imports work
    for m in list(__import__("sys").modules):
        if m in ("ctx_v2",):
            del __import__("sys").modules[m]
    return importlib.import_module("ctx_v2")


# ── _core_instructions ─────────────────────────────────────────────────

class TestCoreInstructions:
    def test_returns_string(self):
        ctx_v2 = _import_ctx_v2()
        with patch("ctx_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "DEFAULT CORE INSTRUCTIONS"
            mock_pm_fn.return_value = mock_pm
            result = ctx_v2._core_instructions()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_falls_back_to_default_when_template_missing(self):
        ctx_v2 = _import_ctx_v2()
        with patch("ctx_v2.get_prompt_manager") as mock_pm_fn:
            mock_pm = MagicMock()
            mock_pm.render_or_default.return_value = "DEFAULT TEXT"
            mock_pm_fn.return_value = mock_pm
            result = ctx_v2._core_instructions()
        assert result == "DEFAULT TEXT"


# ── _yaml_outline ──────────────────────────────────────────────────────

class TestYamlOutline:
    def _patch_dirname(self, monkeypatch, tmp_path):
        """Patch os.path.dirname so that the project root is tmp_path."""
        def mock_dirname(path):
            return str(tmp_path)
        monkeypatch.setattr("ctx_v2.os.path.dirname", mock_dirname)

    def test_no_yaml_file_returns_empty(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("nonexistent", 1, 1)
        assert result == ""

    def test_yaml_chapter_match(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        yaml_content = (
            "chapters:\n"
            "  - number: 1\n"
            "    title: 第一章\n"
            "    function:\n"
            "      - 开端\n"
            "    core_events:\n"
            "      - 主角出场\n"
        )
        (novel_dir / "vol-01-chapters.yaml").write_text(yaml_content, encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)

        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "第一章" in result
        assert "开端" in result
        assert "主角出场" in result

    def test_yaml_no_matching_chapter_returns_volume_header(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 99\n    title: Other\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "第1卷大纲" in result

    def test_invalid_yaml_returns_empty(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "not valid yaml or json{[", encoding="utf-8"
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert result == ""

    def test_json_fallback(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            '{"chapters": [{"number": 1, "title": "JSON章"}]}',
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "JSON章" in result

    def test_danger_scenes_marker(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        yaml_content = (
            "volume_name: 卷名\n"
            "rhythm_rules:\n"
            "  danger_scenes: [1]\n"
            "  major_crises: [1]\n"
            "chapters:\n"
            "  - number: 1\n"
            "    title: 危险章\n"
        )
        (novel_dir / "vol-01-chapters.yaml").write_text(yaml_content, encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "高压章节" in result
        assert "重大危机章" in result

    def test_function_as_string(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n    function: single_func\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "single_func" in result

    def test_yml_extension(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yml").write_text(
            "chapters:\n  - number: 1\n    title: 第二章\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "第二章" in result

    def test_foreshadowing_and_ending_hook(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        yaml_content = (
            "chapters:\n"
            "  - number: 1\n"
            "    title: T\n"
            "    foreshadowing:\n"
            "      - 推进伏笔A\n"
            "      - 推进伏笔B\n"
            "    ending_hook: 主角陷入危机\n"
            "    style_hint: 紧张\n"
        )
        (novel_dir / "vol-01-chapters.yaml").write_text(yaml_content, encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "推进伏笔A" in result
        assert "结尾牵引" in result
        assert "主角陷入危机" in result
        assert "风格提示" in result

    def test_foreshadowing_as_string(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n    foreshadowing: 单一伏笔\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "单一伏笔" in result

    def test_non_dict_data_returns_empty(self, tmp_path, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "- just a list\n- not a dict\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert result == ""

    def test_yaml_exception_falls_back_to_json_failure(self, tmp_path, monkeypatch):
        """When yaml.safe_load raises and json.loads also fails -> return ""."""
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text("anything", encoding="utf-8")
        self._patch_dirname(monkeypatch, tmp_path)

        import yaml as real_yaml
        with patch.object(real_yaml, "safe_load", side_effect=Exception("yaml boom")):
            result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert result == ""

    def test_core_events_as_string(self, tmp_path, monkeypatch):
        """core_events can be a single string (not a list)."""
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "chapters:\n  - number: 1\n    title: T\n    core_events: 单一事件\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "单一事件" in result

    def test_volume_name_in_volume_header(self, tmp_path, monkeypatch):
        """When chapter doesn't match, volume_name is included in header."""
        ctx_v2 = _import_ctx_v2()
        novel_dir = tmp_path / "novels" / "my_novel" / "outline"
        novel_dir.mkdir(parents=True)
        (novel_dir / "vol-01-chapters.yaml").write_text(
            "volume_name: 卷名\nchapters:\n  - number: 99\n",
            encoding="utf-8",
        )
        self._patch_dirname(monkeypatch, tmp_path)
        result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "卷名" in result

    def test_open_raises_continues_to_yml(self, tmp_path, monkeypatch):
        """If .yaml open raises, the function continues to try .yml."""
        ctx_v2 = _import_ctx_v2()
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
            result = ctx_v2._yaml_outline("my_novel", 1, 1)
        assert "Yml章" in result


# ── _chapter_ctx ───────────────────────────────────────────────────────

class TestChapterCtx:
    def test_with_yaml_outline(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_danger_issue.return_value = None
        repo.get_chapter_by_num.return_value = None
        with patch("ctx_v2._yaml_outline", return_value="## 第1卷第1章 写作指令\n内容"):
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        assert "写作指令" in result

    def test_with_db_outline_match(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            repo.get_outline.return_value = {
                "content": "第 001 章 介绍\n第二章 发展\n\n详细描述..."
            }
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        assert "卷纲要求" in result

    def test_db_outline_no_match_falls_back_to_full(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            # No "第001章" pattern -> fall back to first 1500 chars
            repo.get_outline.return_value = {"content": "Just a summary."}
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        assert "本卷大纲" in result

    def test_db_outline_none(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        assert isinstance(result, str)

    def test_with_danger_issue(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = {"content": "危险！"}
            repo.get_chapter_by_num.return_value = None
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        assert "危机" in result or "关卡" in result

    def test_with_previous_chapter(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = {"content": "前章结尾"}
            # chapter_num > 1
            result = ctx_v2._chapter_ctx("n", 1, 2, repo)
        assert "上一章" in result

    def test_chapter_1_no_previous(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        with patch("ctx_v2._yaml_outline", return_value=""):
            repo.get_outline.return_value = None
            repo.get_danger_issue.return_value = None
            repo.get_chapter_by_num.return_value = None
            # chapter_num = 1 -> no previous chapter lookup
            result = ctx_v2._chapter_ctx("n", 1, 1, repo)
        # Should not raise
        assert isinstance(result, str)


# ── _char_ctx ──────────────────────────────────────────────────────────

class TestCharCtx:
    def test_no_active_chars(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = []
        result = ctx_v2._char_ctx(repo, "n", 1)
        assert result == ""

    def test_basic_char(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "林风", "role": "主角", "current_vol": 1, "current_ch": 1}
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)
        assert "林风" in result
        assert "主角" in result

    def test_character_with_all_fields(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {
                "name": "林风", "role": "主角",
                "identity": "剑客", "personality": "冷静",
                "current_status": "修炼中", "emotional_state": "平静",
                "current_vol": 1, "current_ch": 5,
            }
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)
        assert "剑客" in result
        assert "冷静" in result
        assert "修炼中" in result
        assert "平静" in result
        assert "第1卷第5章" in result

    def test_character_limit_5(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        # 10 characters -> only first 5 included
        repo.list_characters_active_in_volume.return_value = [
            {"name": f"角色{i}", "role": "?", "current_vol": 1, "current_ch": 1}
            for i in range(10)
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)
        # Only first 5 names
        assert "角色0" in result
        assert "角色4" in result
        assert "角色5" not in result

    def test_identity_only_in_current_or_past_vol(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        # Character whose identity is in a FUTURE volume -> skip
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "future_identity", "current_vol": 5}
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)  # current_vol=1
        # Identity should NOT be included (5 > 1)
        assert "future_identity" not in result

    def test_identity_in_past_vol_included(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "past_identity", "current_vol": 1}
        ]
        result = ctx_v2._char_ctx(repo, "n", 2)  # current_vol=2
        # Identity SHOULD be included (1 <= 2)
        assert "past_identity" in result

    def test_identity_at_current_vol_included(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "X", "role": "?", "identity": "current_identity", "current_vol": 2}
        ]
        result = ctx_v2._char_ctx(repo, "n", 2)  # current_vol=2
        # Identity SHOULD be included (2 <= 2)
        assert "current_identity" in result

    def test_no_role_uses_question_mark(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters_active_in_volume.return_value = [
            {"name": "NoRole", "current_vol": 1, "current_ch": 1}
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)
        assert "NoRole" in result
        assert "(?)" in result

    def test_field_truncation(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        long_identity = "身份" * 200  # 400 chars, should be truncated to 200
        long_personality = "性格" * 200  # 400 chars, should be truncated to 150
        repo.list_characters_active_in_volume.return_value = [
            {
                "name": "Y", "role": "?",
                "identity": long_identity,
                "personality": long_personality,
                "current_vol": 1, "current_ch": 1,
            }
        ]
        result = ctx_v2._char_ctx(repo, "n", 1)
        # Identity truncated to 200 chars (1 from "身份：" header + 100 from value)
        assert result.count("身份") == 101
        # Personality truncated to 150 chars (0 from "性格：" header truncation)
        # The "性格：" header is one occurrence, value is 150 chars = 75 pairs
        assert result.count("性格") == 76  # 1 header + 75 value


# ── _fs_ctx ────────────────────────────────────────────────────────────

class TestFsCtx:
    def test_empty(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [], "overdue": [], "recent": []
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert result == ""

    def test_due_now(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "FS1", "category": "剧情", "description": "desc1"}],
            "overdue": [], "recent": []
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert "FS1" in result
        assert "必须解决" in result or "🔴" in result
        assert "desc1" in result

    def test_overdue(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [{"name": "FS2", "target_vol": 1, "description": "desc2"}],
            "recent": []
        }
        result = ctx_v2._fs_ctx(repo, "n", 2)  # current > target -> overdue
        assert "FS2" in result
        assert "逾期" in result or "⚠️" in result

    def test_recent(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [],
            "recent": [{"name": "FS3", "introduced_vol": 1}]
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert "FS3" in result
        assert "近期" in result or "🟡" in result

    def test_overdue_limit_3(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [{"name": f"FS{i}", "target_vol": 1} for i in range(10)],
            "recent": []
        }
        result = ctx_v2._fs_ctx(repo, "n", 2)
        # Only first 3 overdue should appear
        assert "FS0" in result
        assert "FS2" in result
        assert "FS3" not in result

    def test_recent_limit_2(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [],
            "overdue": [],
            "recent": [{"name": f"FS{i}", "introduced_vol": 1} for i in range(5)]
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert "FS0" in result
        assert "FS1" in result
        assert "FS2" not in result

    def test_due_now_no_description(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "F", "category": "剧情"}],  # no description
            "overdue": [], "recent": []
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert "F" in result

    def test_all_three_tiers(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_foreshadowing_for_volume.return_value = {
            "due_now": [{"name": "NOW", "category": "剧情", "description": "now desc"}],
            "overdue": [{"name": "OD", "target_vol": 1, "description": "od desc"}],
            "recent": [{"name": "REC", "introduced_vol": 1}],
        }
        result = ctx_v2._fs_ctx(repo, "n", 1)
        assert "NOW" in result
        assert "OD" in result
        assert "REC" in result


# ── _wb_ctx ────────────────────────────────────────────────────────────

class TestWbCtx:
    def test_empty(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = []
        result = ctx_v2._wb_ctx(repo, "n", 1)
        assert result == ""

    def test_basic_entries(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = [
            {"domain": "地理", "name": "青云山", "content": "修仙门派所在地"},
        ]
        result = ctx_v2._wb_ctx(repo, "n", 1)
        assert "青云山" in result
        assert "地理" in result
        assert "修仙门派所在地" in result

    def test_multiple_entries(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_world_building_for_volume.return_value = [
            {"domain": "地理", "name": "山", "content": "c1"},
            {"domain": "势力", "name": "门派", "content": "c2"},
            {"domain": "修炼", "name": "功法", "content": "c3"},
        ]
        result = ctx_v2._wb_ctx(repo, "n", 1)
        assert "山" in result
        assert "门派" in result
        assert "功法" in result


# ── _pace_ctx ──────────────────────────────────────────────────────────

class TestPaceCtx:
    def test_empty(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = None
        result = ctx_v2._pace_ctx(repo, "n", 1, 1)
        assert result == ""

    def test_basic_pacing(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "紧张", "intensity": 8,
            "emotion_target": "压抑", "word_budget_min": 2500, "word_budget_max": 3500
        }
        result = ctx_v2._pace_ctx(repo, "n", 1, 1)
        assert "紧张" in result
        assert "8" in result
        assert "压抑" in result
        assert "2500" in result
        assert "3500" in result

    def test_no_emotion_target(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "缓", "intensity": 3,
            "word_budget_min": 2500, "word_budget_max": 3500
        }
        result = ctx_v2._pace_ctx(repo, "n", 1, 1)
        assert "未设定" in result

    def test_default_word_budgets(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_pacing.return_value = {
            "pace_type": "快", "intensity": 5,
        }
        result = ctx_v2._pace_ctx(repo, "n", 1, 1)
        assert "2500" in result
        assert "3500" in result


# ── _rev_ctx ───────────────────────────────────────────────────────────

class TestRevCtx:
    def test_empty(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = []
        result = ctx_v2._rev_ctx(repo, "n", 1)
        assert result == ""

    def test_basic_revelations(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "身份", "name": "主角身份", "content": "实际上是大能转世"},
        ]
        result = ctx_v2._rev_ctx(repo, "n", 1)
        assert "主角身份" in result
        assert "身份" in result
        assert "实际上是大能转世" in result

    def test_multiple_revelations(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_revelations_for_volume.return_value = [
            {"info_type": "身份", "name": "A", "content": "a"},
            {"info_type": "关系", "name": "B", "content": "b"},
        ]
        result = ctx_v2._rev_ctx(repo, "n", 1)
        assert "A" in result
        assert "B" in result


# ── _arc_ctx ───────────────────────────────────────────────────────────

class TestArcCtx:
    def test_empty(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = []
        result = ctx_v2._arc_ctx(repo, "n", 1)
        assert result == ""

    def test_basic_arcs(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "主线", "name": "复仇", "summary": "主角为家人复仇"},
        ]
        result = ctx_v2._arc_ctx(repo, "n", 1)
        assert "复仇" in result
        assert "主线" in result
        assert "主角为家人复仇" in result

    def test_multiple_arcs(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_plot_arcs_for_volume.return_value = [
            {"type": "主线", "name": "主线A", "summary": "summaryA"},
            {"type": "支线", "name": "支线B", "summary": "summaryB"},
        ]
        result = ctx_v2._arc_ctx(repo, "n", 1)
        assert "主线A" in result
        assert "支线B" in result


# ── _mem_ctx ───────────────────────────────────────────────────────────

class TestMemCtx:
    def test_returns_context_text(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "X"}]
        mock_ctx = MagicMock()
        mock_ctx.context_text = "memory text"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx):
            result = ctx_v2._mem_ctx(repo, "n", 1, 1)
        assert result == "memory text"

    def test_returns_empty_when_no_context(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "X"}]
        with patch("memory_layer.retrieve_memory", return_value=None):
            result = ctx_v2._mem_ctx(repo, "n", 1, 1)
        assert result == ""

    def test_handles_exception(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters.return_value = []
        with patch("memory_layer.retrieve_memory", side_effect=Exception("boom")):
            result = ctx_v2._mem_ctx(repo, "n", 1, 1)
        assert result == ""

    def test_no_characters_uses_default(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters.return_value = None
        mock_ctx = MagicMock()
        mock_ctx.context_text = "memory"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx) as mock_rm:
            result = ctx_v2._mem_ctx(repo, "n", 1, 1)
        # Should pass default ["主角"] as character_names
        call_kwargs = mock_rm.call_args.kwargs
        assert call_kwargs["character_names"] == ["主角"]

    def test_passes_correct_params(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.list_characters.return_value = [{"name": "A"}, {"name": "B"}]
        mock_ctx = MagicMock()
        mock_ctx.context_text = "mem"
        with patch("memory_layer.retrieve_memory", return_value=mock_ctx) as mock_rm:
            ctx_v2._mem_ctx(repo, "novel_x", 3, 7)
        call_kwargs = mock_rm.call_args.kwargs
        assert call_kwargs["novel_name"] == "novel_x"
        assert call_kwargs["volume"] == 3
        assert call_kwargs["chapter_num"] == 7
        assert call_kwargs["character_names"] == ["A", "B"]


# ── _state_ctx ─────────────────────────────────────────────────────────

class TestStateCtx:
    def test_no_events_no_recent(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = []
        result = ctx_v2._state_ctx(repo, "n", 1)
        assert result == ""

    def test_with_events(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = [
            {"vol": 1, "ch": 1, "event_type": "觉醒", "description": "主角觉醒了"}
        ]
        result = ctx_v2._state_ctx(repo, "n", 1)
        assert "觉醒" in result
        assert "主角" in result

    def test_with_recent_chapters_fallback(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "第一章", "word_count": 3000}
        ]
        repo.list_characters.return_value = []
        result = ctx_v2._state_ctx(repo, "n", 1)
        assert "ch-001" in result
        assert "第一章" in result

    def test_with_recent_chapters_no_title(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-002", "word_count": 1500}  # no title
        ]
        repo.list_characters.return_value = []
        result = ctx_v2._state_ctx(repo, "n", 1)
        # Should fall back to chapter_ref
        assert "ch-002" in result

    def test_with_active_characters(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        repo.list_characters.return_value = [
            {"name": "林风", "role": "主角", "current_vol": 1, "current_ch": 5,
             "current_status": "修炼"}
        ]
        result = ctx_v2._state_ctx(repo, "n", 1)
        # Character in current volume range (-2 to current) should appear
        assert "林风" in result
        assert "修炼" in result

    def test_character_outside_range_excluded(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # Character far in the past (vol 1, current vol 10) -> excluded
        repo.list_characters.return_value = [
            {"name": "OldChar", "current_vol": 1, "current_ch": 1}
        ]
        result = ctx_v2._state_ctx(repo, "n", 10)
        assert "OldChar" not in result

    def test_character_limit_5(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        repo.list_characters.return_value = [
            {"name": f"C{i}", "current_vol": 10, "current_ch": 1, "current_status": "s"}
            for i in range(10)
        ]
        result = ctx_v2._state_ctx(repo, "n", 10)
        # Only first 5 chars
        assert "C0" in result
        assert "C4" in result
        assert "C5" not in result

    def test_character_at_volume_minus_2(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # vol 8, target vol 10 -> vol -2 included
        repo.list_characters.return_value = [
            {"name": "Boundary", "current_vol": 8, "current_ch": 1, "current_status": "s"}
        ]
        result = ctx_v2._state_ctx(repo, "n", 10)
        assert "Boundary" in result

    def test_character_at_volume_minus_3_excluded(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # vol 7, target vol 10 -> vol -3 excluded
        repo.list_characters.return_value = [
            {"name": "FarOld", "current_vol": 7, "current_ch": 1, "current_status": "s"}
        ]
        result = ctx_v2._state_ctx(repo, "n", 10)
        assert "FarOld" not in result

    def test_fallback_no_active_chars(self):
        ctx_v2 = _import_ctx_v2()
        repo = MagicMock()
        repo.get_recent_character_events.return_value = []
        repo.get_recent_chapters.return_value = [
            {"chapter_ref": "ch-001", "title": "T", "word_count": 1000}
        ]
        # Characters with no current_vol
        repo.list_characters.return_value = [
            {"name": "NoVol", "current_vol": 0}
        ]
        result = ctx_v2._state_ctx(repo, "n", 1)
        # 0 is < max(1, 1-2)=1, so excluded
        assert "NoVol" not in result


# ── build_context ──────────────────────────────────────────────────────

class TestBuildContext:
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
        stack.enter_context(patch("ctx_v2.get_repo", return_value=repo))
        stack.enter_context(patch("ctx_v2._yaml_outline", return_value=""))
        stack.enter_context(patch("memory_layer.retrieve_memory",
                                    return_value=MagicMock(context_text="")))
        # Mock get_prompt_manager so _core_instructions() returns a string
        mock_pm = MagicMock()
        mock_pm.render_or_default.return_value = "CORE INSTRUCTIONS"
        mock_pm.render.return_value = ""
        stack.enter_context(patch("ctx_v2.get_prompt_manager", return_value=mock_pm))
        return stack, repo

    def test_basic(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        assert "system_prompt" in result
        assert "layers" in result
        assert "total_tokens" in result
        assert "max_tokens" in result
        assert len(result["layers"]) == 12

    def test_layer_names_in_order(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        expected = [
            "核心指令", "项目元信息", "章节上下文", "角色上下文",
            "伏笔待办", "世界观", "节奏情感", "信息释放",
            "剧情弧线", "RAG记忆检索", "状态演化", "写作风格",
        ]
        actual = [l["name"] for l in result["layers"]]
        assert actual == expected

    def test_volume_string_parsing(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": "vol-05", "chapter_num": 1})
        # Volume should be parsed to 5
        assert result["max_tokens"] > 0

    def test_volume_plain_string_parsing(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": "3", "chapter_num": 1})
        assert result["max_tokens"] > 0

    def test_no_novel_returns_empty_meta(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        repo = self._mock_repo()
        repo.get_novel.return_value = None
        with patch("ctx_v2.get_repo", return_value=repo), \
             patch("ctx_v2._yaml_outline", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="")):
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        # Meta layer should be empty
        meta_layer = next(l for l in result["layers"] if l["name"] == "项目元信息")
        assert meta_layer["content"] == ""

    def test_with_style_and_instructions(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({
                "name": "test", "volume": 1, "chapter_num": 1,
                "style": "辰东风", "instructions": "注重人物心理"
            })
        # Style layer should include style and instructions
        style_layer = next(l for l in result["layers"] if l["name"] == "写作风格")
        assert "辰东风" in style_layer["content"]
        assert "注重人物心理" in style_layer["content"]

    def test_cache_hit(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        params = {"name": "test", "volume": 1, "chapter_num": 1}
        repo = self._mock_repo()
        with patch("ctx_v2.get_repo", return_value=repo) as mock_repo_fn, \
             patch("ctx_v2._yaml_outline", return_value=""), \
             patch("memory_layer.retrieve_memory", return_value=MagicMock(context_text="")):
            r1 = ctx_v2.build_context(params)
            # Second call should hit cache -> mock repo not called again
            r2 = ctx_v2.build_context(params)
        assert r1 is r2

    def test_cache_key_includes_style(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            r1 = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1, "style": "A"})
            r2 = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1, "style": "B"})
        # Different style -> different cache key -> different results
        assert r1 is not r2

    def test_cache_key_includes_instructions(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            r1 = ctx_v2.build_context({
                "name": "test", "volume": 1, "chapter_num": 1, "instructions": "X"
            })
            r2 = ctx_v2.build_context({
                "name": "test", "volume": 1, "chapter_num": 1, "instructions": "Y"
            })
        # Different instructions -> different cache key
        assert r1 is not r2

    def test_cache_miss_after_ttl(self, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        monkeypatch.setattr(ctx_v2, "_CONTEXT_CACHE_V2_TTL", 0.001)
        stack, _ = self._setup_patches()
        with stack:
            r1 = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
            time.sleep(0.05)
            r2 = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        # After TTL, cache miss -> new build
        assert r1 is not r2

    def test_cache_prunes_above_max(self, monkeypatch):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        monkeypatch.setattr(ctx_v2, "_CONTEXT_CACHE_V2_MAX", 3)
        stack, _ = self._setup_patches()
        with stack:
            for i in range(10):
                ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": i})
        # Cache should be capped
        assert len(ctx_v2._CONTEXT_CACHE_V2) <= 3

    def test_footer_from_prompt_manager(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        repo = self._mock_repo()
        mock_pm = MagicMock()
        mock_pm.render_or_default.return_value = "CORE"
        mock_pm.render.side_effect = lambda name, vars: (
            "CUSTOM FOOTER" if name == "chapter_context_footer" else ""
        )
        with patch("ctx_v2.get_repo", return_value=repo), \
             patch("ctx_v2._yaml_outline", return_value=""), \
             patch("memory_layer.retrieve_memory", return_value=MagicMock(context_text="")), \
             patch("ctx_v2.get_prompt_manager", return_value=mock_pm):
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        assert "CUSTOM FOOTER" in result["system_prompt"]

    def test_footer_default_when_empty(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        # Override get_prompt_manager to return empty footer
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        # Default footer includes volume and chapter
        assert "第1卷" in result["system_prompt"]
        assert "第1章" in result["system_prompt"]

    def test_footer_default_with_style(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({
                "name": "test", "volume": 1, "chapter_num": 1,
                "style": "X", "instructions": "Y"
            })
        # Default footer should include style and instructions
        assert "风格：X" in result["system_prompt"]
        assert "用户指示：Y" in result["system_prompt"]

    def test_default_max_tokens(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        assert result["max_tokens"] == 12000

    def test_custom_max_tokens(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            result = ctx_v2.build_context(
                {"name": "test", "volume": 1, "chapter_num": 1, "max_tokens": 5000}
            )
        assert result["max_tokens"] == 5000

    def test_default_chapter_num(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No chapter_num -> defaults to 1
            result = ctx_v2.build_context({"name": "test", "volume": 1})
        assert "第1章" in result["system_prompt"]

    def test_default_volume(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No volume -> defaults to 1
            result = ctx_v2.build_context({"name": "test", "chapter_num": 1})
        assert "第1卷" in result["system_prompt"]

    def test_default_name(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
        stack, _ = self._setup_patches()
        with stack:
            # No name -> empty string (should not crash)
            result = ctx_v2.build_context({"volume": 1, "chapter_num": 1})
        assert "system_prompt" in result

    def test_layers_with_data(self):
        ctx_v2 = _import_ctx_v2()
        ctx_v2._CONTEXT_CACHE_V2.clear()
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
        with patch("ctx_v2.get_repo", return_value=repo), \
             patch("ctx_v2._yaml_outline", return_value=""), \
             patch("memory_layer.retrieve_memory",
                   return_value=MagicMock(context_text="mem")):
            result = ctx_v2.build_context({"name": "test", "volume": 1, "chapter_num": 1})
        # Some layer content should now be non-empty
        non_empty_layers = [l for l in result["layers"] if l["content"]]
        assert len(non_empty_layers) > 5
