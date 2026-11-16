"""Safe composition of deterministic financial results and approved evidence."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from budgetportal.assistant.answer_generator import AssistantAnswer
from budgetportal.assistant.document_retrieval import RetrievedEvidence


class ExplanationStatus(str, Enum):
    EXPLAINED = "explained"
    PARTIALLY_EXPLAINED = "partially_explained"
    NO_EXPLANATION = "no_explanation"
    CONFLICTING_EXPLANATIONS = "conflicting_explanations"


@dataclass(frozen=True)
class HybridExplanationDecision:
    status: ExplanationStatus
    evidence: Sequence[RetrievedEvidence]


class HybridAnswerComposer:
    """Attach only explicitly supported documentary explanation to data facts."""

    EXPLANATION_MARKERS = re.compile(
        r"\b(because|due to|attributable to|resulted from|caused by|as a result of)\b",
        re.I,
    )

    def assess(
        self, evidence: Sequence[RetrievedEvidence]
    ) -> HybridExplanationDecision:
        evidence = tuple(evidence)
        if not evidence:
            return HybridExplanationDecision(ExplanationStatus.NO_EXPLANATION, evidence)
        text = " ".join(item.chunk_text.casefold() for item in evidence)
        if "increased" in text and "decreased" in text:
            return HybridExplanationDecision(
                ExplanationStatus.CONFLICTING_EXPLANATIONS, evidence
            )
        if any(self.EXPLANATION_MARKERS.search(item.chunk_text) for item in evidence):
            return HybridExplanationDecision(ExplanationStatus.EXPLAINED, evidence)
        return HybridExplanationDecision(
            ExplanationStatus.PARTIALLY_EXPLAINED, evidence
        )

    def compose(self, financial_answer: AssistantAnswer, evidence):
        decision = self.assess(evidence)
        sections = ["What the data shows\n{}".format(financial_answer.answer)]
        if decision.status == ExplanationStatus.EXPLAINED:
            excerpts = "\n".join(self._citation(item) for item in decision.evidence)
            sections.append(
                "What approved Vulekamali/National Treasury documents explain\n{}".format(
                    excerpts
                )
            )
        elif decision.status == ExplanationStatus.PARTIALLY_EXPLAINED:
            excerpts = "\n".join(self._citation(item) for item in decision.evidence)
            sections.append(
                "What approved Vulekamali/National Treasury documents explain\nApproved documents provide related context, but do not state a complete verified explanation for the change.\n{}".format(
                    excerpts
                )
            )
        elif decision.status == ExplanationStatus.CONFLICTING_EXPLANATIONS:
            excerpts = "\n".join(self._citation(item) for item in decision.evidence)
            sections.append(
                "What approved Vulekamali/National Treasury documents explain\nApproved documents contain potentially conflicting statements. No single explanation is asserted.\n{}".format(
                    excerpts
                )
            )
        else:
            sections.append(
                "What approved Vulekamali/National Treasury documents explain\nNo approved document evidence was found that explains the change. The assistant will not infer a reason."
            )
        sources = tuple(financial_answer.sources) + tuple(
            self._source(item) for item in decision.evidence
        )
        return "\n\n".join(sections), sources, decision

    @staticmethod
    def _citation(item):
        location = ", {}".format(item.page_section) if item.page_section else ""
        return "- {}{}: {}".format(item.title, location, item.chunk_text[:600])

    @staticmethod
    def _source(item):
        return {
            "title": item.title,
            "source": item.source,
            "financial_year": item.financial_year,
            "document_type": item.document_type,
            "url": item.url,
            "page_section": item.page_section,
        }
