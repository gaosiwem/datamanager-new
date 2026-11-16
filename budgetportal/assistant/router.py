"""Route structured financial, approved-document, and hybrid questions."""

import re
from enum import Enum


class AssistantRoute(str, Enum):
    STRUCTURED_FINANCIAL = "structured_financial"
    DOCUMENT = "document"
    HYBRID = "hybrid"
    PORTAL_DATA = "portal_data"


class AssistantRouter:
    STRUCTURED = re.compile(
        r"\b(how much|what was|allocated|appropriation|compare|largest|rank|trend|percentage|underspend|overspend|expenditure)\b",
        re.I,
    )
    EXPLANATION = re.compile(
        r"\b(what is|define|meaning of|why|reason|explain|how do i)\b", re.I
    )
    PUBLIC_ENTITY = re.compile(r"\bpublic\s+entit(?:y|ies)\b", re.I)
    INFRASTRUCTURE = re.compile(r"\binfrastructure(?:\s+project)?\b", re.I)
    PERFORMANCE = re.compile(r"\bperformance(?:\s+indicator|\s+data|\s+monitoring)?\b", re.I)

    def route(self, question):
        if self.PUBLIC_ENTITY.search(question) or self.INFRASTRUCTURE.search(question) or self.PERFORMANCE.search(question):
            return AssistantRoute.PORTAL_DATA
        structured = bool(self.STRUCTURED.search(question))
        explanatory = bool(self.EXPLANATION.search(question))
        if (
            explanatory
            and ("why" in question.casefold() or "reason" in question.casefold())
            and structured
        ):
            return AssistantRoute.HYBRID
        if re.match(
            r"\s*(?:what\s+is|what\s+(?:does|do)\b.+?\bmean|define|meaning\s+of)\b",
            question,
            re.I,
        ):
            return AssistantRoute.DOCUMENT
        if explanatory and not structured:
            return AssistantRoute.DOCUMENT
        return AssistantRoute.STRUCTURED_FINANCIAL
