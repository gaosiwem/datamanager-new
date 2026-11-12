"""Reusable, bounded Microsoft Foundry client for assistant NLP stages.

The client intentionally exposes only chat-completion transport. Scope
classification, intent parsing, and answer generation remain separate future
components and must validate their own structured responses.
"""

import logging
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests
from django.conf import settings

from .foundry_guard import FoundryBudgetExceeded, FoundryCircuitOpen, FoundryGuard


logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = frozenset((408, 429, 500, 502, 503, 504))
SUPPORTED_AUTH_MODES = frozenset(("api_key", "entra_id"))
SUPPORTED_PURPOSES = frozenset(
    ("scope_classification", "intent_parsing", "answer_generation")
)


class FoundryClientError(Exception):
    """Base error with a message safe for a future public API."""


class FoundryConfigurationError(FoundryClientError):
    pass


class FoundryServiceError(FoundryClientError):
    pass


@dataclass(frozen=True)
class FoundryClientConfig:
    endpoint: str
    deployment: str
    api_key: str
    auth_mode: str
    api_version: str
    entra_scope: str
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_retries: int

    @classmethod
    def from_settings(cls) -> "FoundryClientConfig":
        config = getattr(settings, "AZURE_OPENAI", {})
        return cls(
            endpoint=config.get("endpoint", ""),
            deployment=config.get("deployment", ""),
            api_key=config.get("api_key", ""),
            auth_mode=config.get("auth_mode", "api_key"),
            api_version=config.get("api_version", "2024-10-21"),
            entra_scope=config.get(
                "entra_scope", "https://cognitiveservices.azure.com/.default"
            ),
            connect_timeout_seconds=config.get("connect_timeout_seconds", 5),
            read_timeout_seconds=config.get("read_timeout_seconds", 20),
            max_retries=config.get("max_retries", 2),
        )

    def validate(self) -> None:
        if not self.endpoint or not self.deployment:
            raise FoundryConfigurationError("Azure OpenAI is not configured.")
        endpoint = urlparse(self.endpoint)
        if endpoint.scheme != "https" or not endpoint.hostname:
            raise FoundryConfigurationError("Azure OpenAI endpoint must use HTTPS.")
        allowed_hosts = getattr(settings, "AZURE_OPENAI_ALLOWED_HOSTS", ())
        if allowed_hosts and endpoint.hostname not in allowed_hosts:
            raise FoundryConfigurationError("Azure OpenAI endpoint is not approved.")
        if self.auth_mode not in SUPPORTED_AUTH_MODES:
            raise FoundryConfigurationError(
                "Azure OpenAI authentication is not configured."
            )
        if self.auth_mode == "api_key" and not self.api_key:
            raise FoundryConfigurationError(
                "Azure OpenAI authentication is not configured."
            )
        if not self.api_version or not self.entra_scope:
            raise FoundryConfigurationError("Azure OpenAI is not configured.")
        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise FoundryConfigurationError(
                "Azure OpenAI timeout configuration is invalid."
            )
        if (
            not isinstance(self.max_retries, int)
            or self.max_retries < 0
            or self.max_retries > 5
        ):
            raise FoundryConfigurationError(
                "Azure OpenAI retry configuration is invalid."
            )


class FoundryClient:
    """Call an Azure OpenAI deployment with safe, transient-only retries."""

    def __init__(
        self,
        config: Optional[FoundryClientConfig] = None,
        session: Optional[requests.Session] = None,
        credential: Optional[Any] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or FoundryClientConfig.from_settings()
        self.config.validate()
        self.session = session or requests.Session()
        self.credential = credential
        self.sleep = sleep
        self.guard = FoundryGuard()

    @property
    def url(self) -> str:
        endpoint = self.config.endpoint.rstrip("/")
        if self.uses_openai_v1:
            return "{}/chat/completions".format(endpoint)
        return "{}/openai/deployments/{}/chat/completions?api-version={}".format(
            endpoint, self.config.deployment, self.config.api_version
        )

    @property
    def uses_openai_v1(self) -> bool:
        """Whether the configured Foundry endpoint is the OpenAI v1 route.

        Foundry's current OpenAI-compatible endpoint already includes
        ``/openai/v1`` and selects a deployment through the request's ``model``
        field.  Azure's deployment-based endpoint continues to use the older
        route and query-string API version.
        """
        return self.config.endpoint.rstrip("/").endswith("/openai/v1")

    def complete_chat(
        self,
        messages: List[Dict[str, str]],
        purpose: str,
        max_tokens: int = 500,
        temperature: float = 0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a raw payload for a future validated assistant stage."""
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list.")
        if not purpose:
            raise ValueError("purpose is required.")
        if purpose not in SUPPORTED_PURPOSES:
            raise ValueError("purpose is not supported.")
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer.")
        try:
            self.guard.before_call(max_tokens)
        except (FoundryBudgetExceeded, FoundryCircuitOpen) as error:
            raise FoundryServiceError("The AI service is temporarily unavailable.") from error

        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.uses_openai_v1:
            payload["model"] = self.config.deployment
        if response_format is not None:
            payload["response_format"] = response_format
        return self._post(payload, purpose)

    def _post(self, payload: Dict[str, Any], purpose: str) -> Dict[str, Any]:
        slot_key, slot_token = self.guard.acquire_slot()
        try:
            attempts = self.config.max_retries + 1
            for attempt in range(1, attempts + 1):
                try:
                    response = self.session.request(
                        "POST",
                        self.url,
                        headers=self._headers(),
                        json=payload,
                        timeout=(
                            self.config.connect_timeout_seconds,
                            self.config.read_timeout_seconds,
                        ),
                    )
                except requests.RequestException as error:
                    if attempt < attempts:
                        self._log_retry(purpose, attempt, error.__class__.__name__)
                        self.sleep(self._retry_delay(attempt))
                        continue
                    self.guard.failure()
                    self._log_failure(purpose, error.__class__.__name__)
                    raise FoundryServiceError("The AI service is temporarily unavailable.")

                if response.status_code in TRANSIENT_STATUS_CODES and attempt < attempts:
                    self._log_retry(purpose, attempt, "HTTP {}".format(response.status_code))
                    self.sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))
                    continue

                if response.status_code >= 400:
                    self.guard.failure()
                    self._log_failure(purpose, "HTTP {}".format(response.status_code))
                    raise FoundryServiceError("The AI service is temporarily unavailable.")

                try:
                    result = response.json()
                    self.guard.success()
                    return result
                except ValueError:
                    self.guard.failure()
                    self._log_failure(purpose, "invalid JSON response")
                    raise FoundryServiceError("The AI service is temporarily unavailable.")
            raise FoundryServiceError("The AI service is temporarily unavailable.")
        finally:
            self.guard.release_slot(slot_key, slot_token)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.auth_mode == "api_key":
            headers["api-key"] = self.config.api_key
        else:
            headers["Authorization"] = "Bearer {}".format(self._access_token())
        return headers

    def _access_token(self) -> str:
        credential = self.credential
        if credential is None:
            credential = self._default_credential()
            self.credential = credential
        return credential.get_token(self.config.entra_scope).token

    @staticmethod
    def _default_credential() -> Any:
        try:
            from azure.identity import DefaultAzureCredential
        except ImportError:
            raise FoundryConfigurationError(
                "Microsoft Entra ID support is not installed."
            )
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)

    @staticmethod
    def _retry_delay(attempt: int, retry_after: Optional[str] = None) -> float:
        try:
            if retry_after is not None:
                return min(max(float(retry_after), 0), 30)
        except (TypeError, ValueError):
            pass
        return min(2 ** (attempt - 1), 8)

    @staticmethod
    def _log_retry(purpose: str, attempt: int, detail: str) -> None:
        logger.warning(
            "Azure OpenAI request retrying purpose=%s attempt=%s detail=%s",
            purpose,
            attempt,
            detail,
        )

    @staticmethod
    def _log_failure(purpose: str, detail: str) -> None:
        logger.error(
            "Azure OpenAI request failed purpose=%s detail=%s", purpose, detail
        )
