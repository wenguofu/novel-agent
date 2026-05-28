"""
Test reviews table schema completeness for quality reporting.
BUG-01: quality report queries non-existent columns (wc_ok, compliance_ok, etc.)
BUG-02: review INSERT writes to non-existent columns
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
import pytest
import content_db as db

@pytest.fixture
def fresh_db(tmp_path):
    """Isolate each test with its own content.db"""
    db_path = tmp_path / "content.db"
    old_path = db.DB_PATH
    old_novels = db.NOVELS_ROOT
    db.DB_PATH = str(db_path)
    db.NOVELS_ROOT = str(tmp_path)
    db.init_db()
    yield
    db.DB_PATH = old_path
    db.NOVELS_ROOT = old_novels

class TestReviewsTableComplete:
    def test_reviews_has_all_quality_columns(self, fresh_db):
        """BUG-01/02: Verify reviews table has all quality columns"""
        conn = db.get_db()
        conn.execute(
            "INSERT INTO novels (name, title) VALUES (?, ?)",
            ("test_novel", "test")
        )
        conn.commit()
        novel = conn.execute(
            "SELECT id FROM novels WHERE name=?", ("test_novel",)
        ).fetchone()
        nid = novel["id"]

        # Attempt INSERT with all quality columns
        conn.execute("""
            INSERT INTO reviews (novel_id, chapter_ref, ai_review, script_detail,
                wc_ok, compliance_ok, forbidden_ok, bcontrast_count,
                judgment_groups, tell_count, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nid, "vol-01/ch-0001", "test review", "test detail",
              1, 1, 1, 2, 3, 1, 2500))
        conn.commit()

        # Verify columns exist by reading back
        row = conn.execute(
            "SELECT wc_ok, compliance_ok, forbidden_ok, "
            "bcontrast_count, tell_count, judgment_groups "
            "FROM reviews WHERE novel_id=?", (nid,)
        ).fetchone()
        conn.close()

        assert row is not None, "BUG-01: Could not read quality columns"
        assert row["wc_ok"] == 1
        assert row["compliance_ok"] == 1
        assert row["forbidden_ok"] == 1
        assert row["bcontrast_count"] == 2
        assert row["judgment_groups"] == 3
        assert row["tell_count"] == 1

    def test_quality_report_aggregate_queries_work(self, fresh_db):
        """BUG-01: Quality report aggregate queries should work"""
        conn = db.get_db()
        conn.execute(
            "INSERT INTO novels (name, title) VALUES (?, ?)",
            ("test_novel", "test")
        )
        conn.commit()
        novel = conn.execute(
            "SELECT id FROM novels WHERE name=?", ("test_novel",)
        ).fetchone()
        nid = novel["id"]

        # Insert 2 test reviews
        for i, (wc, comp, forb, bc, jg, tell, words) in enumerate([
            (1, 1, 0, 5, 2, 3, 3000),
            (1, 0, 1, 3, 1, 0, 2800),
        ]):
            conn.execute("""
                INSERT INTO reviews (novel_id, chapter_ref, ai_review, script_detail,
                    wc_ok, compliance_ok, forbidden_ok, bcontrast_count,
                    judgment_groups, tell_count, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nid, f"vol-01/ch-000{i+1}", "t", "d",
                  wc, comp, forb, bc, jg, tell, words))
        conn.commit()

        # Replicate actual quality report queries
        total_r = conn.execute(
            "SELECT COUNT(*) as c FROM reviews WHERE novel_id=?", (nid,)
        ).fetchone()["c"]
        wc_pass = conn.execute(
            "SELECT COUNT(*) as c FROM reviews WHERE novel_id=? AND wc_ok=1",
            (nid,)
        ).fetchone()["c"]
        avg_bc = conn.execute(
            "SELECT AVG(bcontrast_count) as v FROM reviews WHERE novel_id=?",
            (nid,)
        ).fetchone()["v"]
        avg_tell = conn.execute(
            "SELECT AVG(tell_count) as v FROM reviews WHERE novel_id=?",
            (nid,)
        ).fetchone()["v"]
        total_jg = conn.execute(
            "SELECT SUM(judgment_groups) as v FROM reviews WHERE novel_id=?",
            (nid,)
        ).fetchone()["v"]
        conn.close()

        assert total_r == 2
        assert wc_pass == 2
        assert avg_bc == 4.0  # (5+3)/2
        assert avg_tell == 1.5  # (3+0)/2
        assert total_jg == 3  # 2+1
