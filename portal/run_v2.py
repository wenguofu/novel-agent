#!/usr/bin/env python3
"""
Novel-Agent v3.4 Launcher — MySQL only.

Drop-in replacement for ``python app.py``.

Usage:
    export DATABASE_URL='mysql+pymysql://user:pass@host:3306/novel_agent'
    python run_v2.py

The portal refuses to start without a MySQL ``DATABASE_URL`` (see
``portal/db.py::validate_database_url``). The launcher does not set a
default — operators must configure ``DATABASE_URL`` explicitly.

Architecture (post-SQLite-removal):
  - ``db.py`` — MySQL-only SQLAlchemy engine, connection pool, schema sync
  - ``models_orm.py`` — 26 ORM models, source of truth for the schema
  - ``repository.py`` — repository pattern with dict-based API, 110+ methods
  - ``app.py`` — Flask routes; all DB access goes through the repository
  - ``context_builder.py`` — canonical 12-layer prompt assembly
  - ``content_db.py`` — backward-compat shim (legacy functions only)
"""

import os
import sys
import logging

PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PORTAL_DIR)

logging.basicConfig(level=logging.INFO, format='%(levelname)s [%(name)s] %(message)s')
log = logging.getLogger("run_v2")

log.info("=" * 60)
log.info("Novel-Agent v3.4 — MySQL Backend")
log.info("=" * 60)

# ═══════════════════════════════════════════════════════════════════════
# Step 1: Validate DATABASE_URL (MySQL only)
# ═══════════════════════════════════════════════════════════════════════

db_url = os.environ.get("DATABASE_URL", "")
if not db_url or not db_url.startswith("mysql"):
    log.error(
        "DATABASE_URL must be set to a MySQL URL like "
        "'mysql+pymysql://user:pass@host:3306/novel_agent'. "
        f"Got: {db_url!r}"
    )
    sys.exit(1)
log.info(f"DB: MySQL ({db_url.split('@')[-1] if '@' in db_url else db_url})")

# ═══════════════════════════════════════════════════════════════════════
# Step 2: Initialize schema (idempotent — CREATE TABLE IF NOT EXISTS)
# ═══════════════════════════════════════════════════════════════════════

from db import ensure_unified_schema, get_engine
from sqlalchemy import inspect

ensure_unified_schema()
try:
    tables = inspect(get_engine()).get_table_names()
    log.info(f"Schema: {len(tables)} tables ready")
except Exception as e:
    log.warning(f"Table-name inspection skipped: {e}")

# ═══════════════════════════════════════════════════════════════════════
# Step 3: Seed config data
# ═══════════════════════════════════════════════════════════════════════

from repository import get_repo
repo = get_repo()
repo.init_config_seed()
log.info("Config seed data verified")

# ═══════════════════════════════════════════════════════════════════════
# Step 4: Start the Flask app
# ═══════════════════════════════════════════════════════════════════════

import app as _app

log.info("=" * 60)
log.info("All systems ready. Engine: MySQL")
log.info("Features: unified-DB | repo-layer | volume-scoped prompts")
log.info("=" * 60)

if __name__ == "__main__":
    _app.app.run(
        host=_app.PORTAL_HOST,
        port=_app.PORTAL_PORT,
        debug=_app.DEBUG,
    )
