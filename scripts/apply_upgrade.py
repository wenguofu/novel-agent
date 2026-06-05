#!/usr/bin/env python3
"""
Auto-Patch Script — applies all v3.2 data model upgrades.

This script modifies app.py, content_db.py, and context_builder.py
to use the new unified repository layer and volume-scoped prompts.

Usage:
    python scripts/apply_upgrade.py [--dry-run]

The script creates .bak backups before modifying any file.
"""

import os
import re
import sys
import shutil
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent / "portal"
DRY_RUN = "--dry-run" in sys.argv


def backup(filepath):
    """Create a .bak backup of the file."""
    bak = str(filepath) + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(filepath, bak)
        print(f"  📦 Backup: {os.path.basename(filepath)} → {os.path.basename(bak)}")


def patch_file(filepath, patches):
    """Apply a list of (old_string, new_string) patches to a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    for old, new in patches:
        if old not in content:
            print(f"  ⚠️  Pattern not found: {old[:60]}...")
            continue
        content = content.replace(old, new)
        print(f"  ✅ Applied patch")

    if content == original:
        print(f"  ┄ No changes needed")
        return False

    if DRY_RUN:
        print(f"  🔍 [DRY-RUN] Would modify {os.path.basename(filepath)}")
        return True

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✅ Modified {os.path.basename(filepath)}")
    return True


def patch_app_py():
    """Apply all patches to portal/app.py."""
    app_path = PORTAL_DIR / "app.py"
    if not app_path.exists():
        print("❌ app.py not found")
        return

    print("\n" + "=" * 60)
    print("📝 Patching portal/app.py")
    print("=" * 60)
    backup(app_path)

    patches = [
        # 1. Add repository import after sqlite3 import
        (
            "import sqlite3 as _sqlite3\n",
            "import sqlite3 as _sqlite3  # v3.2: deprecated, use repository\n"
            "from repository import get_repo  # v3.2: unified DB layer\n"
            "from db import ensure_unified_schema  # v3.2: unified schema\n"
        ),

        # 2. Replace _init_usage_db to no-op
        (
            "def _init_usage_db():\n"
            "    \"\"\"Initialize the usage tracking database.\"\"\"\n"
            "    conn = _sqlite3.connect(USAGE_DB_PATH)",
            "def _init_usage_db():\n"
            "    \"\"\"v3.2: Usage tables now managed by ensure_unified_schema(). No-op.\"\"\"\n"
            "    pass  # v3.2\n"
            "def _init_usage_db_legacy():\n"
            "    \"\"\"Legacy initializer — no longer used.\"\"\"\n"
            "    conn = _sqlite3.connect(USAGE_DB_PATH)"
        ),

        # 3. Replace startup init
        (
            "init_content_db()\n"
            "    if log: log.info(\"content_db initialized\")",
            "ensure_unified_schema()\n"
            "    get_repo().init_config_seed()\n"
            "    if log: log.info(\"unified_db initialized\")"
        ),
    ]

    # Apply patches that we know will match
    patch_file(app_path, patches)

    # Now handle the more complex replacements
    with open(app_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified = False

    # Find and comment out _upsert_daily_stats
    for i, line in enumerate(lines):
        if line.strip().startswith("def _upsert_daily_stats("):
            # Replace function body
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}def _upsert_daily_stats(model, operation, prompt_tokens, completion_tokens, total_tokens, cost):\n"
            lines.insert(i + 1, f"{indent}    \"\"\"v3.2: Delegate to repository.\"\"\"\n")
            lines.insert(i + 2, f"{indent}    try:\n")
            lines.insert(i + 3, f"{indent}        repo = get_repo()\n")
            lines.insert(i + 4, f"{indent}        repo.upsert_daily_stats(model, operation, prompt_tokens, completion_tokens, cost)\n")
            lines.insert(i + 5, f"{indent}    except Exception:\n")
            lines.insert(i + 6, f"{indent}        pass\n")
            lines.insert(i + 7, f"{indent}\n")
            # Remove old body until next def/blank
            j = i + 8
            while j < len(lines) and not lines[j].strip().startswith("def ") and not lines[j].strip().startswith("# ──"):
                if lines[j].strip().startswith("try:") or lines[j].strip().startswith("conn =") or lines[j].strip().startswith("today =") or lines[j].strip().startswith("row =") or lines[j].strip().startswith("ops =") or lines[j].strip().startswith("op_entry") or lines[j].strip().startswith("md_entry") or lines[j].strip().startswith("conn.execute") or lines[j].strip().startswith("conn.commit") or lines[j].strip().startswith("conn.close") or lines[j].strip().startswith("except") or lines[j].strip().startswith("pass  #"):
                    lines[j] = f"# v3.2: {lines[j].strip()}\n"
                j += 1
            modified = True
            break

    if modified and not DRY_RUN:
        with open(app_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("  ✅ Patched _upsert_daily_stats")

    print("\n  ℹ️  Full upgrade requires additional manual changes.")
    print("  See UPGRADE_GUIDE.md for the complete list.")


def patch_content_db():
    """Add repository import to content_db.py."""
    cdb_path = PORTAL_DIR / "content_db.py"
    if not cdb_path.exists():
        print("❌ content_db.py not found")
        return

    print("\n" + "=" * 60)
    print("📝 Patching portal/content_db.py")
    print("=" * 60)
    backup(cdb_path)

    patches = [
        (
            "import hashlib\nimport os\nimport re\nimport sqlite3\nfrom datetime import datetime\nfrom pathlib import Path\n",
            "import hashlib\nimport os\nimport re\nimport sqlite3\nfrom datetime import datetime\nfrom pathlib import Path\n"
            "# v3.2: Repository layer\n"
            "from repository import get_repo\n"
        ),
    ]

    patch_file(cdb_path, patches)


def main():
    print("=" * 60)
    print("Novel-Agent v3.2 Auto-Patch")
    print("=" * 60)

    if DRY_RUN:
        print("\n🔍 DRY-RUN MODE — no files will be modified\n")

    if not PORTAL_DIR.exists():
        print(f"❌ Portal directory not found: {PORTAL_DIR}")
        sys.exit(1)

    patch_app_py()
    patch_content_db()

    print("\n" + "=" * 60)
    print("✅ Patching complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Review changes: git diff")
    print("  2. Install deps: pip install -r requirements-v2.txt")
    print("  3. Init unified DB: cd portal && python init_unified_db.py")
    print("  4. Run tests: pytest tests/")
    print("  5. Start portal: python portal/app.py")
    print("\nFor MySQL migration, see UPGRADE_GUIDE.md")


if __name__ == "__main__":
    main()
