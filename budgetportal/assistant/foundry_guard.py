"""Bound Foundry work per request and protect the provider during failures."""

import contextvars
import time
import uuid
from contextlib import contextmanager

from django.conf import settings
from django.core.cache import cache


class FoundryBudgetExceeded(Exception):
    pass


class FoundryCircuitOpen(Exception):
    pass


_budget = contextvars.ContextVar("assistant_foundry_budget", default=None)


@contextmanager
def foundry_request_guard():
    config = getattr(settings, "ASSISTANT_FOUNDRY_GUARD", {})
    token = _budget.set({"calls": 0, "tokens": 0, "deadline": time.monotonic() + config.get("deadline_seconds", 30)})
    try:
        yield
    finally:
        _budget.reset(token)


class FoundryGuard:
    def __init__(self, cache_backend=cache, config=None):
        self.cache = cache_backend
        self.config = config or getattr(settings, "ASSISTANT_FOUNDRY_GUARD", {})

    def before_call(self, max_tokens):
        state = _budget.get()
        if state is not None:
            if time.monotonic() >= state["deadline"]:
                raise FoundryBudgetExceeded("Assistant request deadline exceeded.")
            if state["calls"] >= self.config.get("max_calls_per_request", 4):
                raise FoundryBudgetExceeded("Foundry call limit exceeded.")
            if state["tokens"] + max_tokens > self.config.get("max_tokens_per_request", 1200):
                raise FoundryBudgetExceeded("Foundry token budget exceeded.")
            state["calls"] += 1
            state["tokens"] += max_tokens
        if self.cache.get("assistant:foundry:circuit-open"):
            raise FoundryCircuitOpen("Foundry circuit breaker is open.")

    def acquire_slot(self):
        """Acquire a bounded global provider slot for the whole HTTP call."""
        token = uuid.uuid4().hex
        lease = self.config.get("deadline_seconds", 30) + 5
        for index in range(self.config.get("max_concurrent_calls", 8)):
            key = "assistant:foundry:slot:{}".format(index)
            if self.cache.add(key, token, timeout=lease):
                return key, token
        raise FoundryBudgetExceeded("Foundry concurrency limit exceeded.")

    def release_slot(self, key, token):
        if not key:
            return
        # Cache backends use an atomic add for slot acquisition. Avoid deleting
        # a newer lease if the original owner timed out.
        try:
            if self.cache.get(key) == token:
                self.cache.delete(key)
        except Exception:
            return

    def success(self):
        self.cache.delete("assistant:foundry:failures")

    def failure(self):
        try:
            if self.cache.add("assistant:foundry:failures", 1, timeout=self.config.get("failure_window_seconds", 60)):
                return
            failures = self.cache.incr("assistant:foundry:failures")
            if failures >= self.config.get("circuit_failure_threshold", 5):
                self.cache.set("assistant:foundry:circuit-open", "1", timeout=self.config.get("circuit_cooldown_seconds", 30))
        except Exception:
            # Never turn a telemetry/cache failure into an unbounded retry loop.
            return
