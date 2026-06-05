"""
API Resilience — circuit breaker, retry, and timeout patterns for DeepSeek API calls.

Features:
  - Exponential backoff retry (via tenacity)
  - Circuit breaker pattern (fail-fast after N consecutive failures)
  - Response time tracking and slow-call warnings
  - Graceful degradation when API is unhealthy
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


# ── Circuit Breaker ─────────────────────────────────────────────────────

@dataclass
class CircuitBreaker:
    """Simple circuit breaker: opens after `failure_threshold` consecutive failures,
    resets after `reset_timeout` seconds.

    Thread-safe for basic use.
    """
    name: str
    failure_threshold: int = 5
    reset_timeout: float = 60.0  # seconds before trying again
    half_open_max: int = 1       # max requests to test in half-open state

    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)  # closed | open | half-open
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return False
            if self._state == "open":
                return True
            # half-open: allow limited requests
            return False

    def try_half_open(self) -> bool:
        """Check if the circuit should transition to half-open. Returns True if transitioned."""
        with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time > self.reset_timeout:
                    self._state = "half-open"
                    logger.info(f"[CircuitBreaker:{self.name}] Transitioning to half-open")
                    return True
            return False

    def record_success(self):
        with self._lock:
            if self._state != "closed":
                logger.info(f"[CircuitBreaker:{self.name}] Reset to closed after success")
            self._state = "closed"
            self._failure_count = 0

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                logger.warning(
                    f"[CircuitBreaker:{self.name}] Circuit OPEN after "
                    f"{self._failure_count} consecutive failures"
                )

    def __call__(self, fn: Callable) -> Callable:
        """Decorator: apply circuit breaker to a function."""
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if self.is_open:
                # Check if timeout has elapsed to transition to half-open
                if not self.try_half_open():
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is open — API calls blocked for "
                        f"{self.reset_timeout - (time.time() - self._last_failure_time):.0f}s"
                    )
            try:
                result = fn(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open and blocks the call."""
    pass


# ── Retry with Exponential Backoff ──────────────────────────────────────

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Decorator: retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        backoff_factor: Multiplier for each retry
        retryable_exceptions: Exception types to retry on
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"[Retry] {fn.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"[Retry] {fn.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
            raise last_exception  # type: ignore
        return wrapper
    return decorator


# ── Response Time Tracker ───────────────────────────────────────────────

@dataclass
class ResponseTimeTracker:
    """Track API response times and log slow calls."""
    slow_threshold: float = 10.0  # seconds
    critical_threshold: float = 30.0

    _total_calls: int = field(default=0, init=False)
    _total_time: float = field(default=0.0, init=False)
    _slow_calls: int = field(default=0, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def track(self, operation: str, duration: float):
        with self._lock:
            self._total_calls += 1
            self._total_time += duration

            if duration >= self.critical_threshold:
                self._slow_calls += 1
                logger.error(
                    f"[SlowCall:CRITICAL] {operation} took {duration:.1f}s "
                    f"(threshold: {self.critical_threshold}s)"
                )
            elif duration >= self.slow_threshold:
                self._slow_calls += 1
                logger.warning(
                    f"[SlowCall] {operation} took {duration:.1f}s "
                    f"(threshold: {self.slow_threshold}s)"
                )

    @property
    def avg_response_time(self) -> float:
        with self._lock:
            return self._total_time / max(self._total_calls, 1)

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "total_calls": self._total_calls,
                "avg_time": round(self.avg_response_time, 3),
                "slow_calls": self._slow_calls,
                "slow_rate": round(self._slow_calls / max(self._total_calls, 1), 3),
            }


# ── Global instances ────────────────────────────────────────────────────

deepseek_circuit = CircuitBreaker(name="minimax-api", failure_threshold=5, reset_timeout=60.0)
response_tracker = ResponseTimeTracker(slow_threshold=10.0, critical_threshold=30.0)


# ── Decorator factory ───────────────────────────────────────────────────

def api_resilient(operation: str = "api-call"):
    """Combined decorator: circuit breaker + retry + timing for API calls.

    Usage:
        @api_resilient("generate-chapter")
        def call_deepseek(...): ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        @deepseek_circuit
        @with_retry(max_attempts=3, retryable_exceptions=(Exception,))
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                duration = time.time() - start
                response_tracker.track(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start
                response_tracker.track(operation, duration)
                raise
        return wrapper
    return decorator
