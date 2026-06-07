"""
Pydantic request/response models for all API endpoints.

Provides:
  - Input validation on all endpoints
  - Auto-generated OpenAPI-compatible schemas
  - Type-safe request parsing
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ── AI / Chat ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    system: str = ""
    user: str = ""
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operation: str = "ai-chat"
    novel: str = ""


class StreamRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    system: str = ""
    user: str = ""
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operation: str = "stream-generate"
    novel: str = ""


class GenerateStreamRequest(BaseModel):
    novel: str = ""
    volume: str = "vol-01"
    chapter_num: int = Field(default=1, ge=1)
    style: str = ""
    instructions: str = ""
    user: str = ""
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    operation: str = "stream-generate"


# ── Novel / Content ─────────────────────────────────────────────────────

class CreateNovelRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    genre: str = ""
    protagonist: str = ""
    selling_point: str = ""
    word_goal: str = "100万"
    perspective: str = "第三人称"
    references: str = ""


class GenerateChapterRequest(BaseModel):
    chapter_num: str = ""
    volume: str = "vol-01"
    style: str = ""
    instructions: str = ""
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)


class EditChapterRequest(BaseModel):
    content: str = Field(..., min_length=1)


class EditOutlineRequest(BaseModel):
    content: str = Field(..., min_length=1)


# ── Config ──────────────────────────────────────────────────────────────

class DeepSeekConfigRequest(BaseModel):
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    temperature: str = ""
    max_tokens: str = ""
    top_p: str = ""

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if v:
            try:
                t = float(v)
                if not 0.0 <= t <= 2.0:
                    raise ValueError("temperature must be between 0.0 and 2.0")
            except ValueError:
                raise ValueError("temperature must be a valid float")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v):
        if v:
            try:
                t = int(v)
                if t < 1:
                    raise ValueError("max_tokens must be positive")
            except ValueError:
                raise ValueError("max_tokens must be a valid integer")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v):
        if v:
            try:
                p = float(v)
                if not 0.0 <= p <= 1.0:
                    raise ValueError("top_p must be between 0.0 and 1.0")
            except ValueError:
                raise ValueError("top_p must be a valid float")
        return v


# ── Reviews ─────────────────────────────────────────────────────────────

class ReviewChapterRequest(BaseModel):
    chapter_content: str = Field(..., min_length=1)
    chapter_ref: str = ""
    volume: str = "vol-01"


# ── Search ──────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    novel: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


# ── Responses ───────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool
    error: str = ""
    data: Optional[Dict[str, Any]] = None


class ErrorDetail(BaseModel):
    detail: str
    phase: str = ""
    label: str = ""
    severity: str = "error"


class GateResponse(BaseModel):
    passed: bool
    phase: str
    phase_label: str
    errors: List[ErrorDetail] = Field(default_factory=list)
    dependent_phases: List[str] = Field(default_factory=list)


# ── Validation helper ───────────────────────────────────────────────────

def validate_request(model_cls, data: dict) -> tuple:
    """Validate request data against a Pydantic model.

    Returns:
        (validated_model_or_None, error_response_or_None)
    """
    try:
        instance = model_cls(**data)
        return instance, None
    except Exception as e:
        errors = []
        if hasattr(e, 'errors'):
            for err in e.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", "validation error")
                errors.append(f"{loc}: {msg}")
        return None, {
            "success": False,
            "error": "请求参数验证失败",
            "validation_errors": errors,
        }


def validate_json_request(model_cls):
    """Decorator factory: validates ``request.json`` against a Pydantic
    model before the wrapped route handler runs. On validation failure
    the decorator short-circuits with a 400 response and a structured
    ``validation_errors`` list — the route body never sees bad input.

    Usage:
        @app.route("/api/ai/chat", methods=["POST"])
        @validate_json_request(ChatRequest)
        def api_ai_chat():
            req: ChatRequest = g.validated_request
            # ... use req.messages, req.system, etc.
    """
    from functools import wraps
    from flask import g, request, jsonify

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            instance, err = validate_request(model_cls, data)
            if err is not None:
                return jsonify(err), 400
            g.validated_request = instance
            return fn(*args, **kwargs)
        return wrapper
    return decorator
