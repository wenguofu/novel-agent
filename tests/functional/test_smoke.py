"""Smoke tests for the functional test infrastructure itself."""
import pytest


def test_client_serves_root_index(client):
    """Flask test client should return 200 for GET /."""
    res = client.get("/")
    assert res.status_code == 200


def test_client_serves_assets(client):
    """Flask test client should serve /assets/ (may 404 if no build, but never 500)."""
    res = client.get("/assets/missing.js")
    assert res.status_code < 500


def test_sample_novel_fixture_creates_novel(client, sample_novel):
    """sample_novel fixture should create a real novel in the tmp DB."""
    res = client.get(f"/api/novels/{sample_novel}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["novel"]["name"] == sample_novel
