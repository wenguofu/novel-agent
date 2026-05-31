#!/usr/bin/env python3
"""
Unified Database Initializer — replaces init_config_db.py.

Creates all tables (content + config + usage) in the primary database,
and seeds config tables with default data.

Usage:
    python init_unified_db.py
"""

import os
import sys
from pathlib import Path

# Ensure portal directory is in path
PORTAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PORTAL_DIR))

from db import get_engine, ensure_unified_schema
from repository import get_repo


def init():
    """Initialize unified database: create tables + seed config data."""
    print("=" * 60)
    print("Novel-Agent Unified DB Initializer")
    print("=" * 60)

    # Step 1: Create all tables
    print("\n📊 Step 1: Creating tables...")
    engine = get_engine()
    from models_orm import Base
    Base.metadata.create_all(engine)

    # Show created tables
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"   ✅ {len(tables)} tables created: {', '.join(sorted(tables))}")

    # Step 2: Migrate data from side DBs (config.db, usage.db) if they exist
    print("\n📦 Step 2: Migrating data from legacy side DBs...")
    ensure_unified_schema()

    # Step 3: Seed config tables with default data
    print("\n🌱 Step 3: Seeding default config data...")
    repo = get_repo()
    repo.init_config_seed()
    print("   ✅ Default config data seeded (banned words, compliance rules, style presets)")

    # Step 4: Verify
    print("\n🔍 Step 4: Verification...")
    try:
        novels = repo.list_novels()
        print(f"   ✅ Novels: {len(novels)}")
        banned = repo.list_banned_words()
        print(f"   ✅ Banned words: {len(banned)}")
        styles = repo.list_style_presets()
        print(f"   ✅ Style presets: {len(styles)}")
    except Exception as e:
        print(f"   ⚠️  Verification warning: {e}")

    print("\n✅ Database initialization complete!")
    print(f"   Database: {str(engine.url).split('@')[-1] if '@' in str(engine.url) else str(engine.url)}")


if __name__ == "__main__":
    init()
