#!/usr/bin/env python3
"""
Novel-Agent v3.3 Launcher — unified DB + repo-based data access.

Drop-in replacement for `python app.py`.

Usage:
    python run_v2.py              # Start portal with SQLite
    DATABASE_URL=mysql+pymysql://user:pass@host:3306/novel_agent python run_v2.py  # MySQL

Architecture:
  - content_db.py → delegates to repository.get_repo() for all DB operations
  - app.py → uses repository for config/usage operations
  - context_builder.py → canonical runtime path (12-layer 2026-06-02 plan)
  - All tables in one database (SQLite or MySQL via DATABASE_URL)
"""

import os
import sys
import logging

PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PORTAL_DIR)

logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
log = logging.getLogger("run_v2")

log.info("=" * 60)
log.info("Novel-Agent v3.3 — Unified DB + Repository Layer")
log.info("=" * 60)

# ═══════════════════════════════════════════════════════════════════════
# Step 1: Set DATABASE_URL
# ═══════════════════════════════════════════════════════════════════════

os.environ.setdefault("DATABASE_URL", f"sqlite:///{PORTAL_DIR}/content.db")
db_url = os.environ["DATABASE_URL"]
engine_type = "MySQL" if db_url.startswith("mysql") else "SQLite"
log.info(f"DB: {engine_type} ({db_url.split('@')[-1] if '@' in db_url else db_url})")

# ═══════════════════════════════════════════════════════════════════════
# Step 2: Initialize unified schema
# ═══════════════════════════════════════════════════════════════════════

from db import ensure_unified_schema, get_engine
from sqlalchemy import inspect

ensure_unified_schema()
tables = inspect(get_engine()).get_table_names()
log.info(f"Unified schema: {len(tables)} tables ready")

# ═══════════════════════════════════════════════════════════════════════
# Step 3: Seed config data
# ═══════════════════════════════════════════════════════════════════════

from repository import get_repo
repo = get_repo()
repo.init_config_seed()
log.info("Config seed data verified")

# ═══════════════════════════════════════════════════════════════════════
# Step 4: Redirect content_db paths for backward compat
# ═══════════════════════════════════════════════════════════════════════

import content_db as _cdb
_unified_db_path = os.path.join(PORTAL_DIR, "content.db")
_cdb.DB_PATH = _unified_db_path

# Patch get_db() to use unified DB path (for SQLite mode)
_original_get_db = _cdb.get_db

def _unified_get_db():
    """get_db() that always uses the unified content.db."""
    if os.environ.get("DATABASE_URL", "").startswith("mysql"):
        # In MySQL mode, content_db already logs a deprecation warning
        return _original_get_db()
    # SQLite mode: ensure unified path
    import sqlite3
    conn = sqlite3.connect(_unified_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

_cdb.get_db = _unified_get_db
log.info("Unified content_db.get_db() → content.db")

# ═══════════════════════════════════════════════════════════════════════
# Step 5: Import app and redirect config/usage paths
# ═══════════════════════════════════════════════════════════════════════

import app as _app

# Redirect old config/usage DB paths to unified content.db
_app.CONFIG_DB_PATH = _unified_db_path
_app.USAGE_DB_PATH = _unified_db_path

# Override app's raw sqlite3 usage functions (safety net if app.py hasn't been updated)
if not os.environ.get("DATABASE_URL", "").startswith("mysql"):
    # SQLite mode: no patching needed, app.py already uses repo where possible
    pass
else:
    # MySQL mode: ensure all raw sqlite3 calls are repo-backed
    def _patched_init_usage_db():
        pass

    def _patched_upsert_daily_stats(model, operation, prompt_tokens, completion_tokens, total_tokens, cost):
        try:
            get_repo().upsert_daily_stats(model, operation, prompt_tokens, completion_tokens, cost)
        except Exception:
            pass

    def _patched_log_token_usage(model, operation, prompt_tokens, completion_tokens, novel=""):
        try:
            cost = 0.0
            try:
                from logging_config import log_token_operation as _lto
                cost = _lto(model, operation, prompt_tokens, completion_tokens, novel=novel)
            except Exception:
                pass
            r = get_repo()
            r.log_usage(model, operation, prompt_tokens, completion_tokens, novel, cost)
            r.upsert_daily_stats(model, operation, prompt_tokens, completion_tokens, cost)
        except Exception:
            pass

    def _patched_db_load_config():
        try:
            return get_repo().load_all_config()
        except Exception:
            return {}

    def _patched_db_save_config(config: dict):
        try:
            r = get_repo()
            for key, value in config.items():
                if value:
                    r.set_config(key, str(value))
        except Exception as e:
            logging.warning(f'[_db_save_config] {e}')

    _app._init_usage_db = _patched_init_usage_db
    _app._upsert_daily_stats = _patched_upsert_daily_stats
    _app.log_token_usage = _patched_log_token_usage
    _app._db_load_config = _patched_db_load_config
    _app._db_save_config = _patched_db_save_config

    log.info("MySQL mode: patched app.py → repository layer")

# ═══════════════════════════════════════════════════════════════════════
# Step 6: Done — start server
# ═══════════════════════════════════════════════════════════════════════

log.info("=" * 60)
log.info(f"All systems ready. Engine: {engine_type}")
log.info("Features: unified-DB | repo-layer | volume-scoped prompts")
log.info("=" * 60)

if __name__ == "__main__":
    _app.app.run(
        host=_app.PORTAL_HOST,
        port=_app.PORTAL_PORT,
        debug=_app.DEBUG,
    )
