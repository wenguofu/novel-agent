"""Tests for the writing-prompt-v2-optimization change.

Each test class is keyed to a section in
``openspec/changes/writing-prompt-v2-optimization/specs/context-builder/spec.md``.

These tests are written in TDD red phase — they assert the post-change
behavior and are expected to FAIL on the un-modified codebase.
"""
import os
import re
import sys
import logging
from pathlib import Path

import pytest

PORTAL_DIR = Path(__file__).resolve().parent.parent.parent / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))

# agent_executor lives in agent-system/scripts/ (not portal/) — the v2
# binary_contrasts test reads its hardcoded schema constant from there.
AGENT_SYSTEM_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "agent-system" / "scripts"
if str(AGENT_SYSTEM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AGENT_SYSTEM_SCRIPTS))


# ═══════════════════════════════════════════════════════════════════════
# 1. Footer source of truth
# ═══════════════════════════════════════════════════════════════════════

class TestFooterFromJinja:
    """Footer MUST come from `chapter_context_footer.j2`, not inline literal."""

    def test_footer_uses_jinja2_template(self, tmp_db):
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 2,
            "chapter_num": 7,
            "style": "",
            "instructions": "",
        })
        # The footer template at portal/prompts/chapter_context_footer.j2
        # renders: "当前卷：第{volume}卷 第{chapter_num}章" — MUST be present
        assert "第2卷 第7章" in result["system_prompt"], (
            "footer should render '第2卷 第7章' from chapter_context_footer.j2"
        )

    def test_footer_includes_style_and_instructions(self, tmp_db):
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "辰东风 80%",
            "instructions": "加快节奏",
        })
        # The j2 template renders style as "风格：{style}" and
        # instructions as "用户指示：{instructions}" per
        # prompts/chapter_context_footer.j2
        assert "风格：辰东风 80%" in result["system_prompt"]
        assert "用户指示：加快节奏" in result["system_prompt"]


# ═══════════════════════════════════════════════════════════════════════
# 2. current_status.md injection (Layer 1.5)
# ═══════════════════════════════════════════════════════════════════════

class TestCurrentStatusInjection:
    """Layer 1.5 reads from the `current_status` DB table (not a file).

    v2 update: the previous file-based read was replaced with a DB-backed
    read so the layer survives MySQL/SQLite parity, can be versioned, and
    can carry structured fields (target override, total word count, etc.)
    alongside the raw prose. The file is now a one-time migration source.
    """

    def test_current_status_included_when_db_row_present(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel("test_novel", title="测试", genre="玄幻", word_goal="1000000")
        # Seed the current_status row with structured + raw fields
        repo.upsert_current_status(
            "test_novel",
            current_volume=2,
            current_chapter=312,
            total_word_count=486000,
            protagonist_state="半神（神格碎片持有者·火之权柄 3/7）",
            key_tasks="1. 破解七重试炼 2. 抵御三波刺客 3. 完成神火契约",
            current_crisis="神格碎片与体内力量排斥, 72小时内必须融合",
            target_volume=1,
            target_chapter=1,
            raw_md="# 旧版状态文档（迁移前）\n",
        )
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        layer_names = [layer["name"] for layer in result["layers"]]
        assert "当前状态" in layer_names, f"expected 当前状态 layer, got {layer_names}"
        cs_layer = next(l for l in result["layers"] if l["name"] == "当前状态")
        # The layer must contain the structured fields and the override note
        assert "真实进度" in cs_layer["content"]
        assert "卷: 2" in cs_layer["content"]
        assert "章: 312" in cs_layer["content"]
        assert "总字数: 486000" in cs_layer["content"]
        assert "本次任务重写" in cs_layer["content"]
        assert "目标章节: **第1卷 第1章**" in cs_layer["content"]
        assert "半神" in cs_layer["content"]
        assert "72小时" in cs_layer["content"]

    def test_current_status_override_emitted_only_when_target_differs(self, tmp_db):
        # When target == current, no override note is emitted (avoids
        # noise on the common "writing the next chapter" path).
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel("test_novel", title="测试", genre="玄幻", word_goal="1000000")
        repo.upsert_current_status(
            "test_novel", current_volume=1, current_chapter=5,
            target_volume=1, target_chapter=6,
            raw_md="",
        )
        from context_builder import _build_current_status_context
        text = _build_current_status_context("test_novel")
        assert "本次任务重写" in text  # target != current → override shown
        # Change target to equal current, override should disappear
        repo.upsert_current_status(
            "test_novel", current_volume=1, current_chapter=5,
            target_volume=1, target_chapter=5,
            raw_md="",
        )
        text = _build_current_status_context("test_novel")
        assert "本次任务重写" not in text  # target == current → no override

    def test_current_status_missing_is_silent(self, tmp_db):
        # No current_status row, no state/current_status.md. build_context
        # must not raise, and the 当前状态 layer must be omitted.
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        assert result is not None
        layer_names = [layer["name"] for layer in result["layers"]]
        # The 当前状态 layer should not appear when the file is missing
        assert "当前状态" not in layer_names, (
            f"expected 当前状态 to be omitted when file missing, got {layer_names}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 3. Robust chapter locator
# ═══════════════════════════════════════════════════════════════════════

class TestChapterLocator:
    """Layer 2 locator must handle Chinese-numeral headings and miss cleanly."""

    def test_chinese_numeral_outline_recognized(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel("test_novel", title="测试", genre="玄幻", word_goal="1000000")
        # Chinese-numeral heading: 第一百二十三章
        repo.upsert_outline(
            "test_novel", "vol-01",
            "第一百二十二章 旧卷尾声\n旧章内容。\n"
            "第一百二十三章 新卷开篇\n新章内容：主角踏入新地界。\n"
            "第一百二十四章 试炼\n试炼开始。",
        )
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 123)
        # The outline slice must include chapter 123's content
        assert "新卷开篇" in text, f"Chinese-numeral locator missed; got: {text!r}"
        # And NOT include chapter 124's content (slice should stop at 124)
        assert "试炼开始" not in text

    def test_locator_miss_returns_empty_not_fallthrough(self, tmp_db, caplog):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel("test_novel", title="测试", genre="玄幻", word_goal="1000000")
        # Outline only has chapter 1; we ask for chapter 99 — every pattern
        # should miss.
        repo.upsert_outline(
            "test_novel", "vol-01",
            "第001章 开篇\n开篇内容：林渊觉醒血脉。\n"
            "第002章 试炼\n试炼开始。",
        )
        with caplog.at_level(logging.WARNING):
            from context_builder import _build_chapter_context
            text = _build_chapter_context("test_novel", 1, 99)
        # MUST NOT include chapter 1's content (the old fallthrough returned [:1500])
        assert "开篇内容" not in text, (
            f"fallthrough to outline[:1500] should be removed; got: {text!r}"
        )
        # MUST have logged a warning
        assert any("99" in rec.message and "miss" in rec.message.lower()
                   for rec in caplog.records), (
            f"expected miss warning, got log: {[r.message for r in caplog.records]}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. Layer 0 clamp
# ═══════════════════════════════════════════════════════════════════════

class TestCoreInstructionsClamp:
    """Layer 0 must be clamped to 500 tok regardless of source length."""

    def test_oversized_j2_is_clipped(self, tmp_db, monkeypatch):
        # Patch the j2 source on disk? Simpler: patch the rendered output
        # of the template to a long string and verify the layer is clipped.
        from context_builder import build_context
        import context_builder as cb

        def _fake_long_core():
            return "A" * 5000  # ~5000 estimated tokens at 1.0 per char
        monkeypatch.setattr(cb, "_get_core_instructions", _fake_long_core)
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        core_layer = next(l for l in result["layers"] if l["name"] == "核心指令")
        assert core_layer["tokens_used"] <= 500, (
            f"core layer must be clamped to 500 tok, got {core_layer['tokens_used']}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 5. danger_issue boundary-aware trim
# ═══════════════════════════════════════════════════════════════════════

class TestDangerIssueTrim:
    """danger_issue slice must stop at a sentence boundary, not mid-word."""

    def test_danger_trimmed_at_sentence_boundary(self, tmp_db):
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel("test_novel", title="测试", genre="玄幻", word_goal="1000000")
        # Build a 1500-char danger_issue: first 1180 chars end on a 。,
        # then 320 more chars of mid-sentence tail.
        long_text = ("A" * 1179) + "。" + ("B" * 320) + "残尾"
        assert len(long_text) == 1502
        repo.upsert_danger_issue("test_novel", "vol-01", 1, long_text)
        from context_builder import _build_chapter_context
        text = _build_chapter_context("test_novel", 1, 1)
        # Find the danger_issue section
        m = re.search(r"## 本章危机/关卡\n(.*?)$", text, re.MULTILINE | re.DOTALL)
        assert m, f"danger_issue section missing in: {text!r}"
        section = m.group(1)
        # Must end on a sentence boundary, not mid-sentence
        assert section.rstrip().endswith("。") or section.rstrip().endswith("！") \
            or section.rstrip().endswith("？"), (
            f"danger_issue not trimmed at sentence boundary, ends with: {section[-30:]!r}"
        )
        # Must NOT contain the mid-sentence "残尾" tail
        assert "残尾" not in section


# ═══════════════════════════════════════════════════════════════════════
# 6. max_binary_contrasts reconciliation
# ═══════════════════════════════════════════════════════════════════════

class TestBinaryContrastsReconcile:
    """j2 and Python constant must both say 2."""

    def test_binary_contrasts_constants_agree(self):
        from context_builder import _get_core_instructions
        text = _get_core_instructions()
        # j2 should mention "全文不超过2次"
        m = re.search(r"全文不超过(\d+)次", text)
        assert m, f"j2 doesn't contain '全文不超过N次' phrasing; got: {text!r}"
        j2_value = int(m.group(1))
        # agent_executor's hardcoded schema constant
        from agent_executor import _AGENT_SCHEMAS
        py_value = _AGENT_SCHEMAS["正文写作"]["content_heuristics"]["max_binary_contrasts"]
        assert j2_value == py_value == 2, (
            f"max_binary_contrasts mismatch: j2={j2_value}, py={py_value}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 7. delivery block instruction
# ═══════════════════════════════════════════════════════════════════════

class TestDeliveryBlockInstruction:
    """core_instructions must mention the delivery block schema."""

    def test_core_has_delivery_keyword(self):
        from context_builder import _get_core_instructions
        text = _get_core_instructions()
        assert "delivery" in text, "core_instructions must mention 'delivery' block"

    @pytest.mark.parametrize("field", [
        "chapter_file", "word_count", "style_applied",
        "new_settings_introduced", "character_state_changes", "foreshadowing_changes",
    ])
    def test_core_has_delivery_field(self, field):
        from context_builder import _get_core_instructions
        text = _get_core_instructions()
        assert field in text, f"core_instructions missing delivery field '{field}'"


# ═══════════════════════════════════════════════════════════════════════
# 5. Existing-chapter payload injection (app.py)
# ═══════════════════════════════════════════════════════════════════════

class TestExistingChapterPayload:
    """When the chapter file exists, api_generate_chapter_v2 must prepend
    the existing content (capped at 4000 tok) so the LLM has something to
    '续写' / '重写' — not just a hint with no payload.
    """

    def test_existing_chapter_payload_injected(self, tmp_path, monkeypatch, tmp_db):
        # Build a fake chapter file under tmp novels/ layout
        novel_name = "test_novel"
        manuscript = tmp_path / "novels" / novel_name / "manuscript" / "vol-01"
        manuscript.mkdir(parents=True)
        chapter_path = manuscript / "ch-0001.md"
        chapter_path.write_text(
            "# 第1章 觉醒\n\n旧版本正文。主角在山巅独坐，"
            "感觉血脉正在苏醒。这是一段已经写过的内容。",
            encoding="utf-8",
        )

        # Patch _resolve_novels_root so context_builder points at tmp_path
        from context_builder import _resolve_novels_root as _orig_resolve
        monkeypatch.setattr(
            "context_builder._resolve_novels_root",
            lambda: str(tmp_path / "novels"),
        )

        # Seed the novel so build_context can produce a non-trivial prompt
        from repository import get_repo
        repo = get_repo()
        repo.upsert_novel(novel_name, title="测试", genre="玄幻", word_goal="1000000")

        # Mimic the chapter-exists branch from api_generate_chapter_v2
        ch_file_path = chapter_path
        from context_builder import _truncate_to_tokens, build_context

        with open(ch_file_path, "r", encoding="utf-8") as f:
            existing_text = f.read()
        existing_block = _truncate_to_tokens(existing_text, 4000)

        ctx = build_context({
            "name": novel_name,
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        system_prompt = (
            "## 上一版本正文（仅供续写/重写参考，不要原样复制）\n"
            + existing_block
            + "\n\n"
            + ctx["system_prompt"]
        )
        system_prompt += "\n\n⚠️ 注意：该章节已存在，请基于已有内容续写或重写，保持一致性。"

        # The block must be present
        assert "## 上一版本正文" in system_prompt
        assert "旧版本正文" in system_prompt
        assert "已存在，请基于已有内容续写或重写" in system_prompt


# ═══════════════════════════════════════════════════════════════════════
# 9. Default max_tokens lifted to 500_000
# ═══════════════════════════════════════════════════════════════════════

class TestDefaultMaxTokens:
    """build_context default max_tokens is 500_000."""

    def test_default_max_tokens_is_500_000(self, tmp_db):
        from context_builder import build_context
        result = build_context({
            "name": "test_novel",
            "volume": 1,
            "chapter_num": 1,
            "style": "",
            "instructions": "",
        })
        assert result["max_tokens"] == 500_000, (
            f"default max_tokens should be 500_000, got {result['max_tokens']}"
        )
