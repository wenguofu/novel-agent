"""Structured JSON logging for novel-agent portal.

Provides:
- StructuredLogger: JSON-format logger with timestamp, level, request_id, operation
- with_logging decorator: auto-add request_id + timing to Flask route handlers
- migrate_existing_logs: convert existing print/logging calls to structured format
- Health check support and performance monitoring
"""

import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from functools import wraps


class StructuredLogger:
    """JSON-format structured logger.

    Usage:
        log = StructuredLogger("novel-agent")
        log.info("chapter generated", novel="my-novel", chapter="ch-0001", elapsed_ms=1234)
    """

    def __init__(self, name: str, level: int = logging.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Only add handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(level)
            self.logger.addHandler(handler)

    def _format(self, level: str, message: str, **extra) -> str:
        record = {
            "timestamp": datetime.now().isoformat(),
            "logger": self.name,
            "level": level,
            "message": message,
        }
        # Merge extra fields, filtering out None values
        for k, v in extra.items():
            if v is not None:
                record[k] = v
        return json.dumps(record, ensure_ascii=False)

    def debug(self, msg, **kwargs):
        self.logger.debug(self._format("DEBUG", msg, **kwargs))

    def info(self, msg, **kwargs):
        self.logger.info(self._format("INFO", msg, **kwargs))

    def warning(self, msg, **kwargs):
        self.logger.warning(self._format("WARNING", msg, **kwargs))

    def error(self, msg, **kwargs):
        self.logger.error(self._format("ERROR", msg, **kwargs))

    def exception(self, msg, **kwargs):
        self.logger.exception(self._format("ERROR", msg, **kwargs))


# Module-level singleton
log = StructuredLogger("novel-agent")


def with_logging(f=None, *, include_args: bool = False):
    """Decorator: add request_id + timing to Flask route handlers.

    Usage:
        @with_logging
        def api_generate_chapter(novel_name): ...

        @with_logging(include_args=True)
        def api_create_novel(): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())[:8]
            start = datetime.now()

            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start).total_seconds()
                extra = {
                    "request_id": request_id,
                    "operation": func.__name__,
                    "elapsed_seconds": round(elapsed, 3),
                    "success": True,
                }
                if include_args and kwargs:
                    extra["kwargs"] = {k: str(v)[:100] for k, v in kwargs.items()}
                log.info(f"{func.__name__} completed", **extra)
                return result
            except Exception as e:
                elapsed = (datetime.now() - start).total_seconds()
                log.error(
                    f"{func.__name__} failed: {e}",
                    request_id=request_id,
                    operation=func.__name__,
                    elapsed_seconds=round(elapsed, 3),
                    success=False,
                    error_type=type(e).__name__,
                )
                raise

        return wrapper

    if f is not None:
        return decorator(f)
    return decorator


def log_token_operation(model, operation, prompt_tokens, completion_tokens,
                        novel="", request_id=None):
    """Log a token-consuming operation with cost estimate."""
    model_lower = model.lower()
    if "reasoner" in model_lower or "r1" in model_lower:
        input_price = 0.14 / 1_000_000
        output_price = 0.28 / 1_000_000
    else:
        input_price = 0.27 / 1_000_000
        output_price = 1.10 / 1_000_000

    cost = round(prompt_tokens * input_price + completion_tokens * output_price, 6)
    total = prompt_tokens + completion_tokens

    log.info(
        "token usage",
        model=model,
        operation=operation,
        novel=novel,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total,
        cost_estimate=cost,
        request_id=request_id,
    )
    return cost


def migrate_existing_logs(app_module_path=None):
    """Install the structured logger as the default for the app module.

    Call this once at startup to replace print() and logging.warning()
    with structured equivalents.
    """
    # Set up root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s"}'
        ))
        root.addHandler(handler)

    log.info("logging initialized", version="1.0")


# ── Health & Performance Monitoring ─────────────────────────────────────

class HealthTracker:
    """Tracks application health metrics."""

    def __init__(self):
        self._start_time = time.time()
        self._request_count = 0
        self._error_count = 0
        self._total_response_time = 0.0
        self._lock = threading.Lock()

    def record_request(self, duration: float, is_error: bool = False):
        with self._lock:
            self._request_count += 1
            self._total_response_time += duration
            if is_error:
                self._error_count += 1

    @property
    def request_count(self) -> int:
        with self._lock:
            return self._request_count

    @property
    def error_count(self) -> int:
        with self._lock:
            return self._error_count

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    @property
    def error_rate(self) -> float:
        with self._lock:
            if self._request_count == 0:
                return 0.0
            return self._error_count / self._request_count

    @property
    def avg_response_time(self) -> float:
        with self._lock:
            if self._request_count == 0:
                return 0.0
            return self._total_response_time / self._request_count

    def get_health(self) -> dict:
        with self._lock:
            return {
                "status": "healthy" if (self._request_count == 0 or self._error_count / self._request_count < 0.1) else "degraded",
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "total_requests": self._request_count,
                "error_count": self._error_count,
                "error_rate": round(self._error_count / max(self._request_count, 1), 4),
                "avg_response_time_ms": round(self._total_response_time / max(self._request_count, 1) * 1000, 1),
            }


health_tracker = HealthTracker()


def with_perf_logging(f=None, *, operation: str = ""):
    """Decorator: add performance tracking to Flask route handlers.

    Combines request_id, timing, and health tracking in one decorator.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            request_id = str(uuid.uuid4())[:8]
            start = time.time()

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                health_tracker.record_request(elapsed, is_error=False)
                extra = {
                    "request_id": request_id,
                    "operation": op_name,
                    "elapsed_ms": round(elapsed * 1000, 1),
                    "success": True,
                }
                log.info(f"[{op_name}] completed", **extra)
                return result
            except Exception as e:
                elapsed = time.time() - start
                health_tracker.record_request(elapsed, is_error=True)
                log.error(
                    f"[{op_name}] failed: {e}",
                    request_id=request_id,
                    operation=op_name,
                    elapsed_ms=round(elapsed * 1000, 1),
                    success=False,
                    error_type=type(e).__name__,
                )
                raise

        return wrapper

    if f is not None:
        return decorator(f)
    return decorator
