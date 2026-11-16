"""Privacy-preserving shared response cache for public assistant answers."""

import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache


SAFE_STATUSES = frozenset(("verified", "data_not_found", "needs_clarification", "out_of_scope"))
PII_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.I),
    re.compile(r"\b(?:\+?27|0)\d[\d\s().-]{7,}\b"),
    re.compile(r"\b\d{6}[\s-]?\d{4,7}\b"),
)


class AssistantCacheUnavailable(Exception):
    """The required shared cache is unavailable."""


def normalise_question(question):
    return " ".join(question.casefold().split())


def contains_personal_data(question):
    return any(pattern.search(question) for pattern in PII_PATTERNS)


@dataclass(frozen=True)
class CacheClaim:
    response: dict = None
    lock_token: str = None


class AssistantAnswerCache:
    """Cache only public, validated answers; never persist raw user questions."""

    def __init__(self, cache_backend=cache, config=None):
        self.cache = cache_backend
        self.config = config or getattr(settings, "ASSISTANT_CACHE", {})

    @property
    def enabled(self):
        return bool(self.config.get("enabled", False))

    def eligible(self, question, context):
        # Screen explanations use trusted server-side path metadata, but do not
        # cache user-derived context or personal questions.
        return self.enabled and not contains_personal_data(question) and not any(
            key not in {"sphere", "department", "financial_year", "screen_path"}
            for key in (context or {})
        )

    def key(self, question, context):
        payload = {
            "v": self.config.get("schema_version", "1"),
            "q": normalise_question(question),
            "context": context or {},
            "data_revision": self._revision("assistant:data-revision"),
            "content_revision": self._revision("assistant:content-revision"),
            "policy_revision": self.config.get("policy_revision", "1"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        secret = self.config.get("hmac_key") or settings.SECRET_KEY
        digest = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
        return "assistant:answer:" + digest

    def get(self, key):
        try:
            return self.cache.get(key)
        except Exception as error:
            self._unavailable(error)

    def claim(self, key):
        cached = self.get(key)
        if cached is not None:
            return CacheClaim(response=cached)
        token = uuid.uuid4().hex
        lock_key = key + ":lock"
        try:
            acquired = self.cache.add(lock_key, token, timeout=self.config.get("lock_seconds", 35))
        except Exception as error:
            self._unavailable(error)
        if acquired:
            return CacheClaim(lock_token=token)
        return CacheClaim()

    def wait_for_result(self, key):
        deadline = time.monotonic() + float(self.config.get("wait_seconds", 1.5))
        while time.monotonic() < deadline:
            response = self.get(key)
            if response is not None:
                return response
            time.sleep(0.1)
        return None

    def store(self, key, response):
        if not self._cacheable(response):
            return
        payload = {name: value for name, value in response.items() if name not in {"request_id", "_observability"}}
        try:
            self.cache.set(key, payload, timeout=self._ttl(payload["status"]))
        except Exception as error:
            self._unavailable(error)

    def release(self, key, token):
        if not token:
            return
        lock_key = key + ":lock"
        # django-redis uses Redis' atomic compare-and-delete primitive. The
        # fallback is for local development only and is deliberately disabled
        # when a shared cache is required.
        try:
            from django_redis import get_redis_connection

            client = get_redis_connection("default")
            client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0",
                1, lock_key, token,
            )
            return
        except ImportError:
            if self.config.get("require_shared_cache", False):
                raise AssistantCacheUnavailable("Shared cache lock support is unavailable.")
        except Exception as error:
            self._unavailable(error)
        if self.cache.get(lock_key) == token:
            self.cache.delete(lock_key)

    def increment_revision(self, name):
        try:
            if self.cache.add(name, 1, timeout=None):
                return 1
            return self.cache.incr(name)
        except Exception as error:
            self._unavailable(error)

    def _revision(self, name):
        try:
            value = self.cache.get(name)
            return value if value is not None else 1
        except Exception as error:
            self._unavailable(error)

    def _cacheable(self, response):
        if response.get("status") not in SAFE_STATUSES:
            return False
        if response.get("_observability", {}).get("output_failure"):
            return False
        return True

    def _ttl(self, status):
        return self.config.get("ttls", {}).get(status, 300)

    def _unavailable(self, error):
        if self.config.get("require_shared_cache", False):
            raise AssistantCacheUnavailable("The shared assistant cache is unavailable.")
        raise error
