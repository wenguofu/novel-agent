"""Regression tests for api_content_stats (M3.1 hotfix W1).

Bug: ``api_content_stats`` (portal/app.py:3543) does ``if "error" in stats``
where ``stats = get_novel_stats(novel_name)``. When the novel doesn't exist,
``get_novel_stats`` returns ``None``, and the membership test raises
``TypeError`` → HTTP 500.

Fix: null-guard the check.

NOTE — W1 hotfix scope: this file ships only 2 dims (happy + 404-not-found)
as regression coverage for the null-guard fix. The project's 4-dim reference
pattern (``tests/functional/test_chapter_lifecycle.py`` — happy_path_,
missing_field_, not_found_, wrong_method_) is NOT applied here because the
W1 hotfix is regression-only and out-of-scope for the broader 4-dim upgrade.

Full 4-dim coverage for ``/api/content/stats/<novel>`` is deferred to M3.1
W3 (4-dim upgrade for 57 non-core endpoints; Tasks 3.1–3.9 per
``docs/superpowers/plans/2026-06-05-m31-quality-followups.md``). The
canonical home for those tests will remain this file.
"""
import pytest


class TestApiContentStats:
    def test_unknown_novel_returns_404_not_500(self, client):
        """Unknown novel must return 404 (success=False), not 500."""
        res = client.get("/api/content/stats/no_such_novel_xyz")
        assert res.status_code == 404
        data = res.get_json()
        assert data.get("success") is False
        assert "error" in data

    def test_known_novel_returns_stats(self, client, sample_novel):
        """Known novel must return stats successfully."""
        res = client.get(f"/api/content/stats/{sample_novel}")
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("success") is True
        assert "stats" in data
