#!/usr/bin/env python3
"""
Verification script for v3.2 data model upgrade.

Tests that all new components work correctly with the existing SQLite data.
Run this AFTER applying the patches from UPGRADE_GUIDE.md.

Usage:
    cd portal && python ../scripts/verify_upgrade.py
"""

import os
import sys
from pathlib import Path

PORTAL_DIR = Path(__file__).resolve().parent.parent / "portal"
sys.path.insert(0, str(PORTAL_DIR))


def test_orm_models():
    """Verify all ORM models can be imported and have correct table names."""
    print("\n📋 Test 1: ORM Models")
    from models_orm import (
        Novel, Outline, Chapter, Review, DangerIssue,
        Foreshadowing, Character, CharacterEvent, WorldBuilding,
        PlotArc, PacingControl, RevelationSchedule, GenreRule,
        StoryVolume, VolumePlan, AliasName, ProjectMeta,
        BannedWord, ComplianceRule, AliasRegistry, StylePreset, DeepSeekConfig,
        UsageRecord, DailyStat, Base,
    )

    models = [
        ("novels", Novel), ("outlines", Outline), ("chapters", Chapter),
        ("reviews", Review), ("danger_issues", DangerIssue),
        ("foreshadowing", Foreshadowing), ("characters", Character),
        ("character_events", CharacterEvent), ("world_building", WorldBuilding),
        ("plot_arcs", PlotArc), ("pacing_control", PacingControl),
        ("revelation_schedule", RevelationSchedule), ("genre_rules", GenreRule),
        ("story_volumes", StoryVolume), ("volume_plans", VolumePlan),
        ("alias_names", AliasName), ("project_meta", ProjectMeta),
        ("banned_words", BannedWord), ("compliance_rules", ComplianceRule),
        ("alias_registry", AliasRegistry), ("style_presets", StylePreset),
        ("deepseek_config", DeepSeekConfig),
        ("usage", UsageRecord), ("daily_stats", DailyStat),
    ]

    for expected_table, model in models:
        actual = model.__tablename__
        assert actual == expected_table, f"{model.__name__}: expected {expected_table}, got {actual}"
        print(f"  ✅ {model.__name__} → {actual}")

    print(f"  ✅ All {len(models)} models verified")
    return True


def test_repository_basics():
    """Verify repository can initialize and query existing data."""
    print("\n📋 Test 2: Repository Basic Operations")
    from repository import get_repo

    repo = get_repo()

    # List novels (should have existing data)
    novels = repo.list_novels()
    print(f"  ✅ Novels in DB: {len(novels)}")
    for n in novels:
        print(f"     - {n['name']} ({n.get('title', 'N/A')})")

    # List characters for first novel
    if novels:
        name = novels[0]["name"]
        chars = repo.list_characters(name)
        print(f"  ✅ Characters in '{name}': {len(chars)}")
        for c in chars[:5]:
            print(f"     - {c['name']} ({c.get('role', 'N/A')})")

        # Test volume-scoped character query
        active = repo.list_characters_active_in_volume(name, 1)
        print(f"  ✅ Active characters in volume 1: {len(active)}")

        # Test volume-scoped foreshadowing
        fs = repo.get_foreshadowing_for_volume(name, 1)
        print(f"  ✅ Foreshadowing: due_now={len(fs['due_now'])}, "
              f"overdue={len(fs['overdue'])}, recent={len(fs['recent'])}")

        # Test config
        config = repo.load_all_config()
        print(f"  ✅ Config entries: {len(config)}")

        # Test search
        results = repo.search_all("测试", name, limit=3)
        print(f"  ✅ Search results: chapters={len(results['chapters'])}, "
              f"outlines={len(results['outlines'])}, reviews={len(results['reviews'])}")

    return True


def test_unified_schema():
    """Verify ensure_unified_schema creates all tables."""
    print("\n📋 Test 3: Unified Schema")
    from db import get_engine, ensure_unified_schema
    from sqlalchemy import inspect

    engine = get_engine()
    ensure_unified_schema()

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = {"novels", "chapters", "outlines", "reviews", "characters",
                "foreshadowing", "world_building", "banned_words", "style_presets",
                "usage", "daily_stats"}

    missing = expected - set(tables)
    if missing:
        print(f"  ⚠️  Missing tables: {missing}")
    else:
        print(f"  ✅ All expected tables present ({len(tables)} total)")

    for t in sorted(tables):
        print(f"     - {t}")
    return True


def test_alembic_setup():
    """Verify Alembic configuration is valid."""
    print("\n📋 Test 4: Alembic Setup")
    alembic_dir = PORTAL_DIR / "alembic"
    required_files = ["env.py", "script.py.mako", "versions/0001_initial_schema.py"]
    for f in required_files:
        path = alembic_dir / f
        if path.exists():
            print(f"  ✅ {f}")
        else:
            print(f"  ❌ Missing: {f}")
            return False

    ini_path = PORTAL_DIR / "alembic.ini"
    if ini_path.exists():
        print(f"  ✅ alembic.ini")
    else:
        print(f"  ❌ Missing: alembic.ini")
        return False

    return True


def main():
    print("=" * 60)
    print("Novel-Agent v3.2 Upgrade Verification")
    print("=" * 60)

    os.chdir(str(PORTAL_DIR))

    tests = [
        ("ORM Models", test_orm_models),
        ("Unified Schema", test_unified_schema),
        ("Repository Basics", test_repository_basics),
        ("Alembic Setup", test_alembic_setup),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n  ❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    if failed > 0:
        print("\n⚠️  Some tests failed. Review the errors above.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed! The upgrade is ready.")


if __name__ == "__main__":
    main()
