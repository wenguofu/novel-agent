"""
Error handling — structured exception hierarchy and Flask error handlers.

Replaces silent `except Exception: pass` patterns with proper logging
and structured error responses.
"""

import logging
import traceback
from typing import Optional, Dict, Any

from flask import jsonify

logger = logging.getLogger(__name__)


# ── Exception Hierarchy ─────────────────────────────────────────────────

class NovelAgentError(Exception):
    """Base exception for all novel-agent errors."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "内部错误"

    def __init__(self, message: Optional[str] = None, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message or self.message)
        self.detail = detail or {}

    def to_dict(self) -> dict:
        """Return error as a plain dict (works outside Flask context)."""
        return {
            "success": False,
            "error": str(self),
            "error_code": self.error_code,
            "detail": self.detail,
        }

    def to_response(self) -> tuple:
        """Return Flask JSON response tuple."""
        return jsonify(self.to_dict()), self.status_code


class ValidationError(NovelAgentError):
    """Request validation failure."""
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "请求参数无效"


class NotFoundError(NovelAgentError):
    """Resource not found."""
    status_code = 404
    error_code = "NOT_FOUND"
    message = "资源不存在"


class GateBlockedError(NovelAgentError):
    """Stage gate check failed."""
    status_code = 400
    error_code = "GATE_BLOCKED"
    message = "阶段门控未通过"

    def __init__(self, phase: str, errors: list, suggestion: str = ""):
        super().__init__(
            message=self.message,
            detail={
                "phase": phase,
                "gate_requirements": errors,
                "suggestion": suggestion,
            },
        )
        self.phase = phase
        self.errors = errors


class APIError(NovelAgentError):
    """External API call failed."""
    status_code = 502
    error_code = "API_ERROR"
    message = "外部API调用失败"


class RateLimitError(NovelAgentError):
    """Rate limit exceeded."""
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "请求过于频繁"

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=self.message,
            detail={"retry_after": retry_after},
        )
        self.retry_after = retry_after


class DatabaseError(NovelAgentError):
    """Database operation failed."""
    status_code = 500
    error_code = "DB_ERROR"
    message = "数据库操作失败"


class ConfigError(NovelAgentError):
    """Configuration error."""
    status_code = 500
    error_code = "CONFIG_ERROR"
    message = "配置错误"


# ── Safe execution helpers ──────────────────────────────────────────────

def safe_call(fn, *args, default=None, log_level: int = logging.WARNING,
              context: str = "", **kwargs):
    """Execute a function safely, logging errors instead of swallowing silently.

    Args:
        fn: Callable to execute
        *args: Positional arguments
        default: Default return value on failure
        log_level: Logging level for errors
        context: Human-readable context for the log message
        **kwargs: Keyword arguments

    Returns:
        fn result or default on failure
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        ctx = f" [{context}]" if context else ""
        logger.log(log_level, f"safe_call failed{ctx}: {e}")
        logger.debug(traceback.format_exc())
        return default


def safe_db_call(fn, *args, default=None, context: str = "", **kwargs):
    """Execute a database function safely. Errors are logged, never swallowed."""
    return safe_call(fn, *args, default=default, context=f"DB:{context}" if context else "DB",
                     log_level=logging.ERROR, **kwargs)


def safe_io_call(fn, *args, default=None, context: str = "", **kwargs):
    """Execute an I/O function safely."""
    return safe_call(fn, *args, default=default, context=f"IO:{context}" if context else "IO",
                     log_level=logging.ERROR, **kwargs)


# ── Flask error handler registration ────────────────────────────────────

def register_error_handlers(app):
    """Register centralized error handlers on a Flask app."""

    @app.errorhandler(NovelAgentError)
    def handle_novel_agent_error(e: NovelAgentError):
        logger.error(f"[{e.error_code}] {e}", extra={"detail": e.detail})
        return e.to_response()

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({
            "success": False,
            "error": "接口不存在",
            "error_code": "NOT_FOUND",
        }), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({
            "success": False,
            "error": "不支持的HTTP方法",
            "error_code": "METHOD_NOT_ALLOWED",
        }), 405

    @app.errorhandler(500)
    def handle_500(e):
        logger.error(f"Unhandled server error: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "服务器内部错误，请稍后重试",
            "error_code": "INTERNAL_ERROR",
        }), 500

    logger.info("Error handlers registered")
