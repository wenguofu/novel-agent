"""Unit tests for portal/rag_engine.py (M3.1 W2 T2.7.6).

Targets line coverage 48% -> 90%+. Tests the lazy chroma init,
collection lookup with name sanitization, query filtering, and
the multi-category budget management. ChromaDB is mocked.
"""
import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import rag_engine
from rag_engine import (
    CHROMA_AVAILABLE,
    CHROMA_DB_DIR,
    EMBED_MODEL,
    _ensure_chroma,
    _get_collection,
    _get_model,
    _is_chroma_available,
    _query_chroma,
    query_categories,
)


def _reset_rag_state():
    """Reset module-level lazy-init state between tests."""
    rag_engine._chroma_imported = False
    rag_engine._chroma_available = None
    rag_engine._model = None
    # Drop any globals injected by a successful _ensure_chroma() call so
    # the next test starts from a clean slate.
    for injected in ("chromadb", "SentenceTransformer"):
        if injected in rag_engine.__dict__:
            del rag_engine.__dict__[injected]


# ── Module-level state ─────────────────────────────────────────────────

class TestModuleGlobals:
    def test_chroma_db_dir_is_path(self):
        assert isinstance(CHROMA_DB_DIR, Path)
        assert "novel_rag_db" in str(CHROMA_DB_DIR)

    def test_embed_model_name(self):
        assert EMBED_MODEL == "BAAI/bge-small-zh-v1.5"

    def test_chroma_available_is_none_at_import(self):
        # `property(...) if False else None` ensures CHROMA_AVAILABLE is
        # always None at import time (see line 45 of rag_engine.py).
        assert CHROMA_AVAILABLE is None


# ── _ensure_chroma ─────────────────────────────────────────────────────

class TestEnsureChroma:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_returns_true_when_chroma_imports(self):
        with patch.dict("sys.modules", {
            "chromadb": MagicMock(),
            "sentence_transformers": MagicMock(),
        }):
            result = _ensure_chroma()
        assert result is True
        assert rag_engine._chroma_available is True
        assert rag_engine._chroma_imported is True

    def test_returns_false_when_chroma_missing(self):
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("chromadb", "sentence_transformers"):
                raise ImportError("not installed")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = _ensure_chroma()
        assert result is False
        assert rag_engine._chroma_available is False

    def test_caches_result(self):
        with patch.dict("sys.modules", {
            "chromadb": MagicMock(),
            "sentence_transformers": MagicMock(),
        }):
            r1 = _ensure_chroma()
            r2 = _ensure_chroma()
        assert r1 is r2
        # Module state is cached
        assert rag_engine._chroma_imported is True
        assert rag_engine._chroma_available is True

    def test_caches_negative_result(self):
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("chromadb", "sentence_transformers"):
                raise ImportError("not installed")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            r1 = _ensure_chroma()
            r2 = _ensure_chroma()
        assert r1 is False
        assert r2 is False
        assert rag_engine._chroma_imported is True

    def test_sets_globals_on_success(self):
        with patch.dict("sys.modules", {
            "chromadb": MagicMock(),
            "sentence_transformers": MagicMock(),
        }):
            _ensure_chroma()
        # Globals are populated by `globals()['chromadb'] = _cb`
        assert "chromadb" in rag_engine.__dict__
        assert "SentenceTransformer" in rag_engine.__dict__


# ── _get_model ─────────────────────────────────────────────────────────

class TestGetModel:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_returns_none_when_chroma_unavailable(self):
        with patch("rag_engine._ensure_chroma", return_value=False):
            result = _get_model()
        assert result is None

    def test_loads_model_when_available(self):
        mock_model = MagicMock()
        with patch("rag_engine._ensure_chroma", return_value=True), \
             patch("rag_engine.SentenceTransformer", return_value=mock_model, create=True):
            result = _get_model()
        assert result is mock_model
        assert rag_engine._model is mock_model

    def test_returns_cached_model(self):
        cached = MagicMock()
        rag_engine._model = cached
        with patch("rag_engine._ensure_chroma", return_value=True):
            result = _get_model()
        assert result is cached

    def test_swallows_model_load_exception(self):
        with patch("rag_engine._ensure_chroma", return_value=True), \
             patch("rag_engine.SentenceTransformer",
                   side_effect=Exception("load failed"), create=True):
            result = _get_model()
        assert result is None


# ── _is_chroma_available ──────────────────────────────────────────────

class TestIsChromaAvailable:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_delegates_to_ensure_chroma(self):
        with patch("rag_engine._ensure_chroma", return_value=True) as mock_ensure:
            result = _is_chroma_available()
        assert result is True
        mock_ensure.assert_called_once()

    def test_delegates_returns_false(self):
        with patch("rag_engine._ensure_chroma", return_value=False):
            result = _is_chroma_available()
        assert result is False


# ── _get_collection ────────────────────────────────────────────────────

class TestGetCollection:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_returns_none_when_chroma_unavailable(self):
        # CHROMA_AVAILABLE is None at import; the `if not CHROMA_AVAILABLE`
        # branch fires before we touch chromadb.
        with patch("rag_engine.CHROMA_AVAILABLE", None):
            result = _get_collection("test_novel")
        assert result is None

    def test_returns_collection_when_available(self):
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch("rag_engine.CHROMA_AVAILABLE", True), \
             patch("rag_engine._ensure_chroma", return_value=True), \
             patch.object(rag_engine, "chromadb", mock_chromadb, create=True):
            result = _get_collection("test_novel")
        assert result is mock_collection
        mock_client.get_collection.assert_called_once()

    def test_sanitizes_novel_name(self):
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch("rag_engine.CHROMA_AVAILABLE", True), \
             patch("rag_engine._ensure_chroma", return_value=True), \
             patch.object(rag_engine, "chromadb", mock_chromadb, create=True):
            result = _get_collection("novel/with:special*chars")
        # The sanitized name should be passed: special chars -> "_"
        call_args = mock_client.get_collection.call_args[0][0]
        assert "/" not in call_args
        assert ":" not in call_args
        assert "*" not in call_args
        # The remaining chars (alphanumeric) are preserved
        assert "novel" in call_args
        assert "with" in call_args
        assert "special" in call_args
        assert "chars" in call_args

    def test_hashes_short_names(self):
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch("rag_engine.CHROMA_AVAILABLE", True), \
             patch("rag_engine._ensure_chroma", return_value=True), \
             patch.object(rag_engine, "chromadb", mock_chromadb, create=True):
            # Name with only special chars: sanitized -> "___" -> strip -> ""
            # Length 0 < 3 -> md5 hash used
            result = _get_collection("___")
        call_args = mock_client.get_collection.call_args[0][0]
        # Hashed name is 16 hex chars
        assert len(call_args) == 16
        assert call_args.isalnum() or all(c in "0123456789abcdef" for c in call_args)

    def test_returns_none_on_client_exception(self):
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.side_effect = Exception("disk full")
        with patch("rag_engine.CHROMA_AVAILABLE", True), \
             patch("rag_engine._ensure_chroma", return_value=True), \
             patch.object(rag_engine, "chromadb", mock_chromadb, create=True):
            result = _get_collection("test_novel")
        assert result is None

    def test_returns_none_when_collection_missing(self):
        # get_collection raises (e.g. collection doesn't exist yet)
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client
        with patch("rag_engine.CHROMA_AVAILABLE", True), \
             patch("rag_engine._ensure_chroma", return_value=True), \
             patch.object(rag_engine, "chromadb", mock_chromadb, create=True):
            result = _get_collection("test_novel")
        assert result is None


# ── _query_chroma ──────────────────────────────────────────────────────

class TestQueryChroma:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_returns_empty_when_no_collection(self):
        with patch("rag_engine._get_collection", return_value=None):
            result = _query_chroma("novel", "query")
        assert result == []

    def test_returns_empty_on_query_error(self):
        mock_collection = MagicMock()
        mock_collection.query.side_effect = Exception("query failed")
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            result = _query_chroma("novel", "query")
        assert result == []

    def test_formats_results(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1 content", "doc2 content"]],
            "metadatas": [[
                {"file_type": "chapter", "source_file": "src1", "title": "t1",
                 "volume": 1, "chapter": 5, "char_count": 100},
                {"file_type": "outline", "source_file": "src2", "title": "t2",
                 "volume": 1, "chapter": 6, "char_count": 50},
            ]],
            "distances": [[0.2, 0.5]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            result = _query_chroma("novel", "query")
        assert len(result) == 2
        assert result[0]["content"] == "doc1 content"
        assert result[0]["score"] == pytest.approx(0.8)  # 1.0 - 0.2
        assert result[0]["file_type"] == "chapter"
        assert result[0]["volume"] == 1
        assert result[0]["chapter"] == 5
        assert result[0]["char_count"] == 100
        assert result[0]["source"] == "src1"
        assert result[0]["title"] == "t1"
        # Second item: 1.0 - 0.5 = 0.5
        assert result[1]["score"] == pytest.approx(0.5)

    def test_builds_filter_with_file_type_only(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", file_type="chapter")
        # Inspect the where filter
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"file_type": "chapter"}

    def test_builds_filter_with_volume_only(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", volume=2)
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"volume": 2}

    def test_builds_filter_with_chapter_only(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", chapter=7)
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] == {"chapter": 7}

    def test_builds_filter_with_multiple_conditions(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", file_type="chapter", volume=1, chapter=5)
        call_kwargs = mock_collection.query.call_args.kwargs
        assert "$and" in call_kwargs["where"]
        assert len(call_kwargs["where"]["$and"]) == 3

    def test_no_filter_when_no_params(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query")
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["where"] is None

    def test_caps_n_results_at_10(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", n_results=20)
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["n_results"] == 10

    def test_passes_n_results_below_cap(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            _query_chroma("novel", "query", n_results=3)
        call_kwargs = mock_collection.query.call_args.kwargs
        assert call_kwargs["n_results"] == 3

    def test_handles_missing_metadatas(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": None,  # No metadatas
            "distances": [[0.3]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            result = _query_chroma("novel", "query")
        # Falls back to empty meta -> file_type="?"
        assert result[0]["file_type"] == "?"
        assert result[0]["source"] == "?"

    def test_handles_missing_distances(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["doc1"]],
            "metadatas": [[{}]],
            "distances": None,
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            result = _query_chroma("novel", "query")
        # Default distance 1.0 -> score 0.0
        assert result[0]["score"] == 0.0

    def test_handles_empty_results(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        with patch("rag_engine._get_collection", return_value=mock_collection), \
             patch("rag_engine._get_model", return_value=MagicMock()):
            result = _query_chroma("novel", "query")
        assert result == []


# ── query_categories ──────────────────────────────────────────────────

class TestQueryCategories:
    def setup_method(self):
        _reset_rag_state()

    def teardown_method(self):
        _reset_rag_state()

    def test_empty_categories(self):
        result = query_categories("novel", [])
        assert result["results"] == []
        assert result["total_tokens"] == 0

    def test_max_tokens_in_response(self):
        with patch("rag_engine._query_chroma", return_value=[]):
            result = query_categories("novel", [], total_max_tokens=5000)
        assert result["max_tokens"] == 5000

    def test_default_total_max_tokens(self):
        with patch("rag_engine._query_chroma", return_value=[]):
            result = query_categories("novel", [])
        # Default total_max_tokens is 10000
        assert result["max_tokens"] == 10000

    def test_collects_chunks_within_budget(self):
        # Mock _query_chroma to return 3 chunks; only 1 fits in budget
        # (150 fits in 250; 150+150=300 > 250)
        mock_chunks = [
            {"content": "测" * 100, "file_type": "chapter"},  # 150 tokens
            {"content": "测" * 100, "file_type": "chapter"},  # 150 tokens
            {"content": "测" * 100, "file_type": "chapter"},  # 150 tokens
        ]
        with patch("rag_engine._query_chroma", return_value=mock_chunks):
            result = query_categories("novel", [{
                "category": "x", "query": "q", "max_tokens": 250, "limit": 5,
            }], total_max_tokens=1000)
        # First chunk fits (0+150=150 <= 250); second exceeds (150+150=300>250)
        assert len(result["results"][0]["chunks"]) == 1
        assert result["results"][0]["tokens_used"] == 150

    def test_collects_all_chunks_within_budget(self):
        mock_chunks = [
            {"content": "测" * 10, "file_type": "chapter"},  # 15 tokens
            {"content": "测" * 10, "file_type": "chapter"},  # 15 tokens
        ]
        with patch("rag_engine._query_chroma", return_value=mock_chunks):
            result = query_categories("novel", [{
                "category": "x", "query": "q", "max_tokens": 1000, "limit": 5,
            }], total_max_tokens=10000)
        assert len(result["results"][0]["chunks"]) == 2

    def test_breaks_when_budget_exhausted(self):
        # 3 chunks of 150 tokens; budget=400 fits 2, breaks on 3rd
        # iter 0: 0+150=150 <= 400 -> add
        # iter 1: 150+150=300 <= 400 -> add
        # iter 2: 300+150=450 > 400 -> break
        mock_chunks = [
            {"content": "测" * 100, "file_type": "chapter"},  # 150 tokens
            {"content": "测" * 100, "file_type": "chapter"},  # 150 tokens
            {"content": "测" * 100, "file_type": "chapter"},  # would exceed
        ]
        with patch("rag_engine._query_chroma", return_value=mock_chunks):
            result = query_categories("novel", [{
                "category": "x", "query": "q", "max_tokens": 400, "limit": 5,
            }], total_max_tokens=1000)
        assert len(result["results"][0]["chunks"]) == 2
        assert result["results"][0]["tokens_used"] == 300

    def test_total_tokens_is_sum(self):
        # Each category consumes tokens independently; total = sum
        mock_chunks = [
            {"content": "测" * 10, "file_type": "chapter"},  # 15
            {"content": "测" * 10, "file_type": "chapter"},  # 15
        ]
        with patch("rag_engine._query_chroma", return_value=mock_chunks):
            result = query_categories("novel", [
                {"category": "a", "query": "q", "max_tokens": 100, "limit": 5},
                {"category": "b", "query": "q", "max_tokens": 100, "limit": 5},
            ], total_max_tokens=1000)
        # Cat a: 15+15=30, Cat b: 15+15=30, total=60
        assert result["total_tokens"] == 60
        assert result["results"][0]["tokens_used"] == 30
        assert result["results"][1]["tokens_used"] == 30

    def test_mode_chromadb_when_available(self):
        with patch("rag_engine._query_chroma", return_value=[]), \
             patch("rag_engine.CHROMA_AVAILABLE", True):
            result = query_categories("novel", [])
        assert result["mode"] == "chromadb"

    def test_mode_db_only_when_unavailable(self):
        with patch("rag_engine._query_chroma", return_value=[]), \
             patch("rag_engine.CHROMA_AVAILABLE", None):
            result = query_categories("novel", [])
        assert result["mode"] == "db-only"

    def test_default_category_name(self):
        with patch("rag_engine._query_chroma", return_value=[]):
            result = query_categories("novel", [{"query": "q"}])
        # Missing "category" key -> default "general"
        assert result["results"][0]["category"] == "general"

    def test_default_max_tokens(self):
        with patch("rag_engine._query_chroma", return_value=[]):
            result = query_categories("novel", [{"category": "x", "query": "q"}])
        # Missing "max_tokens" -> default 1000
        assert result["results"][0]["tokens_requested"] == 1000

    def test_default_limit(self):
        with patch("rag_engine._query_chroma", return_value=[]) as mock_q:
            query_categories("novel", [{"category": "x", "query": "q"}])
        # Default limit is 5
        call_kwargs = mock_q.call_args.kwargs
        assert call_kwargs["n_results"] == 5

    def test_passes_file_type_when_present(self):
        with patch("rag_engine._query_chroma", return_value=[]) as mock_q:
            query_categories("novel", [{
                "category": "x", "query": "q", "file_type": "outline",
            }])
        call_kwargs = mock_q.call_args.kwargs
        assert call_kwargs["file_type"] == "outline"

    def test_uses_category_as_file_type_when_missing(self):
        with patch("rag_engine._query_chroma", return_value=[]) as mock_q:
            query_categories("novel", [{
                "category": "plot_continuity", "query": "q",
                # no file_type
            }])
        call_kwargs = mock_q.call_args.kwargs
        # Should use category as file_type (file_type or category)
        assert call_kwargs["file_type"] == "plot_continuity"

    def test_passes_volume_and_chapter(self):
        with patch("rag_engine._query_chroma", return_value=[]) as mock_q:
            query_categories("novel", [{
                "category": "x", "query": "q", "volume": 3, "chapter": 10,
            }])
        call_kwargs = mock_q.call_args.kwargs
        assert call_kwargs["volume"] == 3
        assert call_kwargs["chapter"] == 10

    def test_budget_caps_total_across_categories(self):
        # Two categories each requesting 1000 tokens, total cap 600.
        # First category consumes the entire budget; second gets nothing.
        mock_chunks = [
            {"content": "测" * 10, "file_type": "chapter"},  # 15
        ]
        with patch("rag_engine._query_chroma", return_value=mock_chunks):
            result = query_categories("novel", [
                {"category": "a", "query": "q", "max_tokens": 1000, "limit": 5},
                {"category": "b", "query": "q", "max_tokens": 1000, "limit": 5},
            ], total_max_tokens=600)
        # First category gets the chunk (allocated=600); second gets 0
        # (remaining=0 -> allocated=0 -> first chunk 15 > 0 breaks)
        assert len(result["results"][0]["chunks"]) == 1
        assert len(result["results"][1]["chunks"]) == 0
        assert result["results"][1]["tokens_used"] == 0
        assert result["total_tokens"] == 15
