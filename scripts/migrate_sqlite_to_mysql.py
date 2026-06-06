#!/usr/bin/env python3
"""
SQLite → MySQL Data Migration Script

Exports all data from SQLite databases (content.db, config.db, usage.db)
and imports into MySQL via SQLAlchemy.

Usage:
    # Set MySQL connection
    export DATABASE_URL="mysql+pymysql://user:pass@localhost:3306/novel_agent"

    # Dry run (validate only)
    python migrate_sqlite_to_mysql.py --dry-run

    # Full migration
    python migrate_sqlite_to_mysql.py

    # Export only (to JSON files)
    python migrate_sqlite_to_mysql.py --export-only --export-dir ./backup
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add portal to path
PORTAL_DIR = Path(__file__).resolve().parent.parent / "portal"
sys.path.insert(0, str(PORTAL_DIR))


def get_sqlite_data():
    """Export all data from the 3 SQLite databases as a dict of table→rows."""
    import sqlite3

    portal_dir = str(PORTAL_DIR)
    dbs = {
        "content.db": [
            "novels", "outlines", "chapters", "reviews", "danger_issues",
            "foreshadowing", "characters", "character_events", "world_building",
            "plot_arcs", "pacing_control", "revelation_schedule", "genre_rules",
            "story_volumes", "volume_plans", "alias_names", "project_meta",
        ],
        "config.db": [
            "banned_words", "compliance_rules", "alias_registry",
            "style_presets", "deepseek_config",
        ],
        "usage.db": [
            "usage", "daily_stats",
        ],
    }

    all_data = {}
    for db_name, tables in dbs.items():
        db_path = os.path.join(portal_dir, db_name)
        if not os.path.exists(db_path):
            print(f"  ⚠️  {db_name} not found, skipping")
            continue

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        for table in tables:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                if rows:
                    all_data[table] = [dict(r) for r in rows]
                    print(f"  ✅ {db_name}:{table} — {len(rows)} rows")
                else:
                    print(f"  ┄ {db_name}:{table} — empty")
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  {db_name}:{table} — {e}")

        conn.close()

    return all_data


def export_to_json(data, export_dir):
    """Export data to JSON files (one per table)."""
    os.makedirs(export_dir, exist_ok=True)
    for table, rows in data.items():
        fpath = os.path.join(export_dir, f"{table}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
        print(f"  📄 {fpath} ({len(rows)} rows)")
    print(f"\n✅ Exported {len(data)} tables to {export_dir}")


def import_to_mysql(data):
    """Import data into MySQL via SQLAlchemy ORM."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or db_url.startswith("sqlite"):
        print("❌ DATABASE_URL must be set to a MySQL URL")
        print("   Example: export DATABASE_URL='mysql+pymysql://user:pass@localhost:3306/novel_agent'")
        sys.exit(1)

    print(f"\n🔗 Connecting to MySQL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    engine = create_engine(db_url, pool_pre_ping=True)

    # Create all tables
    from models_orm import Base
    Base.metadata.create_all(engine)
    print("✅ Tables created")

    Session = sessionmaker(bind=engine)

    # Import order respects FK dependencies
    import_order = [
        # content.db tables
        "novels", "outlines", "chapters", "reviews", "danger_issues",
        "foreshadowing", "characters", "character_events", "world_building",
        "plot_arcs", "pacing_control", "revelation_schedule", "genre_rules",
        "story_volumes", "volume_plans", "alias_names", "project_meta",
        # config.db tables (no FK to novels)
        "banned_words", "compliance_rules", "alias_registry",
        "style_presets", "deepseek_config",
        # usage.db tables (no FK)
        "usage", "daily_stats",
    ]

    # Map table name to model class
    from models_orm import (
        Novel, Outline, Chapter, Review, DangerIssue,
        Foreshadowing, Character, CharacterEvent, WorldBuilding,
        PlotArc, PacingControl, RevelationSchedule, GenreRule,
        StoryVolume, VolumePlan, AliasName, ProjectMeta,
        BannedWord, ComplianceRule, AliasRegistry, StylePreset, DeepSeekConfig,
        UsageRecord, DailyStat,
    )

    model_map = {
        "novels": Novel, "outlines": Outline, "chapters": Chapter,
        "reviews": Review, "danger_issues": DangerIssue,
        "foreshadowing": Foreshadowing, "characters": Character,
        "character_events": CharacterEvent, "world_building": WorldBuilding,
        "plot_arcs": PlotArc, "pacing_control": PacingControl,
        "revelation_schedule": RevelationSchedule,
        "genre_rules": GenreRule, "story_volumes": StoryVolume,
        "volume_plans": VolumePlan, "alias_names": AliasName,
        "project_meta": ProjectMeta,
        "banned_words": BannedWord, "compliance_rules": ComplianceRule,
        "alias_registry": AliasRegistry, "style_presets": StylePreset,
        "deepseek_config": DeepSeekConfig,
        "usage": UsageRecord, "daily_stats": DailyStat,
    }

    total_imported = 0
    session = Session()
    try:
        for table in import_order:
            if table not in data:
                continue
            model = model_map.get(table)
            if not model:
                print(f"  ⚠️  No model for table: {table}")
                continue

            rows = data[table]
            count = 0
            for row in rows:
                # Remove 'id' to let MySQL auto-increment
                row_copy = {k: v for k, v in row.items() if k != "id"}
                try:
                    obj = model(**row_copy)
                    session.add(obj)
                    count += 1
                except Exception as e:
                    print(f"  ⚠️  {table} row error: {e}")
                    continue

            session.flush()
            total_imported += count
            print(f"  ✅ {table}: {count}/{len(rows)} rows imported")

        session.commit()
        print(f"\n🎉 Import complete: {total_imported} total rows imported to MySQL")
    except Exception as e:
        session.rollback()
        print(f"\n❌ Import failed: {e}")
        raise
    finally:
        session.close()


def validate_migration(data):
    """Validate data before migration (row counts, constraint checks)."""
    issues = []

    # Check FK integrity: all novel_ids in child tables must exist in novels
    novel_names = {r["name"] for r in data.get("novels", [])}
    novel_ids = {r["id"] for r in data.get("novels", [])}

    for table in data:
        if table == "novels":
            continue
        for row in data[table]:
            nid = row.get("novel_id")
            if nid is not None and nid not in novel_ids:
                issues.append(f"FK violation: {table}.novel_id={nid} not in novels")

    # Check unique constraints
    if "outlines" in data:
        seen = set()
        for r in data["outlines"]:
            key = (r["novel_id"], r["volume"])
            if key in seen:
                issues.append(f"Duplicate outline: novel_id={key[0]}, volume={key[1]}")
            seen.add(key)

    if "chapters" in data:
        seen = set()
        for r in data["chapters"]:
            key = (r["novel_id"], r["chapter_ref"])
            if key in seen:
                issues.append(f"Duplicate chapter: novel_id={key[0]}, chapter_ref={key[1]}")
            seen.add(key)

    if issues:
        print("\n⚠️  Validation issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ Validation passed — no issues found")

    return issues


def main():
    parser = argparse.ArgumentParser(description="SQLite → MySQL Migration")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no import")
    parser.add_argument("--export-only", action="store_true", help="Export to JSON only")
    parser.add_argument("--export-dir", default="./migration_backup", help="Export directory")
    parser.add_argument("--skip-validate", action="store_true", help="Skip validation")
    args = parser.parse_args()

    print("=" * 60)
    print("SQLite → MySQL Data Migration")
    print("=" * 60)

    # Step 1: Export from SQLite
    print("\n📤 Step 1: Exporting SQLite data...")
    data = get_sqlite_data()

    total_rows = sum(len(v) for v in data.values())
    print(f"\n📊 Total: {len(data)} tables, {total_rows} rows")

    # Step 2: Validate
    if not args.skip_validate:
        print("\n🔍 Step 2: Validating data...")
        issues = validate_migration(data)
        if issues and not args.dry_run:
            print("\n❌ Fix validation issues before migration, or use --skip-validate")
            sys.exit(1)

    # Step 3: Export or Import
    if args.export_only or args.dry_run:
        print(f"\n📄 Step 3: Exporting to JSON ({'dry-run' if args.dry_run else 'export'})...")
        export_to_json(data, args.export_dir)
        if args.dry_run:
            print("\n✅ Dry run complete. No data imported to MySQL.")
    else:
        print("\n📥 Step 3: Importing to MySQL...")
        import_to_mysql(data)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
