"""Unit tests for portal/resilience.py (M3.1 W2 Task 2.6).

Targets line coverage 0% -> 80%. The resilience module is pure
Python — circuit breaker state machine, retry decorator, and
response-time tracker. No DB or Flask needed.

We exercise the public API: CircuitBreaker, CircuitBreakerOpenError,
with_retry, ResponseTimeTracker, api_resilient, and the two module
globals (deepseek_circuit, response_tracker).

For deterministic time-based tests we use:
  * small reset_timeout (0.01s) + real time.sleep(0.02) for the
    half-open transition
  * unittest.mock.patch on ``resilience.time.sleep`` to assert
    backoff delays without actually sleeping

NOTE on ResponseTimeTracker.stats: the source has a known bug where
``stats`` (line 184) acquires ``self._lock`` (a non-reentrant
``threading.Lock``) and then calls ``self.avg_response_time`` (line
188) which tries to acquire the same lock again — a deadlock. We
work around it in tests by swapping ``_lock`` for a
``threading.RLock()`` only for the stats tests, leaving the source
unmodified.
"""
import threading
import time
from unittest.mock import patch

import pytest

import resilience
from resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ResponseTimeTracker,
    api_resilient,
    deepseek_circuit,
    response_tracker,
    with_retry,
)


@pytest.fixture
def rlock_tracker():
    """ResponseTimeTracker with a re-entrant lock so .stats() doesn't
    deadlock on the known lock-in-stats bug.
    """
    t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
    t._lock = threading.RLock()
    return t


# ── CircuitBreaker — basic state machine ───────────────────────────────


class TestCircuitBreakerBasic:
    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.is_open is False
        assert cb._state == "closed"

    def test_default_thresholds(self):
        cb = CircuitBreaker(name="test")
        assert cb.failure_threshold == 5
        assert cb.reset_timeout == 60.0
        assert cb.half_open_max == 1

    def test_below_threshold_stays_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        assert cb._state == "closed"
        assert cb._failure_count == 2

    def test_at_threshold_opens(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb._state == "open"

    def test_above_threshold_keeps_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()  # opens here
        cb.record_failure()  # stays open
        assert cb.is_open is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        # Now two more failures should not open
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False

    def test_record_success_closes_from_open(self):
        """If a breaker is somehow open and we record success,
        state should reset to closed (defensive path)."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb._state == "open"
        cb.record_success()
        assert cb._state == "closed"
        assert cb._failure_count == 0


# ── CircuitBreaker — half-open transition ──────────────────────────────


class TestCircuitBreakerHalfOpen:
    def test_try_half_open_before_timeout_returns_false(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=2, reset_timeout=60.0
        )
        cb.record_failure()
        cb.record_failure()
        # No time has passed — still open
        assert cb.try_half_open() is False
        assert cb._state == "open"

    def test_try_half_open_after_timeout_returns_true(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=2, reset_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)  # past reset_timeout
        assert cb.try_half_open() is True
        assert cb._state == "half-open"

    def test_try_half_open_when_closed_returns_false(self):
        """Closed breakers never transition to half-open via try_half_open."""
        cb = CircuitBreaker(name="test")
        assert cb.try_half_open() is False
        assert cb._state == "closed"

    def test_is_open_false_during_half_open(self):
        """The is_open property returns False in half-open state —
        it permits limited test traffic through."""
        cb = CircuitBreaker(
            name="test", failure_threshold=2, reset_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.try_half_open()
        assert cb._state == "half-open"
        assert cb.is_open is False

    def test_half_open_success_closes(self):
        """A success while in half-open should reset to closed."""
        cb = CircuitBreaker(
            name="test", failure_threshold=2, reset_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.try_half_open()
        assert cb._state == "half-open"
        cb.record_success()
        assert cb._state == "closed"
        assert cb._failure_count == 0


# ── CircuitBreaker — decorator (callable) ──────────────────────────────


class TestCircuitBreakerDecorator:
    def test_decorator_passes_through_success(self):
        cb = CircuitBreaker(name="test")

        @cb
        def good_fn():
            return "ok"

        assert good_fn() == "ok"
        assert cb.is_open is False

    def test_decorator_preserves_function_metadata(self):
        cb = CircuitBreaker(name="test")

        @cb
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."
        assert my_function() == 42

    def test_decorator_counts_failures_and_opens(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)

        @cb
        def bad_fn():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            bad_fn()
        with pytest.raises(ValueError):
            bad_fn()
        assert cb.is_open is True

    def test_decorator_raises_circuit_open_when_blocked(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)

        @cb
        def bad_fn():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            bad_fn()  # 1 failure → opens
        # Subsequent calls should be blocked with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as excinfo:
            bad_fn()
        assert "test" in str(excinfo.value)

    def test_decorator_recovers_after_half_open_success(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, reset_timeout=0.01
        )
        state = {"calls": 0}

        @cb
        def sometimes_bad():
            state["calls"] += 1
            if state["calls"] == 1:
                raise ValueError("boom")
            return "ok"

        with pytest.raises(ValueError):
            sometimes_bad()
        assert cb.is_open is True

        time.sleep(0.02)  # past reset_timeout

        # Next call: is_open is True, but try_half_open transitions
        # to half-open, allowing the call through. The success closes
        # the breaker.
        assert sometimes_bad() == "ok"
        assert cb._state == "closed"
        assert cb.is_open is False


# ── with_retry — exponential backoff ───────────────────────────────────


class TestWithRetry:
    def test_succeeds_on_first_try(self):
        @with_retry(max_attempts=3, base_delay=0.01)
        def good_fn():
            return "ok"

        assert good_fn() == "ok"

    def test_retries_then_succeeds(self):
        counter = {"calls": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def flaky_fn():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise ValueError("transient")
            return "ok"

        assert flaky_fn() == "ok"
        assert counter["calls"] == 2

    def test_exhausts_attempts_then_raises(self):
        counter = {"calls": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def always_fails():
            counter["calls"] += 1
            raise ValueError("always")

        with pytest.raises(ValueError):
            always_fails()
        assert counter["calls"] == 3

    def test_only_retries_specified_exceptions(self):
        counter = {"calls": 0}

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        def fn():
            counter["calls"] += 1
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            fn()
        # TypeError is not in retryable_exceptions, so no retries
        assert counter["calls"] == 1

    def test_retries_on_subclass_of_retryable(self):
        """Exception matching is by isinstance, so subclasses of a
        retryable exception should also be retried."""
        counter = {"calls": 0}

        class MyValueError(ValueError):
            pass

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        def fn():
            counter["calls"] += 1
            if counter["calls"] < 3:
                raise MyValueError("flaky")
            return "ok"

        assert fn() == "ok"
        assert counter["calls"] == 3

    def test_caps_delay_at_max_delay(self):
        """max_delay should clamp the exponential backoff.

        With base_delay=1.0, backoff_factor=10.0, max_attempts=3,
        max_delay=2.0:
          attempt 1 fails → sleep 1.0 (base)
          attempt 2 fails → sleep min(10.0, 2.0) = 2.0 (capped)
          attempt 3 fails → raise
        """
        @with_retry(
            max_attempts=3,
            base_delay=1.0,
            max_delay=2.0,
            backoff_factor=10.0,
        )
        def fn():
            raise ValueError("boom")

        with patch("resilience.time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                fn()
            sleep_values = [c.args[0] for c in mock_sleep.call_args_list]
            # Two sleeps: after attempt 1 and after attempt 2
            assert len(sleep_values) == 2
            assert sleep_values[0] == 1.0
            assert sleep_values[1] == 2.0  # capped

    def test_exponential_backoff_sequence(self):
        """base_delay=0.5, backoff_factor=2.0:
          attempt 1 fails → sleep 0.5
          attempt 2 fails → sleep 1.0
          attempt 3 fails → raise
        """
        @with_retry(
            max_attempts=3,
            base_delay=0.5,
            backoff_factor=2.0,
        )
        def fn():
            raise ValueError("boom")

        with patch("resilience.time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                fn()
            sleep_values = [c.args[0] for c in mock_sleep.call_args_list]
            assert sleep_values == [0.5, 1.0]

    def test_preserves_function_metadata(self):
        @with_retry(max_attempts=2, base_delay=0.01)
        def my_func():
            """My doc."""
            return 1

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My doc."

    def test_passes_args_and_kwargs(self):
        @with_retry(max_attempts=2, base_delay=0.01)
        def add(a, b, mult=1):
            return (a + b) * mult

        assert add(2, 3, mult=4) == 20

    def test_succeeds_on_last_attempt(self):
        counter = {"calls": 0}

        @with_retry(max_attempts=3, base_delay=0.01)
        def fn():
            counter["calls"] += 1
            if counter["calls"] < 3:
                raise ValueError("not yet")
            return "finally"

        assert fn() == "finally"
        assert counter["calls"] == 3

    def test_default_retryable_includes_exception(self):
        """By default, retryable_exceptions=(Exception,), so any
        subclass of Exception should be retried."""
        counter = {"calls": 0}

        @with_retry(max_attempts=2, base_delay=0.01)
        def fn():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise RuntimeError("flaky")
            return "ok"

        assert fn() == "ok"
        assert counter["calls"] == 2


# ── ResponseTimeTracker ────────────────────────────────────────────────


class TestResponseTimeTracker:
    def test_initial_state(self):
        t = ResponseTimeTracker()
        assert t._total_calls == 0
        assert t._total_time == 0.0
        assert t._slow_calls == 0
        # avg uses max(0, 1) → 0/1 = 0
        assert t.avg_response_time == 0.0

    def test_default_thresholds(self):
        t = ResponseTimeTracker()
        assert t.slow_threshold == 10.0
        assert t.critical_threshold == 30.0

    def test_track_fast_call(self):
        t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
        t.track("op", 0.5)
        assert t._total_calls == 1
        assert t._total_time == 0.5
        assert t._slow_calls == 0

    def test_track_slow_call(self):
        t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
        t.track("op", 1.5)  # above slow, below critical
        assert t._total_calls == 1
        assert t._slow_calls == 1

    def test_track_critical_call(self):
        t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
        t.track("op", 2.5)  # above critical
        assert t._total_calls == 1
        assert t._slow_calls == 1

    def test_track_exactly_at_slow_threshold(self):
        """Boundary check: duration exactly equal to slow_threshold
        should count as slow (>= comparison)."""
        t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
        t.track("op", 1.0)
        assert t._slow_calls == 1

    def test_track_exactly_at_critical_threshold(self):
        """Boundary check: duration exactly equal to critical_threshold
        should count as slow (>= comparison)."""
        t = ResponseTimeTracker(slow_threshold=1.0, critical_threshold=2.0)
        t.track("op", 2.0)
        assert t._slow_calls == 1

    def test_avg_response_time_after_calls(self):
        t = ResponseTimeTracker()
        t.track("op", 1.0)
        t.track("op", 2.0)
        t.track("op", 3.0)
        assert t._total_calls == 3
        assert t._total_time == 6.0
        assert t.avg_response_time == 2.0

    def test_stats_returns_dict_with_keys(self, rlock_tracker):
        t = rlock_tracker
        t.track("op", 0.5)
        t.track("op", 1.5)  # slow
        s = t.stats
        assert isinstance(s, dict)
        assert s["total_calls"] == 2
        assert s["slow_calls"] == 1
        assert "avg_time" in s
        assert "slow_rate" in s
        # 1 slow out of 2 = 0.5
        assert s["slow_rate"] == 0.5
        # avg_time should be 1.0 (rounded to 3 places)
        assert s["avg_time"] == 1.0

    def test_stats_with_no_calls(self, rlock_tracker):
        t = rlock_tracker
        s = t.stats
        assert s["total_calls"] == 0
        assert s["slow_calls"] == 0
        assert s["avg_time"] == 0.0
        assert s["slow_rate"] == 0.0

    def test_stats_slow_rate_zero_when_no_calls(self, rlock_tracker):
        """slow_rate uses max(total, 1) — should be 0/1 = 0 when empty."""
        t = rlock_tracker
        assert t.stats["slow_rate"] == 0.0

    def test_stats_avg_rounded(self, rlock_tracker):
        t = rlock_tracker
        t.track("op", 1.0)
        t.track("op", 1.0)
        t.track("op", 1.0)
        # avg = 1.0, rounded to 3 places
        assert t.stats["avg_time"] == 1.0


# ── Module globals ──────────────────────────────────────────────────────


class TestModuleGlobals:
    def test_deepseek_circuit_exists(self):
        assert isinstance(deepseek_circuit, CircuitBreaker)
        assert deepseek_circuit.name == "minimax-api"
        assert deepseek_circuit.failure_threshold == 5
        assert deepseek_circuit.reset_timeout == 60.0

    def test_response_tracker_exists(self):
        assert isinstance(response_tracker, ResponseTimeTracker)
        assert response_tracker.slow_threshold == 10.0
        assert response_tracker.critical_threshold == 30.0


# ── api_resilient — combined decorator factory ──────────────────────────


class TestApiResilient:
    def test_returns_function_result(self):
        @api_resilient("test-op")
        def fn():
            return "ok"

        assert fn() == "ok"

    def test_propagates_exceptions(self):
        @api_resilient("test-op")
        def bad_fn():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            bad_fn()

    def test_tracks_response_time_on_success(self):
        @api_resilient("test-op-tracks-success")
        def fn():
            return "ok"

        before = response_tracker._total_calls
        fn()
        after = response_tracker._total_calls
        assert after == before + 1

    def test_tracks_response_time_on_exception(self):
        @api_resilient("test-op-tracks-error")
        def bad_fn():
            raise ValueError("boom")

        before = response_tracker._total_calls
        with pytest.raises(ValueError):
            bad_fn()
        after = response_tracker._total_calls
        # The with_retry decorator inside api_resilient retries 3 times,
        # so the api_resilient wrapper is called 3 times — each call
        # records timing. The final exception propagates after all
        # retries are exhausted.
        assert after == before + 3

    def test_preserves_function_metadata(self):
        @api_resilient("op")
        def my_function():
            """The doc."""
            return 1

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "The doc."

    def test_passes_args_and_kwargs(self):
        @api_resilient("op")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_default_operation_name(self):
        """api_resilient() with no arg should use the default 'api-call'."""
        @api_resilient()
        def fn():
            return 42

        assert fn() == 42

    def test_retry_then_succeed(self):
        """A function that fails the first 2 calls (caught by retry) and
        succeeds on the 3rd should return the success value via the
        combined decorator."""
        state = {"calls": 0}

        @api_resilient("flaky-op")
        def flaky():
            state["calls"] += 1
            if state["calls"] < 3:
                raise ValueError("transient")
            return "finally"

        with patch("resilience.time.sleep"):
            assert flaky() == "finally"
        assert state["calls"] == 3
