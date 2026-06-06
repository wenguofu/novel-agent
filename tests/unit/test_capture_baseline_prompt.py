"""Unit test for scripts/capture_baseline_prompt.py (M3.2 W5 helper).

Exercises ``main()`` end-to-end with ``build_context`` mocked, asserting
the baseline markdown file is created at the expected path with the
expected structure.

Option A (chosen) — mocks ``build_context`` directly:
  * fast (no DB seeding, no template rendering, no tokenizer load)
  * deterministic (known totals + layer count in assertions)
  * still exercises the real ``main()`` (file I/O, format string, footer)

The output path is redirected by monkey-patching the loaded module's
``__file__`` attribute, which the script reads via ``os.path.dirname``
at call time — so the file lands under ``tmp_path/docs/prompts/`` and
the real ``docs/prompts/`` directory is left untouched.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "capture_baseline_prompt.py"


@pytest.fixture
def script_module(tmp_path):
    """Load capture_baseline_prompt.py as a fresh module + redirect output.

    Adapted: the script computes its output path via
    ``os.path.dirname(__file__) + "/../docs/prompts/..."``. Setting
    ``module.__file__`` to a path under ``tmp_path`` causes the relative
    ``..`` traversal to resolve under ``tmp_path`` as well, so we never
    write into the real ``docs/prompts/`` directory.
    """
    # Snapshot sys.modules so the script's ``sys.path.insert`` + module
    # cache mutation doesn't leak into sibling tests.
    snapshot_modules = set(sys.modules)
    snapshot_syspath = list(sys.path)

    spec = importlib.util.spec_from_file_location(
        "capture_baseline_prompt_under_test",
        str(SCRIPT_PATH),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Redirect output: pretend the script lives at tmp_path/scripts/foo.py
    # so dirname(__file__)/../docs/prompts/ resolves to tmp_path/docs/prompts/.
    fake_scripts_dir = tmp_path / "scripts"
    fake_scripts_dir.mkdir(parents=True, exist_ok=True)
    mod.__file__ = str(fake_scripts_dir / "capture_baseline_prompt.py")

    yield mod

    # Restore module table + sys.path so the next test sees pristine state.
    for name in list(sys.modules):
        if name not in snapshot_modules:
            del sys.modules[name]
    sys.path[:] = snapshot_syspath


def _fake_build_context(_params):
    """Return a deterministic shape matching context_builder.build_context."""
    return {
        "system_prompt": "## fake system prompt\nwith multiple lines\n",
        "layers": [
            {"name": f"layer_{i}", "content": f"c{i}", "tokens_used": 100}
            for i in range(12)
        ],
        "total_tokens": 1234,
        "max_tokens": 10000,
    }


def test_main_writes_baseline_file_with_expected_structure(
    script_module, tmp_path, monkeypatch, capsys
):
    """main() creates baseline_<novel>_vol01_ch001.md with metadata header,
    layer breakdown, and the fenced system_prompt body."""
    # Mock build_context inside the loaded module's namespace.
    monkeypatch.setattr(script_module, "build_context", _fake_build_context)

    # Run the real main() — exercises file I/O, format strings, header.
    script_module.main()

    # The script writes to dirname(__file__)/../docs/prompts/baseline_...md.
    # With __file__ pointed at tmp_path/scripts/, that resolves under tmp_path.
    novel_slug = script_module.NOVEL.replace("/", "_")
    expected_name = (
        f"baseline_{novel_slug}"
        f"_vol{script_module.VOLUME:02d}"
        f"_ch{script_module.CHAPTER_NUM:03d}.md"
    )
    out_path = tmp_path / "docs" / "prompts" / expected_name
    assert out_path.exists(), f"baseline file not found at {out_path}"

    content = out_path.read_text(encoding="utf-8")

    # Header block (markdown title + metadata lines)
    assert f"# Baseline prompt — {script_module.NOVEL}" in content
    assert "**Captured:**" in content
    assert "**Total tokens:** 1234" in content
    assert "**Max tokens:** 10000" in content
    assert "**Layers:** 12" in content

    # Layer breakdown section + at least one entry from the fake
    assert "## Layer breakdown" in content
    assert "- layer_0: 100 tokens" in content
    assert "- layer_11: 100 tokens" in content

    # System prompt fenced block with the mocked body
    assert "## System prompt" in content
    assert "```" in content
    assert "fake system prompt" in content

    # Stdout reports the write + totals
    captured = capsys.readouterr()
    assert "Baseline prompt written to" in captured.out
    assert "1234" in captured.out
    assert "Layers: 12" in captured.out


def test_main_uses_real_build_context_signature(script_module, monkeypatch):
    """Smoke check: main() invokes build_context with the documented
    keyword-bearing dict (name/volume/chapter_num/style/instructions/
    max_tokens) so a future signature drift breaks this test, not prod.
    """
    captured_params = {}

    def spy(params):
        captured_params.update(params)
        return _fake_build_context(params)

    monkeypatch.setattr(script_module, "build_context", spy)
    script_module.main()

    # All six documented keys must be passed through.
    assert captured_params["name"] == script_module.NOVEL
    assert captured_params["volume"] == script_module.VOLUME
    assert captured_params["chapter_num"] == script_module.CHAPTER_NUM
    assert captured_params["style"] == script_module.STYLE
    assert captured_params["instructions"] == script_module.INSTRUCTIONS
    assert captured_params["max_tokens"] == script_module.MAX_TOKENS
