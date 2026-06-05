"""Shared helpers for functional tests (M3.1 W3-T3.1).

Centralises the 4-dim assertion helpers and the most common test
fixtures (content_db DB-path redirect, AI chat stub) so the
per-endpoint test files can stay focused on endpoint-specific
expectations.

Four dimensions per endpoint (per M2 core 4-dim pattern in
``tests/functional/test_chapter_lifecycle.py``):

  1. ``happy_path_*``   — 200/201 with success=True
  2. ``missing_field_*`` — 400/422 with success=False when required
                          field is absent
  3. ``not_found_*``     — 404 when the referenced resource does
                          not exist
  4. ``wrong_method_*``  — 405 when an unsupported HTTP verb is used

Helpers
-------
``point_content_db_at_tmp(monkeypatch, tmp_db_url)``
    Redirect ``content_db.DB_PATH`` at the tmp SQLite file and seed
    a minimal ``novels`` row so endpoints that delegate to
    ``content_db`` (rather than the SQLAlchemy ``repository``) see
    the same data as the rest of the test. Used by tests against
    ``/api/content/*`` and any chapter-outline route that bypasses
    the ``tmp_db`` SQLAlchemy engine.

``fake_deepseek_chat(monkeypatch, content="...")``
    Replace ``app.deepseek_chat`` with a deterministic stub. Returns
    the stub callable so callers can override side effects per test.

``assert_success_envelope(res)``
    Assert the response carries a JSON ``success`` key (the standard
    M3 envelope contract).

``assert_wrong_method_405(res)``
    Assert a 405 status code (the standard wrong-method response).

``assert_not_found(res)``
    Assert the response is 404 with success=False.

``assert_missing_field(res, field_name=None)``
    Assert the response is 400/422 with success=False. If
    ``field_name`` is given, also assert the field name appears in
    the error message (some endpoints echo the missing field name).
"""
import sqlite3


# ─── DB-path redirect helper ──────────────────────────────────────────

def point_content_db_at_tmp(monkeypatch, tmp_db_url):
    """Redirect ``content_db.DB_PATH`` at the tmp SQLite DB and ensure
    a ``test_novel`` row exists in that file.

    Many ``/api/content/*`` and chapter-outline routes delegate to
    ``content_db`` helpers (``search_all``, ``get_novel_stats``,
    ``sync_novel_from_files``, ...). ``content_db.get_db()`` opens raw
    sqlite3 against a module-level ``DB_PATH`` that defaults to
    ``portal/content.db`` — it does NOT honour ``DATABASE_URL``. The
    shared ``tmp_db`` fixture only seeds the SQLAlchemy engine, so we
    have to bridge the two paths so endpoints that use ``content_db``
    see the same data as endpoints that use ``repository``.

    Returns the ``content_db`` module for callers that need to
    monkeypatch additional attributes.
    """
    db_file = tmp_db_url.replace("sqlite:///", "")
    import content_db as _cd
    monkeypatch.setattr(_cd, "DB_PATH", db_file)
    # The tmp_db fixture's ensure_unified_schema() already created
    # the schema. We just need a test_novel row for _get_novel_id()
    # to resolve.
    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO novels (name, created_at) "
            "VALUES (?, datetime('now'))",
            ("test_novel",),
        )
        conn.commit()
    finally:
        conn.close()
    return _cd


# ─── AI chat stub ─────────────────────────────────────────────────────

def fake_deepseek_chat(monkeypatch, content="测试章节正文。"):
    """Monkeypatch ``app.deepseek_chat`` with a deterministic stub.

    Returns the patched callable so callers can override side effects
    per test (e.g., make the stub raise to exercise error paths).
    """
    import app as _app

    def _fake(messages, system_prompt=None, temperature=None,
              max_tokens=None, top_p=None, stream=False,
              operation=None, novel=""):
        return {
            "success": True,
            "content": content,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }
    monkeypatch.setattr(_app, "deepseek_chat", _fake)
    return _fake


# ─── Envelope assertions ──────────────────────────────────────────────

def assert_success_envelope(res):
    """Assert the response carries a JSON ``success`` key (M3 contract)."""
    assert res.get_json() is not None, f"no JSON body: {res.data!r}"
    assert "success" in res.get_json(), \
        f"missing 'success' key in response: {res.get_json()!r}"


def assert_wrong_method_405(res):
    """Assert a 405 response (wrong HTTP verb)."""
    assert res.status_code == 405, \
        f"expected 405, got {res.status_code}: {res.data!r}"


def assert_not_found(res):
    """Assert a 404 with success=False."""
    assert res.status_code == 404, \
        f"expected 404, got {res.status_code}: {res.data!r}"
    data = res.get_json() or {}
    assert data.get("success") is False, \
        f"expected success=False, got {data!r}"


def assert_missing_field(res, field_name=None):
    """Assert a 400/422 with success=False (missing required field).

    If ``field_name`` is given, also assert the field name appears in
    the response body or error message (some endpoints echo the
    missing field name; others don't, in which case the assertion
    is best-effort).
    """
    assert res.status_code in (400, 422), \
        f"expected 400/422, got {res.status_code}: {res.data!r}"
    data = res.get_json() or {}
    assert data.get("success") is False, \
        f"expected success=False, got {data!r}"
    if field_name is not None:
        body_text = res.data.decode("utf-8", errors="ignore")
        assert field_name in body_text, \
            f"expected field name '{field_name}' in response: {body_text!r}"
