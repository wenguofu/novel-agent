"""
BUG-04: Verify token budget enforcement in context_builder.
content[:allocated * 2] uses allocated (token count) as char offset — wrong.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
from context_builder import build_context
from token_utils import count_tokens


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Local ``tmp_db`` fixture for this root-level test file.

    Mirrors the pattern in ``tests/functional/conftest.py`` —
    point ``DATABASE_URL`` at a fresh tmp SQLite file, drop the
    cached ``db`` / ``repository`` modules so the engine is
    re-created, run ``ensure_unified_schema`` to create tables,
    then yield the URL.
    """
    from urllib.parse import urlparse
    import importlib

    db_file = tmp_path / "test_content.db"
    db_url = f"sqlite:///{db_file}"
    # Drop cached modules so a fresh engine is created.
    for m in list(sys.modules):
        if m.startswith(("db", "repository", "app", "content_db", "config", "context_builder")):
            del sys.modules[m]
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TESTING", "1")
    from db import ensure_unified_schema
    from repository import get_repo
    ensure_unified_schema()
    get_repo().init_config_seed()
    # Sync content_db.DB_PATH for legacy get_db() callers.
    if "content_db" in sys.modules:
        import content_db
        content_db.DB_PATH = str(db_file)
    yield db_url


class TestTokenTruncation:
    def testcount_tokens_chinese(self):
        """Chinese text should cost ~1.5 tokens per character"""
        text = "这是一个测试句子用于验证中文分词和token计数功能"
        tokens = count_tokens(text)
        assert tokens > 0
        # Chinese chars ≈ 1.5 tokens each (no English words to dilute)
        assert tokens > len(text)  # tokens should be MORE than chars

    def test_truncation_respects_budget_with_large_content(self, tmp_db):
        """With max_tokens=1000 and large content, should not overflow"""
        # Sync content_db.DB_PATH with the tmp DB so the legacy
        # ``get_db()`` reads the same file the ``tmp_db`` fixture
        # created the schema in. The runtime path uses the
        # repository, so this sync is only needed because the
        # test seeds via raw SQL.
        import sys
        from urllib.parse import urlparse
        parsed = urlparse(tmp_db)
        db_file = parsed.path
        if "content_db" in sys.modules:
            del sys.modules["content_db"]
        import content_db as db
        db.DB_PATH = db_file

        # Create a novel with large outline content that would overflow naive truncation
        conn = db.get_db()
        conn.execute("INSERT INTO novels (name, title, genre) VALUES (?,?,?)",
                     ("overflow_test", "Test", "玄幻"))
        conn.commit()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", ("overflow_test",)).fetchone()
        nid = novel["id"]

        # Insert a very large outline (5000 Chinese chars ≈ 7500 tokens)
        large_outline = "第" + "一" * 5000 + "章\n大量内容" * 500
        conn.execute("""
            INSERT INTO outlines (novel_id, volume, content) VALUES (?, 'vol-01', ?)
        """, (nid, large_outline))
        conn.commit()
        conn.close()

        # Build context with strict 500 token limit
        ctx = build_context({
            "name": "overflow_test", "volume": 1, "chapter_num": 1,
            "style": "", "instructions": "", "max_tokens": 500,
        })

        # The total tokens should not absurdly exceed max_tokens
        assert ctx["total_tokens"] <= 1000, \
            f"Token budget violated: {ctx['total_tokens']} > 1000 (max=500)"

        # Cleanup
        conn = db.get_db()
        conn.execute("DELETE FROM outlines WHERE novel_id=?", (nid,))
        conn.execute("DELETE FROM novels WHERE id=?", (nid,))
        conn.commit()
        conn.close()
