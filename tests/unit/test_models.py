"""Unit tests for portal/models.py (M3.1 W2 Task 2.5).

Targets line coverage 0% -> 80% on ``portal/models.py``. Pydantic
models have validation logic worth testing: required fields, field
constraints, custom ``@field_validator`` decorators, and the
``validate_request`` helper used by route handlers.

No DB, no Flask, no fixtures — these are pure pydantic validation
tests, instantiating each model class with valid and invalid inputs.
"""
import pytest
from pydantic import ValidationError

from models import (
    ChatMessage,
    ChatRequest,
    StreamRequest,
    GenerateStreamRequest,
    CreateNovelRequest,
    GenerateChapterRequest,
    EditChapterRequest,
    EditOutlineRequest,
    DeepSeekConfigRequest,
    ReviewChapterRequest,
    SearchRequest,
    APIResponse,
    ErrorDetail,
    GateResponse,
    validate_request,
)


# ── ChatMessage ─────────────────────────────────────────────────────────

class TestChatMessage:
    def test_valid_user(self):
        m = ChatMessage(role="user", content="hi")
        assert m.role == "user"
        assert m.content == "hi"

    def test_valid_system(self):
        m = ChatMessage(role="system", content="sys prompt")
        assert m.role == "system"

    def test_valid_assistant(self):
        m = ChatMessage(role="assistant", content="reply")
        assert m.role == "assistant"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="bogus", content="hi")

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")

    def test_missing_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(content="hi")  # type: ignore[call-arg]

    def test_missing_content_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user")  # type: ignore[call-arg]


# ── ChatRequest ─────────────────────────────────────────────────────────

class TestChatRequest:
    def test_defaults(self):
        r = ChatRequest()
        assert r.messages == []
        assert r.temperature is None
        assert r.max_tokens is None
        assert r.top_p is None
        assert r.operation == "ai-chat"
        assert r.novel == ""
        assert r.system == ""
        assert r.user == ""

    def test_valid_with_messages(self):
        m = ChatMessage(role="user", content="hi")
        r = ChatRequest(messages=[m], temperature=0.5, max_tokens=100)
        assert len(r.messages) == 1
        assert r.temperature == 0.5
        assert r.max_tokens == 100

    def test_temperature_out_of_range_high(self):
        with pytest.raises(ValidationError):
            ChatRequest(temperature=3.0)

    def test_temperature_out_of_range_negative(self):
        with pytest.raises(ValidationError):
            ChatRequest(temperature=-0.1)

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(max_tokens=0)

    def test_max_tokens_negative_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(max_tokens=-1)

    def test_max_tokens_too_high_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(max_tokens=100001)

    def test_top_p_out_of_range(self):
        with pytest.raises(ValidationError):
            ChatRequest(top_p=1.5)

    def test_top_p_negative_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(top_p=-0.1)


# ── StreamRequest ───────────────────────────────────────────────────────

class TestStreamRequest:
    def test_defaults(self):
        r = StreamRequest()
        assert r.messages == []
        assert r.model is None
        assert r.temperature is None
        assert r.operation == "stream-generate"

    def test_valid_full(self):
        m = ChatMessage(role="user", content="hi")
        r = StreamRequest(
            messages=[m],
            model="deepseek",
            temperature=1.0,
            max_tokens=2000,
            top_p=0.9,
            operation="stream",
            novel="novel-1",
        )
        assert r.model == "deepseek"
        assert r.novel == "novel-1"

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            StreamRequest(temperature=5.0)

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            StreamRequest(max_tokens=0)

    def test_top_p_out_of_range(self):
        with pytest.raises(ValidationError):
            StreamRequest(top_p=2.0)


# ── GenerateStreamRequest ───────────────────────────────────────────────

class TestGenerateStreamRequest:
    def test_defaults(self):
        r = GenerateStreamRequest()
        assert r.novel == ""
        assert r.volume == "vol-01"
        assert r.chapter_num == 1
        assert r.style == ""
        assert r.instructions == ""
        assert r.user == ""
        assert r.operation == "stream-generate"

    def test_valid_full(self):
        r = GenerateStreamRequest(
            novel="my-novel",
            volume="vol-02",
            chapter_num=5,
            style="wuxia",
            instructions="be dramatic",
            user="alice",
        )
        assert r.novel == "my-novel"
        assert r.volume == "vol-02"
        assert r.chapter_num == 5

    def test_chapter_num_zero_rejected(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(chapter_num=0)

    def test_chapter_num_negative_rejected(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(chapter_num=-1)

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(temperature=3.0)

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(max_tokens=0)

    def test_top_p_boundary_zero(self):
        r = GenerateStreamRequest(top_p=0.0)
        assert r.top_p == 0.0

    def test_top_p_boundary_one(self):
        r = GenerateStreamRequest(top_p=1.0)
        assert r.top_p == 1.0

    def test_top_p_above_one_rejected(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(top_p=1.5)

    def test_top_p_negative_rejected(self):
        with pytest.raises(ValidationError):
            GenerateStreamRequest(top_p=-0.1)


# ── CreateNovelRequest ──────────────────────────────────────────────────

class TestCreateNovelRequest:
    def test_minimum(self):
        r = CreateNovelRequest(name="test")
        assert r.name == "test"
        assert r.word_goal == "100万"
        assert r.perspective == "第三人称"
        assert r.genre == ""
        assert r.protagonist == ""
        assert r.selling_point == ""
        assert r.references == ""

    def test_name_required(self):
        with pytest.raises(ValidationError):
            CreateNovelRequest()  # type: ignore[call-arg]

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            CreateNovelRequest(name="x" * 200)

    def test_name_empty_rejected(self):
        with pytest.raises(ValidationError):
            CreateNovelRequest(name="")

    def test_full(self):
        r = CreateNovelRequest(
            name="My Novel",
            genre="xianxia",
            protagonist="Lin",
            selling_point="treasure hunting",
            word_goal="200万",
            perspective="第一人称",
            references="book1",
        )
        assert r.name == "My Novel"
        assert r.genre == "xianxia"
        assert r.perspective == "第一人称"


# ── GenerateChapterRequest ──────────────────────────────────────────────

class TestGenerateChapterRequest:
    def test_defaults(self):
        r = GenerateChapterRequest()
        assert r.chapter_num == ""
        assert r.volume == "vol-01"
        assert r.style == ""
        assert r.instructions == ""
        assert r.temperature is None
        assert r.max_tokens is None

    def test_valid(self):
        r = GenerateChapterRequest(
            chapter_num="3",
            volume="vol-02",
            style="wuxia",
            instructions="intro chapter",
        )
        assert r.chapter_num == "3"
        assert r.volume == "vol-02"

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            GenerateChapterRequest(temperature=3.0)

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            GenerateChapterRequest(max_tokens=0)


# ── EditChapterRequest ──────────────────────────────────────────────────

class TestEditChapterRequest:
    def test_valid(self):
        r = EditChapterRequest(content="some text")
        assert r.content == "some text"

    def test_content_required(self):
        with pytest.raises(ValidationError):
            EditChapterRequest()  # type: ignore[call-arg]

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            EditChapterRequest(content="")


# ── EditOutlineRequest ──────────────────────────────────────────────────

class TestEditOutlineRequest:
    def test_valid(self):
        r = EditOutlineRequest(content="outline text")
        assert r.content == "outline text"

    def test_content_required(self):
        with pytest.raises(ValidationError):
            EditOutlineRequest()  # type: ignore[call-arg]

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            EditOutlineRequest(content="")


# ── DeepSeekConfigRequest validators ────────────────────────────────────

class TestDeepSeekConfig:
    def test_defaults(self):
        r = DeepSeekConfigRequest()
        assert r.api_key == ""
        assert r.api_base == ""
        assert r.model == ""
        assert r.temperature == ""
        assert r.max_tokens == ""
        assert r.top_p == ""

    def test_valid(self):
        r = DeepSeekConfigRequest(
            api_key="k",
            api_base="https://api.example.com",
            model="deepseek-chat",
            temperature="0.5",
            max_tokens="100",
            top_p="0.9",
        )
        assert r.temperature == "0.5"
        assert r.max_tokens == "100"
        assert r.top_p == "0.9"

    def test_empty_strings_pass(self):
        # Empty strings should not trigger validators (falsy branch).
        r = DeepSeekConfigRequest(temperature="", max_tokens="", top_p="")
        assert r.temperature == ""
        assert r.max_tokens == ""
        assert r.top_p == ""

    def test_invalid_temperature_string(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(temperature="abc")

    def test_temperature_out_of_range_high(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(temperature="5.0")

    def test_temperature_out_of_range_low(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(temperature="-0.5")

    def test_temperature_boundary_zero(self):
        r = DeepSeekConfigRequest(temperature="0.0")
        assert r.temperature == "0.0"

    def test_temperature_boundary_two(self):
        r = DeepSeekConfigRequest(temperature="2.0")
        assert r.temperature == "2.0"

    def test_invalid_max_tokens(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(max_tokens="abc")

    def test_max_tokens_zero_rejected(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(max_tokens="0")

    def test_max_tokens_negative_rejected(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(max_tokens="-1")

    def test_invalid_top_p(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(top_p="abc")

    def test_top_p_out_of_range_high(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(top_p="2.0")

    def test_top_p_out_of_range_low(self):
        with pytest.raises(ValidationError):
            DeepSeekConfigRequest(top_p="-0.1")

    def test_top_p_boundary_zero(self):
        r = DeepSeekConfigRequest(top_p="0.0")
        assert r.top_p == "0.0"

    def test_top_p_boundary_one(self):
        r = DeepSeekConfigRequest(top_p="1.0")
        assert r.top_p == "1.0"


# ── ReviewChapterRequest ────────────────────────────────────────────────

class TestReviewChapterRequest:
    def test_defaults(self):
        r = ReviewChapterRequest(chapter_content="text")
        assert r.chapter_content == "text"
        assert r.chapter_ref == ""
        assert r.volume == "vol-01"

    def test_valid_full(self):
        r = ReviewChapterRequest(
            chapter_content="content",
            chapter_ref="ch1.md",
            volume="vol-02",
        )
        assert r.chapter_ref == "ch1.md"
        assert r.volume == "vol-02"

    def test_content_required(self):
        with pytest.raises(ValidationError):
            ReviewChapterRequest()  # type: ignore[call-arg]

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ReviewChapterRequest(chapter_content="")


# ── SearchRequest ───────────────────────────────────────────────────────

class TestSearch:
    def test_valid(self):
        r = SearchRequest(query="term")
        assert r.query == "term"
        assert r.limit == 20
        assert r.novel is None

    def test_valid_with_novel(self):
        r = SearchRequest(query="x", novel="n1", limit=10)
        assert r.novel == "n1"
        assert r.limit == 10

    def test_query_required(self):
        with pytest.raises(ValidationError):
            SearchRequest()  # type: ignore[call-arg]

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_query_too_long_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="x" * 501)

    def test_limit_zero_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="x", limit=0)

    def test_limit_too_high(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="x", limit=200)

    def test_limit_boundary_high(self):
        r = SearchRequest(query="x", limit=100)
        assert r.limit == 100


# ── APIResponse ─────────────────────────────────────────────────────────

class TestAPIResponse:
    def test_minimum(self):
        r = APIResponse(success=True)
        assert r.success is True
        assert r.error == ""
        assert r.data is None

    def test_with_data(self):
        r = APIResponse(success=True, error="", data={"k": 1})
        assert r.success is True
        assert r.data == {"k": 1}

    def test_failure(self):
        r = APIResponse(success=False, error="boom")
        assert r.success is False
        assert r.error == "boom"

    def test_success_required(self):
        with pytest.raises(ValidationError):
            APIResponse()  # type: ignore[call-arg]


# ── ErrorDetail ────────────────────────────────────────────────────────

class TestErrorDetail:
    def test_defaults(self):
        e = ErrorDetail(detail="boom")
        assert e.detail == "boom"
        assert e.phase == ""
        assert e.label == ""
        assert e.severity == "error"

    def test_full(self):
        e = ErrorDetail(
            detail="missing field",
            phase="init",
            label="init-phase",
            severity="warning",
        )
        assert e.detail == "missing field"
        assert e.phase == "init"
        assert e.severity == "warning"

    def test_detail_required(self):
        with pytest.raises(ValidationError):
            ErrorDetail()  # type: ignore[call-arg]


# ── GateResponse ────────────────────────────────────────────────────────

class TestGateResponse:
    def test_minimum(self):
        g = GateResponse(passed=True, phase="init", phase_label="初始化")
        assert g.passed is True
        assert g.phase == "init"
        assert g.phase_label == "初始化"
        assert g.errors == []
        assert g.dependent_phases == []

    def test_with_errors(self):
        err = ErrorDetail(detail="x")
        g = GateResponse(
            passed=False,
            phase="check",
            phase_label="校验",
            errors=[err],
            dependent_phases=["init"],
        )
        assert g.passed is False
        assert len(g.errors) == 1
        assert g.errors[0].detail == "x"
        assert g.dependent_phases == ["init"]

    def test_passed_required(self):
        with pytest.raises(ValidationError):
            GateResponse(phase="init", phase_label="初始化")  # type: ignore[call-arg]

    def test_phase_required(self):
        with pytest.raises(ValidationError):
            GateResponse(passed=True, phase_label="x")  # type: ignore[call-arg]

    def test_phase_label_required(self):
        with pytest.raises(ValidationError):
            GateResponse(passed=True, phase="init")  # type: ignore[call-arg]


# ── validate_request helper ────────────────────────────────────────────

class TestValidateRequest:
    def test_valid_data_returns_model(self):
        model, err = validate_request(ChatMessage, {"role": "user", "content": "hi"})
        assert model is not None
        assert err is None
        assert model.role == "user"

    def test_invalid_data_returns_error(self):
        model, err = validate_request(ChatMessage, {"role": "bogus", "content": ""})
        assert model is None
        assert err is not None
        assert err["success"] is False
        assert "validation_errors" in err
        assert isinstance(err["validation_errors"], list)
        assert len(err["validation_errors"]) >= 1

    def test_missing_required_field(self):
        model, err = validate_request(ChatRequest, {})
        # ChatRequest has all defaults, so {} is valid. Use a model that
        # requires fields instead.
        assert model is not None
        assert err is None

        model2, err2 = validate_request(CreateNovelRequest, {})
        assert model2 is None
        assert err2 is not None
        assert "name" in str(err2["validation_errors"])

    def test_validation_errors_contain_locations(self):
        model, err = validate_request(SearchRequest, {})
        assert model is None
        assert err is not None
        # Each error should be a "loc: msg" string.
        for entry in err["validation_errors"]:
            assert ":" in entry

    def test_valid_with_optional_model(self):
        model, err = validate_request(
            DeepSeekConfigRequest, {"temperature": "0.5", "max_tokens": "100"}
        )
        assert model is not None
        assert model.temperature == "0.5"

    def test_non_validation_error_returns_generic_failure(self):
        # When the underlying constructor raises something other than
        # ValidationError (e.g. TypeError from wrong arg shape), the helper
        # returns a generic failure envelope with empty validation_errors
        # (the except branch at models.py line ~185).
        model, err = validate_request(ChatMessage, "not-a-dict")
        assert model is None
        assert err["success"] is False
        assert err["validation_errors"] == []
