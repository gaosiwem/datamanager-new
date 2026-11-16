"""Prompt-attack screening with deterministic Vulekamali-safe outcomes."""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.conf import settings


logger = logging.getLogger(__name__)

BLOCKED_PROMPT_ATTACK_RESPONSE = {
    "status": "blocked_prompt_attack",
    "answer": "I can only assist with questions related to Vulekamali.",
}

ATTACK_PATTERNS = (
    re.compile(
        r"\bignore\s+(?:all\s+)?(?:previous|prior|your)?\s*instructions?\b",
        re.I,
    ),
    re.compile(r"\bignore\s+(?:your\s+)?(?:rules?|restrictions?)\b", re.I),
    re.compile(r"\byou\s+are\s+no\s+longer\b", re.I),
    re.compile(
        r"\b(?:reveal|show|print|display)\b.{0,40}\b(?:system\s+prompt|developer\s+instructions?)\b",
        re.I,
    ),
    re.compile(r"\bpretend\b.{0,50}\brestrictions?\b", re.I),
    re.compile(r"\bbypass\b.{0,40}\b(?:rules?|restrictions?)\b", re.I),
    re.compile(r"\bauthori[sz]ed\s+by\s+national\s+treasury\b", re.I),
    re.compile(
        r"\b(?:environment\s+variables?|azure\s+credentials?|api\s+keys?|tokens?|database\s+passwords?)\b",
        re.I,
    ),
    re.compile(r"\bexecute\s+(?:arbitrary\s+)?sql\b", re.I),
    re.compile(r"\b(?:run|execute|write)\b.{0,30}\bpython(?:\s+code)?\b", re.I),
)

# These are not prompt attacks by themselves.  They are recognised only when
# appended after a complete, safely separable Vulekamali question so that the
# valid component can proceed without allowing unrelated knowledge to leak.
UNRELATED_SUFFIX_PATTERNS = (
    re.compile(r"\b(?:what is|tell me)\s+the\s+capital\s+of\b", re.I),
    re.compile(r"\bteach me\s+(?:python|java)\b", re.I),
    re.compile(r"\b(?:medical|personal)\s+advice\b", re.I),
    re.compile(r"\b(?:chicken\s+)?recipe\b", re.I),
    re.compile(r"\bwindows server\b", re.I),
    re.compile(r"\bwrite me\s+a\s+cv\b", re.I),
    re.compile(r"\bwho won yesterday\b", re.I),
    re.compile(r"\banswer anything i ask\b", re.I),
)


class PromptSecurityStatus(str, Enum):
    CLEAN = "clean"
    SANITIZED = "sanitized"
    BLOCKED_PROMPT_ATTACK = "blocked_prompt_attack"


class PromptShieldError(Exception):
    """A configured external prompt shield could not safely assess input."""


@dataclass(frozen=True)
class PromptSecurityDecision:
    status: PromptSecurityStatus
    question: Optional[str]
    response: Optional[dict]


@dataclass(frozen=True)
class AssistantInputDecision:
    """The application boundary result before any assistant processing begins."""

    status: str
    question: Optional[str]
    answer: Optional[str]


class PromptAttackScreen:
    """Run before scope classification and never return attack instructions."""

    def __init__(self, prompt_shield=None) -> None:
        self.prompt_shield = prompt_shield

    @classmethod
    def from_settings(cls):
        content_safety = getattr(settings, "AZURE_CONTENT_SAFETY", {})
        if not content_safety.get("enabled", False):
            return cls()
        from .prompt_shield import FoundryPromptShield

        return cls(prompt_shield=FoundryPromptShield())

    def screen(self, question: str) -> PromptSecurityDecision:
        if not isinstance(question, str) or not question.strip():
            return self._blocked()

        question = question.strip()
        match = self._first_attack(question)
        if match:
            safe_question = self._safe_prefix(question, match.start())
            if safe_question:
                return PromptSecurityDecision(
                    PromptSecurityStatus.SANITIZED, safe_question, None
                )
            return self._blocked()

        unrelated = self._first_unrelated_suffix(question)
        if unrelated:
            safe_question = self._safe_prefix(question, unrelated.start())
            if safe_question:
                return PromptSecurityDecision(
                    PromptSecurityStatus.SANITIZED, safe_question, None
                )

        if self.prompt_shield is not None:
            try:
                if self.prompt_shield.detect_attack(question):
                    return self._blocked()
            except PromptShieldError as error:
                logger.error(
                    "Prompt shield failed error_type=%s", error.__class__.__name__
                )
                return self._blocked()

        return PromptSecurityDecision(PromptSecurityStatus.CLEAN, question, None)

    @staticmethod
    def _first_attack(question: str):
        matches = [pattern.search(question) for pattern in ATTACK_PATTERNS]
        matches = [match for match in matches if match]
        return min(matches, key=lambda match: match.start()) if matches else None

    @staticmethod
    def _first_unrelated_suffix(question: str):
        matches = [pattern.search(question) for pattern in UNRELATED_SUFFIX_PATTERNS]
        matches = [match for match in matches if match]
        return min(matches, key=lambda match: match.start()) if matches else None

    @staticmethod
    def _safe_prefix(question: str, attack_start: int) -> Optional[str]:
        prefix = question[:attack_start].rstrip()
        boundary = re.search(r"(?:[?.;!]\s*|\s+(?:and\s+)?then\s*)$", prefix, re.I)
        if not boundary:
            return None
        safe_question = prefix[: boundary.start()].strip()
        return safe_question or None

    @staticmethod
    def _blocked() -> PromptSecurityDecision:
        return PromptSecurityDecision(
            PromptSecurityStatus.BLOCKED_PROMPT_ATTACK,
            None,
            dict(BLOCKED_PROMPT_ATTACK_RESPONSE),
        )


class AssistantInputGuard:
    """Apply prompt-attack protection before Vulekamali scope enforcement."""

    def __init__(self, prompt_attack_screen, scope_enforcer) -> None:
        self.prompt_attack_screen = prompt_attack_screen
        self.scope_enforcer = scope_enforcer

    def check(self, question: str) -> AssistantInputDecision:
        prompt_decision = self.prompt_attack_screen.screen(question)
        if prompt_decision.status == PromptSecurityStatus.BLOCKED_PROMPT_ATTACK:
            return AssistantInputDecision(
                status=BLOCKED_PROMPT_ATTACK_RESPONSE["status"],
                question=None,
                answer=BLOCKED_PROMPT_ATTACK_RESPONSE["answer"],
            )

        scope_decision = self.scope_enforcer.enforce(prompt_decision.question)
        if not scope_decision.allowed:
            return AssistantInputDecision(
                status="scope_blocked",
                question=None,
                answer=scope_decision.response,
            )
        return AssistantInputDecision(
            status="allowed",
            question=prompt_decision.question,
            answer=None,
        )
