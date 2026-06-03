#!/usr/bin/env python3
"""Render docs/system-functional-spec.md from docs/auto-inventory.json.

Reads the Jinja2 template, the JSON manifest, and (optionally) an existing
spec.md's Manual Notes blocks. Preserves manual notes across regenerations.
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    print("jinja2 is required: pip install jinja2", file=sys.stderr)
    sys.exit(1)


MANUAL_BLOCK = re.compile(
    r"<!-- MANUAL: ([^\s]+) -->\n(.*?)<!-- /MANUAL -->",
    re.DOTALL,
)
# Marker emitted by the template for the empty placeholder. If a block's body
# is just this comment (possibly with surrounding whitespace), it is NOT
# real content and should not be preserved across regenerations.
EMPTY_PLACEHOLDER_MARKER = "(no manual notes yet"


def extract_manual_notes(spec_path: Path) -> Dict[str, str]:
    """Read spec.md and return {key: body} for every non-empty Manual Notes block.

    Blocks whose body is just the auto-generated empty placeholder (matches
    EMPTY_PLACEHOLDER_MARKER) are omitted. Whitespace-only bodies are also
    omitted.
    """
    if not spec_path.exists():
        return {}
    text = spec_path.read_text(encoding="utf-8")
    notes: Dict[str, str] = {}
    for match in MANUAL_BLOCK.finditer(text):
        key = match.group(1)
        body = match.group(2).rstrip()
        stripped = body.strip()
        if not stripped or EMPTY_PLACEHOLDER_MARKER in stripped:
            continue
        notes[key] = body
    return notes


def render_spec(manifest_path: Path, template_path: Path, manual_notes: Dict[str, str]) -> str:
    """Render the spec to a string. Does NOT write to disk.

    `manual_notes` is {endpoint_key: prose_string}. The template's
    `{% if ep.key in manual_notes %}` branch substitutes the prose into the
    Manual Notes block. Endpoints without notes get the empty placeholder.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)
    return template.render(
        generated_at=manifest["generated_at"],
        endpoint_count=manifest["endpoint_count"],
        endpoints=manifest["endpoints"],
        repo_index=manifest.get("repository_index", {}),
        repo_index_size=manifest.get("repository_index_size", 0),
        manual_notes=manual_notes,
    )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--inventory", type=Path, default=Path("docs/auto-inventory.json"))
    parser.add_argument("--template", type=Path, default=Path("docs/system-functional-spec.j2.md"))
    parser.add_argument("--out", type=Path, default=Path("docs/system-functional-spec.md"))
    parser.add_argument("--existing", type=Path, default=None,
                        help="Path to existing spec.md to preserve Manual Notes from "
                             "(default: same as --out, so the first render of an existing "
                             "spec preserves its notes)")
    args = parser.parse_args()
    existing = args.existing if args.existing is not None else args.out
    notes = extract_manual_notes(existing)
    rendered = render_spec(args.inventory, args.template, notes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"Rendered {args.out} ({len(notes)} manual notes preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
