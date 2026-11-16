"""Privacy-safe structured observability for assistant processing."""

import json
import logging
import threading
from collections import Counter, defaultdict
from time import perf_counter


logger = logging.getLogger(__name__)


class AssistantObservability:
    """Process-local counters plus structured logs for deployed log collectors.

    Raw questions are deliberately neither stored nor logged. Production log
    aggregation can retain these structured events according to its approved
    privacy policy without introducing a second question-content store.
    """

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger
        self._counts = Counter()
        self._latencies = defaultdict(list)
        self._lock = threading.Lock()

    def stage(self, stage, started):
        duration_ms = round((perf_counter() - started) * 1000, 2)
        with self._lock:
            self._latencies[stage].append(duration_ms)
        return duration_ms

    def request(
        self,
        request_id,
        final_status,
        duration_ms,
        scope=None,
        category=None,
        intent=None,
        confidence=None,
        fallback_used=False,
        output_failure=False,
    ):
        with self._lock:
            self._counts["total_requests"] += 1
            self._counts[self._metric_for_status(final_status)] += 1
            if fallback_used:
                self._counts["deterministic_fallback_responses"] += 1
            if output_failure:
                self._counts["output_validation_failures"] += 1
        self._log(
            "assistant_request",
            {
                "request_id": request_id,
                "scope": scope,
                "category": category,
                "intent": intent,
                "final_status": final_status,
                "duration_ms": duration_ms,
                "scope_confidence": confidence,
                "fallback_used": fallback_used,
            },
        )

    def foundry_failure(self, request_id, stage):
        with self._lock:
            self._counts["foundry_failures"] += 1
        self._log(
            "assistant_foundry_failure", {"request_id": request_id, "stage": stage}
        )

    def snapshot(self):
        with self._lock:
            return {
                "counts": dict(self._counts),
                "latency_by_stage_ms": {
                    key: tuple(value) for key, value in self._latencies.items()
                },
            }

    @staticmethod
    def _metric_for_status(status):
        return {
            "verified": "verified_answers",
            "out_of_scope": "out_of_scope_requests",
            "needs_clarification": "ambiguous_requests",
            "data_not_found": "data_not_found_responses",
            "unsupported_vulekamali_query": "unsupported_queries",
            "blocked_prompt_attack": "prompt_attacks",
        }.get(status, "errors")

    def _log(self, event, fields):
        self.logger.info(
            "%s %s", event, json.dumps(fields, sort_keys=True, default=str)
        )
