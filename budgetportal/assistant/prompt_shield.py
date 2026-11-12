"""Optional Azure AI Content Safety Prompt Shields integration."""

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings

from .prompt_security import PromptShieldError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptShieldConfig:
    endpoint: str
    api_key: str
    auth_mode: str
    api_version: str
    entra_scope: str
    timeout_seconds: float

    @classmethod
    def from_settings(cls):
        config = getattr(settings, "AZURE_CONTENT_SAFETY", {})
        return cls(
            endpoint=config.get("endpoint", ""),
            api_key=config.get("api_key", ""),
            auth_mode=config.get("auth_mode", "api_key"),
            api_version=config.get("api_version", "2024-09-01"),
            entra_scope=config.get(
                "entra_scope", "https://cognitiveservices.azure.com/.default"
            ),
            timeout_seconds=config.get("timeout_seconds", 10),
        )

    def validate(self):
        if not self.endpoint or self.timeout_seconds <= 0:
            raise PromptShieldError("Prompt Shields is not configured.")
        if self.auth_mode not in ("api_key", "entra_id"):
            raise PromptShieldError("Prompt Shields is not configured.")
        if self.auth_mode == "api_key" and not self.api_key:
            raise PromptShieldError("Prompt Shields is not configured.")


class FoundryPromptShield:
    """Detect indirect and direct prompt attacks through Prompt Shields."""

    def __init__(
        self, config: Optional[PromptShieldConfig] = None, session=None, credential=None
    ):
        self.config = config or PromptShieldConfig.from_settings()
        self.config.validate()
        self.session = session or requests.Session()
        self.credential = credential

    def detect_attack(self, question: str) -> bool:
        try:
            response = self.session.request(
                "POST",
                "{}/contentsafety/text:shieldPrompt?api-version={}".format(
                    self.config.endpoint.rstrip("/"), self.config.api_version
                ),
                headers=self._headers(),
                json={"userPrompt": question},
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise PromptShieldError("Prompt Shields request failed.")
            return bool(response.json()["userPromptAnalysis"]["attackDetected"])
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            logger.error(
                "Prompt Shields request failed error_type=%s", error.__class__.__name__
            )
            raise PromptShieldError("Prompt Shields request failed.")

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.config.auth_mode == "api_key":
            headers["Ocp-Apim-Subscription-Key"] = self.config.api_key
        else:
            headers["Authorization"] = "Bearer {}".format(self._access_token())
        return headers

    def _access_token(self):
        credential = self.credential
        if credential is None:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError:
                raise PromptShieldError("Prompt Shields is not configured.")
            credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
            self.credential = credential
        return credential.get_token(self.config.entra_scope).token
