"""Tests for scripts/render_spec.py — the Jinja2 renderer."""
from pathlib import Path

FIXTURE_INV = Path(__file__).parent / "fixtures" / "mini_inventory.json"
TEMPLATE = Path(__file__).parent.parent / "docs" / "system-functional-spec.j2.md"


def test_render_contains_endpoint_section_heading():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "#### Endpoint: GET /api/novels" in out
    assert "#### Endpoint: POST /api/context/build" in out


def test_render_includes_repo_method_index():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "repo.list_novels" in out
    assert "repo.list_genre_rules" in out


def test_render_emits_empty_manual_notes_placeholder_by_default():
    from render_spec import render_spec
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes={})
    assert "<!-- MANUAL: GET_/api/novels -->" in out
    assert "<!-- /MANUAL -->" in out


def test_render_substitutes_manual_notes_when_provided():
    from render_spec import render_spec
    notes = {
        "GET_/api/novels": "Returns the list of registered novels. See README 'API endpoints' table."
    }
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes=notes)
    # The provided note replaces the empty placeholder body
    assert "Returns the list of registered novels." in out
    assert "<!-- MANUAL: GET_/api/novels -->" in out  # anchor still present


def test_extract_manual_notes_round_trip(tmp_path):
    """If an existing spec.md has Manual Notes, they should be parseable
    so the caller can re-render without losing them."""
    from render_spec import extract_manual_notes
    existing = tmp_path / "spec.md"
    existing.write_text(
        "# Spec\n"
        "<!-- MANUAL: GET_/api/novels -->\n"
        "Some prose here.\n"
        "<!-- /MANUAL -->\n"
        "\n"
        "<!-- MANUAL: POST_/api/context/build -->\n"
        "Other prose.\n"
        "<!-- /MANUAL -->\n",
        encoding="utf-8",
    )
    notes = extract_manual_notes(existing)
    assert notes["GET_/api/novels"] == "Some prose here."
    assert notes["POST_/api/context/build"] == "Other prose."


def test_extract_skips_empty_placeholder_blocks(tmp_path):
    """The empty placeholder emitted by the template for endpoints with no
    notes must NOT be re-injected as content on the next render — otherwise
    a no-op regeneration would propagate empty blocks forever."""
    from render_spec import extract_manual_notes
    existing = tmp_path / "spec.md"
    existing.write_text(
        "<!-- MANUAL: GET_/api/novels -->\n"
        "Real prose that must be preserved.\n"
        "<!-- /MANUAL -->\n"
        "\n"
        "<!-- MANUAL: POST_/api/context/build -->\n"
        "<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->\n"
        "<!-- /MANUAL -->\n",
        encoding="utf-8",
    )
    notes = extract_manual_notes(existing)
    assert "GET_/api/novels" in notes
    assert "POST_/api/context/build" not in notes  # placeholder skipped


def test_render_preserves_existing_manual_notes(tmp_path):
    """End-to-end: render with old spec.md present → manual notes survive."""
    from render_spec import render_spec, extract_manual_notes
    old = tmp_path / "spec.md"
    old.write_text(
        "<!-- MANUAL: GET_/api/novels -->\n"
        "Pre-existing prose that must survive regeneration.\n"
        "<!-- /MANUAL -->\n",
        encoding="utf-8",
    )
    notes = extract_manual_notes(old)
    out = render_spec(FIXTURE_INV, TEMPLATE, manual_notes=notes)
    assert "Pre-existing prose that must survive regeneration." in out
