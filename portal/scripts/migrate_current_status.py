#!/usr/bin/env python3
"""Migrate `novels/{name}/state/current_status.md` into the `current_status` table.

For each novel that has a state/current_status.md file but NO row in
current_status, this script:
  1. Reads the .md content
  2. Pulls out the easy structured fields (current_volume, current_chapter,
     total_word_count) by regex
  3. Stores the whole text in `raw_md`
  4. Inserts the row

The file is renamed to .md.migrated (NOT deleted) so the migration is
reversible and the user can re-import or audit later.

Usage:
    python portal/scripts/migrate_current_status.py              # migrate all novels
    python portal/scripts/migrate_current_status.py --novel X    # migrate one
    python portal/scripts/migrate_current_status.py --reset-to 1:1  # after migrate, reset target to vol-1 ch-1
"""
import argparse
import os
import re
import sys
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PORTAL_DIR))

from db import ensure_unified_schema  # noqa: E402
from repository import get_repo  # noqa: E402


def _extract_structured(md: str) -> dict:
    """Pull a few easy structured fields from the .md prose.

    The legacy .md format is hand-written free-form (e.g.
    "**已完结章节**：312 章 / 计划总章节 500 章"). The regexes here are
    best-effort — anything that can't be extracted stays in raw_md and
    the LLM parses the prose at render time.
    """
    fields: dict = {}
    # The legacy .md uses `**` markdown bolding around field names, so
    # the regexes tolerate the `**` prefix/suffix.
    m = re.search(r"已完结章节\*\*?[：:]\s*(\d+)\s*章", md)
    if m:
        fields["current_chapter"] = int(m.group(1))
    m = re.search(r"总字数\*\*?[：:]\s*约?\s*([\d.]+)\s*万", md)
    if m:
        # 48.6 万字 → 486000 chars
        fields["total_word_count"] = int(float(m.group(1)) * 10_000)
    m = re.search(r"最新章节\*\*?[：:]\s*第\s*(\d+)\s*章", md)
    if m:
        # The "最新章节" line gives the most recent chapter number
        fields["current_chapter"] = int(m.group(1))
    # Volume uses Chinese numerals (e.g. "第二卷") in many project files;
    # `\d` in Python's re only matches ASCII [0-9], so include the
    # common Chinese digits explicitly. Then convert Chinese → int via
    # the small lookup below.
    cn_digits = "零一二三四五六七八九十百千万〇"
    m = re.search(rf"第\s*([0-9{cn_digits}]+)\s*卷", md)
    if m:
        raw = m.group(1)
        try:
            fields.setdefault("current_volume", _chinese_or_arabic_to_int(raw))
        except ValueError:
            pass
    return fields


def _chinese_or_arabic_to_int(s: str) -> int:
    """Convert a Chinese or Arabic numeral string to int (1-99 range).

    Supports both forms because project files use whichever the author
    happened to type. Examples: "2" → 2, "十二" → 12, "二十三" → 23,
    "九" → 9. Volumes rarely exceed single digits, so the tens parser
    is enough; hundreds/thousands raise ValueError and the caller
    silently leaves the field unset (the prose in raw_md carries the
    human-readable form).
    """
    if s.isdigit():
        return int(s)
    digit_map = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3,
                 "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if s in digit_map:
        return digit_map[s]
    if "十" not in s:
        raise ValueError(f"unparseable numeral: {s!r}")
    if s.startswith("十"):
        rest = s[1:]
        tens = 1
    elif s.endswith("十"):
        tens = digit_map[s[0]]
        rest = ""
    else:
        parts = s.split("十")
        if len(parts) != 2:
            raise ValueError(f"compound numeral too complex for v1: {s!r}")
        if parts[0] not in digit_map or parts[1] not in digit_map:
            raise ValueError(f"unknown digit in {s!r}")
        tens = digit_map[parts[0]]
        rest = parts[1]
    ones = digit_map[rest] if rest else 0
    return tens * 10 + ones


def migrate_one(novel_name: str, repo, novels_root: Path) -> str:
    """Migrate one novel. Returns 'migrated' / 'skipped' / 'no-file'."""
    file_path = novels_root / novel_name / "state" / "current_status.md"
    if not file_path.exists():
        return "no-file"
    if repo.get_current_status(novel_name) is not None:
        return "skipped"  # already migrated

    md = file_path.read_text(encoding="utf-8").strip()
    fields = _extract_structured(md)
    fields["raw_md"] = md
    repo.upsert_current_status(novel_name, **fields)

    # Rename file to .md.migrated — keeps audit trail, prevents double-import
    backup = file_path.with_suffix(".md.migrated")
    file_path.rename(backup)
    return "migrated"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--novel", help="migrate a single novel (default: all)")
    parser.add_argument(
        "--reset-to",
        metavar="VOL:CH",
        help="after migration, set target override to VOL:CH (e.g. 1:1)",
    )
    parser.add_argument(
        "--novels-root",
        default=str(PORTAL_DIR.parent / "novels"),
        help="path to novels/ directory",
    )
    args = parser.parse_args()

    ensure_unified_schema()
    repo = get_repo()
    novels_root = Path(args.novels_root)

    targets = [args.novel] if args.novel else sorted(
        d.name for d in novels_root.iterdir() if d.is_dir()
    )

    print(f"Migrating current_status.md → current_status table for {len(targets)} novel(s)")
    for name in targets:
        result = migrate_one(name, repo, novels_root)
        suffix = ""
        if args.reset_to and result == "migrated":
            try:
                v, ch = args.reset_to.split(":")
                repo.reset_current_status(name, int(v), int(ch))
                suffix = f" + reset target to vol-{v} ch-{ch}"
            except ValueError:
                print(f"  ⚠️ invalid --reset-to value: {args.reset_to!r}, expected VOL:CH")
        print(f"  {name}: {result}{suffix}")


if __name__ == "__main__":
    main()
