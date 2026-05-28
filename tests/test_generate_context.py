"""
BUG-03: Verify generate-chapter uses v3 context builder.
The old api_generate_chapter built prompts inline without pacing/revelation/vector search.
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
import content_db as db
from context_builder import build_context

@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "content.db"
    old_path = db.DB_PATH
    old_novels = db.NOVELS_ROOT
    db.DB_PATH = str(db_path)
    db.NOVELS_ROOT = str(tmp_path)
    db.init_db()
    yield tmp_path
    db.DB_PATH = old_path
    db.NOVELS_ROOT = old_novels

class TestGenerateChapterUsesV3Context:
    def test_build_context_includes_pacing_when_exists(self, fresh_db):
        """When pacing_control has data for a chapter, context includes it"""
        conn = db.get_db()
        conn.execute(
            "INSERT INTO novels (name, title, genre) VALUES (?, ?, ?)",
            ("test_novel", "Test", "玄幻")
        )
        conn.commit()
        novel = conn.execute("SELECT id FROM novels WHERE name=?", ("test_novel",)).fetchone()
        nid = novel["id"]

        # Add pacing for chapter 5
        conn.execute("""
            INSERT INTO pacing_control (novel_id, volume, chapter_start, chapter_end,
                pace_type, intensity, emotion_target)
            VALUES (?, 1, 5, 5, '高潮', 9, '燃')
        """, (nid,))
        conn.commit()
        conn.close()

        ctx = build_context({
            "name": "test_novel", "volume": 1, "chapter_num": 5,
            "style": "", "instructions": "", "max_tokens": 10000,
        })
        assert ctx["system_prompt"], "Should produce system prompt"
        # Pacing should be in the system prompt
        assert "高潮" in ctx["system_prompt"], f"Expected pacing '高潮' in prompt, got: {ctx['system_prompt'][:500]}"
        assert "节奏" in ctx["system_prompt"], f"Expected pacing section in prompt"

    def test_build_context_falls_back_gracefully(self, fresh_db):
        """When no pacing/revelation data, still produces valid prompt"""
        conn = db.get_db()
        conn.execute(
            "INSERT INTO novels (name, title, genre) VALUES (?, ?, ?)",
            ("test_novel2", "Test2", "玄幻")
        )
        conn.commit()
        conn.close()

        ctx = build_context({
            "name": "test_novel2", "volume": 1, "chapter_num": 1,
            "style": "金庸风", "instructions": "写打斗", "max_tokens": 10000,
        })
        assert ctx["system_prompt"], "Should produce system prompt even with minimal data"
        assert ctx["total_tokens"] > 0
        assert ctx["total_tokens"] <= 10000
        # Should have at least core instructions
        assert "网文写作" in ctx["system_prompt"]
