"""
DEPRECATED: Use init_unified_db.py instead.
This file is kept for backward compatibility only.
In v3.3+, config tables are created by ensure_unified_schema() and
seeded by repository.init_config_seed().
"""
import sys
import os

PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PORTAL_DIR)

if __name__ == "__main__":
    from db import ensure_unified_schema
    from repository import get_repo
    ensure_unified_schema()
    get_repo().init_config_seed()
    print("Config DB initialized via unified schema.")
else:
    # When imported, check if we're in MySQL mode
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("mysql"):
        # MySQL mode: do nothing, tables are managed by ORM
        pass
    else:
        # SQLite mode: legacy behavior
        try:
            from db import ensure_unified_schema
            from repository import get_repo
            ensure_unified_schema()
            get_repo().init_config_seed()
        except Exception:
            pass  # Silently fail if not ready
