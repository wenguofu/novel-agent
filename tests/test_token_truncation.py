"""
BUG-04: Verify token budget enforcement in context_builder.
content[:allocated * 2] uses allocated (token count) as char offset — wrong.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
from context_builder import build_context, _count_tokens

class TestTokenTruncation:
    def test_count_tokens_chinese(self):
        """Chinese text should cost ~1.5 tokens per character"""
        text = "这是一个测试句子用于验证中文分词和token计数功能"
        tokens = _count_tokens(text)
        assert tokens > 0
        # Chinese chars ≈ 1.5 tokens each (no English words to dilute)
        assert tokens > len(text)  # tokens should be MORE than chars

    def test_truncation_respects_budget_with_large_content(self):
        """With max_tokens=1000 and large content, should not overflow"""
        # Create a novel with large outline content that would overflow naive truncation
        import content_db as db
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
