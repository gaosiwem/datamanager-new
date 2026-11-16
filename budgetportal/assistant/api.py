"""Public, safe orchestration endpoint for the Vulekamali assistant."""

import json
import ipaddress
import logging
import re
import uuid
from time import perf_counter
from dataclasses import replace
from decimal import Decimal

from django.core.cache import cache
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from budgetportal.assistant.answer_generator import AnswerGenerationError, AnswerGenerator
from budgetportal.assistant.cache import AssistantAnswerCache, AssistantCacheUnavailable
from budgetportal.assistant.foundry_guard import foundry_request_guard
from budgetportal.assistant.audited_outcome_availability import (
    AUDIT_PHASES,
    AuditedOutcomeAvailability,
)
from budgetportal.assistant.answerability import AnswerabilityChecker
from budgetportal.assistant.budget_query_engine import (
    NEEDS_BUDGET_PHASE,
    BudgetQueryEngine,
)
from budgetportal.assistant.document_retrieval import ApprovedDocumentRetriever
from budgetportal.assistant.entity_resolver import EntityResolver, ResolutionStatus
from budgetportal.assistant.foundry_client import FoundryClientError
from budgetportal.assistant.hybrid import HybridAnswerComposer
from budgetportal.assistant.output_validator import AnswerOutputValidator
from budgetportal.assistant.observability import AssistantObservability
from budgetportal.assistant.portal_data import PortalDataService
from budgetportal.assistant.portal_question_parser import PortalDataQuestionParser
from budgetportal.assistant.prompt_security import (
    BLOCKED_PROMPT_ATTACK_RESPONSE,
    PromptAttackScreen,
    PromptSecurityStatus,
)
from budgetportal.assistant.question_parser import (
    BudgetQuestionParser,
    QuestionParsingError,
)
from budgetportal.assistant.schemas import BudgetPhase, EntityType, GroupBy, Intent
from budgetportal.assistant.scope_control import Scope, ScopeClassifier, ScopeEnforcer
from budgetportal.assistant.router import AssistantRoute, AssistantRouter


logger = logging.getLogger(__name__)
OBSERVABILITY = AssistantObservability()
MAX_QUESTION_LENGTH = 2000
MAX_CONTEXT_VALUE_LENGTH = 200
MAX_REQUEST_BODY_BYTES = 4096
ALLOWED_CONTEXT_FIELDS = frozenset((
    "sphere",
    "department",
    "financial_year",
    "screen_path",
))
SCREEN_EXPLANATION_QUESTIONS = frozenset((
    "explain this page",
    "explain this screen",
    "what am i looking at",
))
# This prevents an intentionally broad name from creating an unbounded number
# of deterministic database queries.  Common cross-sphere department names
# have far fewer matches (for example, Social Development has ten).
MAX_AMBIGUOUS_DEPARTMENT_MATCHES = 20
PUBLIC_SCREEN_PATHS = (
    re.compile(r"^/$"),
    re.compile(r"^/(?:faq|about|resources|glossary|videos|learning-resources)/?$"),
    re.compile(r"^/budget-summary/\d{4}-\d{2}/?$"),
    re.compile(r"^/datasets(?:/[\w-]+)?/?$"),
)


class AssistantQueryService:
    """Coordinate assistant stages without logging user questions or secrets."""

    def __init__(
        self,
        prompt_attack_screen=None,
        scope_enforcer=None,
        question_parser=None,
        entity_resolver=None,
        query_engine=None,
        answerability_checker=None,
        answer_generator=None,
        output_validator=None,
        router=None,
        document_retriever=None,
        hybrid_composer=None,
        observability=None,
        audited_outcome_availability=None,
        portal_data_service=None,
        portal_question_parser=None,
    ):
        self.prompt_attack_screen = (
            prompt_attack_screen or PromptAttackScreen.from_settings()
        )
        # Foundry-backed components must be created only when their stage is
        # reached.  Constructing them here validates Azure credentials, which
        # used to make even fully deterministic requests (for example,
        # "Explain this page") fail before they were handled.
        self._scope_enforcer = scope_enforcer
        self._question_parser = question_parser
        self.entity_resolver = entity_resolver or EntityResolver()
        self.query_engine = query_engine or BudgetQueryEngine()
        self.answerability_checker = answerability_checker or AnswerabilityChecker()
        self._answer_generator = answer_generator
        self.output_validator = output_validator or AnswerOutputValidator()
        self.router = router or AssistantRouter()
        self.document_retriever = document_retriever or ApprovedDocumentRetriever()
        self.hybrid_composer = hybrid_composer or HybridAnswerComposer()
        self.observability = observability or OBSERVABILITY
        self.audited_outcome_availability = (
            audited_outcome_availability or AuditedOutcomeAvailability()
        )
        self.portal_data_service = portal_data_service or PortalDataService()
        self._portal_question_parser = portal_question_parser

    @property
    def scope_enforcer(self):
        if self._scope_enforcer is None:
            self._scope_enforcer = ScopeEnforcer(ScopeClassifier())
        return self._scope_enforcer

    @property
    def question_parser(self):
        if self._question_parser is None:
            self._question_parser = BudgetQuestionParser()
        return self._question_parser

    @property
    def answer_generator(self):
        if self._answer_generator is None:
            self._answer_generator = AnswerGenerator()
        return self._answer_generator

    @property
    def portal_question_parser(self):
        if self._portal_question_parser is None:
            self._portal_question_parser = PortalDataQuestionParser()
        return self._portal_question_parser

    def process(self, question, context=None, request_id=None):
        stage_started = perf_counter()
        screened = self.prompt_attack_screen.screen(question)
        self.observability.stage("prompt_attack_screening", stage_started)
        if screened.status == PromptSecurityStatus.BLOCKED_PROMPT_ATTACK:
            return {**BLOCKED_PROMPT_ATTACK_RESPONSE, "request_id": request_id}

        if self._is_screen_explanation_request(screened.question):
            return self._screen_explanation_response(context, request_id)

        stage_started = perf_counter()
        scope = self.scope_enforcer.enforce(screened.question)
        self.observability.stage("scope_classification", stage_started)
        if not scope.allowed:
            status = self._scope_status(scope)
            return {
                "status": status,
                "answer": scope.response,
                "request_id": request_id,
            }

        route = self.router.route(screened.question)
        if route == AssistantRoute.PORTAL_DATA:
            try:
                stage_started = perf_counter()
                query = self.portal_question_parser.parse(
                    screened.question, self._portal_data_route(screened.question)
                )
                self.observability.stage("portal_intent_parsing", stage_started)
            except (QuestionParsingError, FoundryClientError):
                return self._response(
                    "needs_clarification",
                    "Please ask a specific question about the selected Vulekamali dataset.",
                    request_id,
                )
            stage_started = perf_counter()
            response = self.portal_data_service.respond(query, screened.question)
            self.observability.stage("portal_data_query", stage_started)
            response["query"] = query.to_dict()
            response["request_id"] = request_id
            return response
        if route == AssistantRoute.DOCUMENT:
            return self._document_response(screened.question, request_id)
        hybrid_evidence = (
            self.document_retriever.retrieve(screened.question)
            if route == AssistantRoute.HYBRID
            else ()
        )

        try:
            stage_started = perf_counter()
            query = self.question_parser.parse(screened.question)
            self.observability.stage("intent_parsing", stage_started)
        except (QuestionParsingError, FoundryClientError):
            return self._response(
                "needs_clarification",
                "Please ask a specific Vulekamali budget question.",
                request_id,
            )

        query, page_context, context_error = self._apply_context(
            query, context, screened.question
        )
        if context_error:
            return self._response("needs_clarification", context_error, request_id)
        stage_started = perf_counter()
        validation = self.entity_resolver.validate_budget_query(query, page_context)
        self.observability.stage("entity_validation", stage_started)
        if validation.status == ResolutionStatus.AMBIGUOUS_ENTITY:
            audit_history = self._ambiguous_department_audit_history_response(
                query, validation, context, request_id, scope
            )
            if audit_history is not None:
                return audit_history
            expanded = self._ambiguous_department_amount_response(
                query, validation, request_id, scope
            )
            if expanded is not None:
                return expanded
            return self._response(
                "needs_clarification",
                "Please specify the Vulekamali entity more precisely.",
                request_id,
            )
        if validation.status != ResolutionStatus.RESOLVED:
            history_response = self._audited_outcome_history_response(
                self._canonicalise(query, validation), context, request_id, scope
            )
            if history_response is not None:
                return history_response
            availability_response = self._audited_outcome_availability_response(
                query, context, validation, request_id
            )
            if availability_response is not None:
                return availability_response
            return self._response(
                "data_not_found",
                "The requested information is not available in Vulekamali.",
                request_id,
            )

        query = self._canonicalise(query, validation)
        query = self._infer_ranking_dimension(query, screened.question)
        query = self._infer_main_appropriation_for_allocation(
            query, screened.question
        )
        catalogue_response = self._catalogue_response(
            screened.question, query, request_id, scope
        )
        if catalogue_response is not None:
            return catalogue_response
        stage_started = perf_counter()
        result = self.query_engine.execute(query)
        self.observability.stage("deterministic_query", stage_started)
        if result.status == NEEDS_BUDGET_PHASE:
            return self._response(
                "needs_clarification",
                "Please specify a budget phase, such as Main appropriation or Final Appropriation.",
                request_id,
            )
        stage_started = perf_counter()
        decision = self.answerability_checker.assess(query, result)
        self.observability.stage("answerability", stage_started)
        history_response = self._audited_outcome_history_response(
            query, context, request_id, scope, decision.status
        )
        if history_response is not None:
            return history_response
        availability_response = self._audited_outcome_availability_response(
            query, context, None, request_id, decision.status
        )
        if availability_response is not None:
            return availability_response
        stage_started = perf_counter()
        try:
            answer = self.answer_generator.generate(query, result, decision)
        except (AnswerGenerationError, FoundryClientError):
            # The result was already produced from validated, deterministic
            # Vulekamali data.  The output validator can safely render that
            # evidence without relying on a prose-generation request.
            answer = None
        self.observability.stage("answer_generation", stage_started)
        stage_started = perf_counter()
        output = self.output_validator.validate_or_fallback(query, result, answer)
        self.observability.stage("output_validation", stage_started)
        status = (
            "verified"
            if output.answer.status == "verified" and decision.status == "answerable"
            else self._answerability_status(decision.status)
        )
        answer_text, sources, explanation = (
            self.hybrid_composer.compose(output.answer, hybrid_evidence)
            if route == AssistantRoute.HYBRID
            else (output.answer.answer, output.answer.sources, None)
        )
        data = {
            "values": result.values,
            "calculations": result.calculations,
            "fallback_used": output.fallback_used,
        }
        if explanation is not None:
            data["explanation_status"] = explanation.status.value
        return {
            "status": status,
            "answer": answer_text,
            "query": query.to_dict(),
            "data": _json_safe(data),
            "sources": sources,
            "request_id": request_id,
            "_observability": {
                "scope": scope.decision.scope.value if scope.decision else None,
                "category": scope.decision.category if scope.decision else None,
                "confidence": scope.decision.confidence if scope.decision else None,
                "intent": query.intent.value,
                "fallback_used": output.fallback_used,
                "output_failure": bool(output.failure_reason),
            },
        }

    def _document_response(self, question, request_id):
        evidence = self.document_retriever.retrieve(question)
        if not evidence:
            return self._response(
                "data_not_found",
                "No approved Vulekamali information is available for that question.",
                request_id,
            )
        item = evidence[0]
        source = {
            "title": item.title,
            "source": item.source,
            "financial_year": item.financial_year,
            "document_type": item.document_type,
            "url": item.url,
            "page_section": item.page_section,
        }
        answer = item.chunk_text
        if len(answer) > 600:
            try:
                answer = self.answer_generator.summarise_document(question, answer)
            except (AnswerGenerationError, FoundryClientError):
                answer = self._short_document_answer(answer)
        return {
            "status": "verified",
            "answer": answer,
            "query": {"route": AssistantRoute.DOCUMENT.value},
            "data": {
                "evidence": [{"title": item.title, "page_section": item.page_section}]
            },
            "sources": (source,),
            "request_id": request_id,
        }

    def _audited_outcome_availability_response(
        self, query, context, validation, request_id, answerability_status=None
    ):
        """Explain the two-year audit-data lag without changing source years."""
        context = context or {}
        selected_year = context.get("financial_year") or query.financial_year
        if not selected_year or not self._is_audit_request(query):
            return None
        phase_failed = validation and validation.failed_field in {
            "budget_phase", "comparison_phase"
        }
        if not phase_failed and answerability_status not in {
            "insufficient_data", "unsupported"
        }:
            return None
        years = self.audited_outcome_availability.available_for(
            selected_year, context.get("sphere")
        )
        if not years:
            return None
        return {
            "status": "data_not_found",
            "answer": (
                "Audited outcomes are not available for {}. For the selected {} budget, "
                "audited-outcome data is available from {} downward: {}."
            ).format(selected_year, selected_year, years[0], ", ".join(years)),
            "data": {
                "audited_outcome_availability": {
                    "selected_financial_year": selected_year,
                    "available_financial_years": years,
                }
            },
            "request_id": request_id,
        }

    def _audited_outcome_history_response(
        self, query, context, request_id, scope, answerability_status=None
    ):
        """Return actual audited values for the valid historical source years.

        A selected current budget year is a display context.  It must never be
        used to relabel an older audited outcome.  This path is intentionally
        limited to a direct audit-phase request; an underspending calculation
        still requires matching Final Appropriation and Audit Outcome records
        for the same source year.
        """
        context = context or {}
        selected_year = context.get("financial_year") or query.financial_year
        if (
            not selected_year
            or query.budget_phase is None
            or query.budget_phase.value not in AUDIT_PHASES
            or answerability_status not in (None, "insufficient_data", "unsupported")
        ):
            return None
        years = self.audited_outcome_availability.available_for(
            selected_year, context.get("sphere")
        )
        if not years:
            return None

        observations, sources = [], []
        # Prefer the source's historic ``Audit Outcome`` label where both
        # labels exist, then use ``Audited outcome`` only if that is the sole
        # published representation for the exact source year.
        source_phases = (BudgetPhase.AUDIT_OUTCOME, BudgetPhase.AUDITED_OUTCOME)
        for year in years:
            for phase in source_phases:
                source_query = replace(
                    query,
                    intent=Intent.AMOUNT_LOOKUP,
                    financial_year=year,
                    budget_phase=phase,
                    comparison_year=None,
                    comparison_phase=None,
                )
                result = self.query_engine.execute(source_query)
                decision = self.answerability_checker.assess(source_query, result)
                if decision.status != "answerable" or not result.values:
                    continue
                amount = result.values[0].get("amount")
                if amount is None:
                    continue
                observations.append(
                    {
                        "financial_year": year,
                        "budget_phase": phase.value,
                        "amount": amount,
                    }
                )
                sources.extend(result.source_metadata)
                break
        if not observations:
            return None

        answer = (
            "Audited outcomes are published about two financial years after the budget year. "
            "For the selected {} budget, the verified audited-outcome data is: {}. "
            "Each amount is labelled with its actual source financial year."
        ).format(
            selected_year,
            "; ".join(
                "{} ({}): {}".format(
                    item["financial_year"],
                    item["budget_phase"],
                    self._format_amount(item["amount"]),
                )
                for item in observations
            ),
        )
        return {
            "status": "verified",
            "answer": answer,
            "query": query.to_dict(),
            "data": _json_safe(
                {
                    "values": observations,
                    "calculations": {},
                    "audited_outcome_availability": {
                        "selected_financial_year": selected_year,
                        "available_financial_years": years,
                    },
                    "fallback_used": True,
                }
            ),
            "sources": _json_safe(sources),
            "request_id": request_id,
            "_observability": {
                "scope": scope.decision.scope.value if scope.decision else None,
                "category": scope.decision.category if scope.decision else None,
                "confidence": scope.decision.confidence if scope.decision else None,
                "intent": Intent.AMOUNT_LOOKUP.value,
                "fallback_used": True,
                "output_failure": False,
            },
        }

    @staticmethod
    def _is_audit_request(query):
        return query.intent == Intent.VARIANCE_ANALYSIS or any(
            phase is not None and phase.value in AUDIT_PHASES
            for phase in (query.budget_phase, query.comparison_phase)
        )

    def _catalogue_response(self, question, query, request_id, scope):
        """Answer requests for published column values without an amount phase."""
        if query.budget_phase is not None:
            return None
        normalized_question = " ".join(question.casefold().split())
        if not re.search(r"\b(?:what|which|list|show)\b", normalized_question):
            return None
        if re.search(r"\b(?:how much|allocated|appropriat|spend|expenditure)\b", normalized_question):
            return None
        catalogue_fields = (
            (r"\bsubprogrammes?\b", "subprogramme", "Subprogrammes"),
            (r"\bprogrammes?\b", "programme", "Programmes"),
            (r"\beconomic classifications?\b", "economicClassification2", "Economic classifications"),
            (r"\bfunction groups?\b", "functionGroup1", "Function groups"),
        )
        match = next(
            (item for item in catalogue_fields if re.search(item[0], normalized_question)),
            None,
        )
        if match is None:
            return None
        _, field, title = match
        values = self.query_engine.catalogue_values(query, field)
        if not values:
            return self._response(
                "data_not_found",
                "No {} are available for the selected Vulekamali filters.".format(title.casefold()),
                request_id,
            )
        department = " for {}".format(query.department) if query.department else ""
        answer = "{}{} for {}: {}.".format(
            title, department, query.financial_year, "; ".join(values)
        )
        return {
            "status": "verified",
            "answer": answer,
            "query": query.to_dict(),
            "data": {"values": [{"entity": value} for value in values], "calculations": {}},
            "sources": [],
            "request_id": request_id,
            "_observability": {
                "scope": scope.decision.scope.value if scope.decision else None,
                "category": scope.decision.category if scope.decision else None,
                "confidence": scope.decision.confidence if scope.decision else None,
                "intent": query.intent.value,
                "fallback_used": True,
                "output_failure": False,
            },
        }

    @staticmethod
    def _infer_main_appropriation_for_allocation(query, question):
        """Treat an unspecified allocation as a Main appropriation request."""
        if query.budget_phase is not None:
            return query
        if query.intent not in (
            Intent.AMOUNT_LOOKUP,
            Intent.RANKING,
            Intent.COMPARISON,
            Intent.TREND_ANALYSIS,
            Intent.PERCENTAGE_CHANGE,
        ):
            return query
        if re.search(r"\b(?:allocation|allocated|appropriated)\b", question, re.IGNORECASE):
            return replace(query, budget_phase=BudgetPhase.MAIN_APPROPRIATION)
        return query

    @staticmethod
    def _infer_ranking_dimension(query, question):
        """Make explicit highest/top column questions deterministic rankings."""
        normalized_question = question.casefold()
        if not re.search(r"\b(?:highest|largest|top|most)\b", normalized_question):
            return query
        dimensions = (
            (r"\bsubprogrammes?\b", GroupBy.SUBPROGRAMME),
            (r"\bprogrammes?\b", GroupBy.PROGRAMME),
            (r"\beconomic classifications?\b", GroupBy.ECONOMIC_CLASSIFICATION_2),
            (r"\bfunction groups?\b", GroupBy.FUNCTION_GROUP),
        )
        group_by = next(
            (dimension for pattern, dimension in dimensions if re.search(pattern, normalized_question)),
            None,
        )
        if group_by is None:
            return query
        values = {
            "intent": Intent.RANKING,
            "group_by": group_by,
            "limit": query.limit or 1,
        }
        if query.entity_type is None:
            if re.search(r"\bnational\b", normalized_question):
                values["entity_type"] = EntityType.NATIONAL
            elif re.search(r"\bprovincial\b", normalized_question):
                values["entity_type"] = EntityType.PROVINCIAL
        return replace(query, **values)

    def _ambiguous_department_amount_response(
        self, query, validation, request_id, scope
    ):
        """Return separate values for a safely bounded ambiguous department.

        This deliberately applies only to an ordinary amount lookup with an
        explicit phase.  We do not extend the convenience to comparisons,
        rankings, programmes, or subprogrammes, where choosing a cross-sphere
        interpretation could change the meaning of the calculation.
        """
        if (
            validation.failed_field != "department"
            or query.intent != Intent.AMOUNT_LOOKUP
            or query.budget_phase is None
            or query.programme
            or query.subprogramme
        ):
            return None
        resolution = validation.resolved.get("department")
        candidates = getattr(resolution, "candidate_entities", ()) if resolution else ()
        if not candidates or len(candidates) > MAX_AMBIGUOUS_DEPARTMENT_MATCHES:
            return None

        rows, sources = [], []
        for department in candidates:
            government = department.government
            is_provincial = government.sphere.slug == "provincial"
            candidate_query = replace(
                query,
                department=department.name,
                province=government.name if is_provincial else None,
                entity_type=(
                    EntityType.PROVINCIAL if is_provincial else EntityType.NATIONAL
                ),
            )
            result = self.query_engine.execute(candidate_query)
            decision = self.answerability_checker.assess(candidate_query, result)
            label = self._department_label(department)
            amount = (
                result.values[0].get("amount")
                if decision.status == "answerable" and result.values
                else None
            )
            rows.append(
                {
                    "department": department.name,
                    "sphere": government.sphere.slug,
                    "province": government.name if is_provincial else None,
                    "label": label,
                    "amount": amount,
                    "has_matching_data": amount is not None,
                }
            )
            if amount is not None:
                for source in result.source_metadata:
                    sources.append(
                        {**source, "department": department.name, "label": label}
                    )

        if not rows:
            return self._response(
                "data_not_found",
                "The requested information is not available in Vulekamali.",
                request_id,
            )
        rows.sort(key=lambda row: (row["sphere"], row["province"] or "", row["department"]))
        answer = "Matching Vulekamali departments for {} ({}): {}. Values are shown separately and are not combined.".format(
            query.financial_year,
            query.budget_phase.value,
            "; ".join(
                "{}: {}".format(
                    row["label"],
                    self._format_amount(row["amount"])
                    if row["amount"] is not None
                    else "No matching data",
                )
                for row in rows
            ),
        )
        return {
            "status": "verified",
            "answer": answer,
            "query": query.to_dict(),
            "data": _json_safe(
                {"values": rows, "calculations": {}, "fallback_used": True}
            ),
            "sources": _json_safe(sources),
            "request_id": request_id,
            "_observability": {
                "scope": scope.decision.scope.value if scope.decision else None,
                "category": scope.decision.category if scope.decision else None,
                "confidence": scope.decision.confidence if scope.decision else None,
                "intent": query.intent.value,
                "fallback_used": True,
                "output_failure": False,
            },
        }

    def _ambiguous_department_audit_history_response(
        self, query, validation, context, request_id, scope
    ):
        """Return each matching department's latest published audit outcome.

        Ambiguity must not bypass the audit-outcome availability rule.  A
        question such as ``Health audited outcome for 2026-27`` has no current
        audit value by design, but it can still be answered separately for
        National and every provincial Health department using the published
        historical source year.
        """
        if (
            validation.failed_field != "department"
            or query.intent != Intent.AMOUNT_LOOKUP
            or query.budget_phase is None
            or query.budget_phase.value not in AUDIT_PHASES
            or query.programme
            or query.subprogramme
        ):
            return None
        resolution = validation.resolved.get("department")
        candidates = getattr(resolution, "candidate_entities", ()) if resolution else ()
        if not candidates or len(candidates) > MAX_AMBIGUOUS_DEPARTMENT_MATCHES:
            return None

        selected_year = (context or {}).get("financial_year") or query.financial_year
        years = self.audited_outcome_availability.available_for(selected_year)
        if not years:
            return None

        rows, sources = [], []
        source_phases = (BudgetPhase.AUDIT_OUTCOME, BudgetPhase.AUDITED_OUTCOME)
        for department in candidates:
            government = department.government
            is_provincial = government.sphere.slug == "provincial"
            label = self._department_label(department)
            observation = None
            for year in years:
                for phase in source_phases:
                    source_query = replace(
                        query,
                        department=department.name,
                        province=government.name if is_provincial else None,
                        entity_type=(
                            EntityType.PROVINCIAL
                            if is_provincial
                            else EntityType.NATIONAL
                        ),
                        financial_year=year,
                        budget_phase=phase,
                        comparison_year=None,
                        comparison_phase=None,
                    )
                    result = self.query_engine.execute(source_query)
                    decision = self.answerability_checker.assess(source_query, result)
                    if decision.status != "answerable" or not result.values:
                        continue
                    amount = result.values[0].get("amount")
                    if amount is None:
                        continue
                    observation = {
                        "financial_year": year,
                        "budget_phase": phase.value,
                        "amount": amount,
                    }
                    for source in result.source_metadata:
                        sources.append(
                            {**source, "department": department.name, "label": label}
                        )
                    break
                if observation is not None:
                    break
            rows.append(
                {
                    "department": department.name,
                    "sphere": government.sphere.slug,
                    "province": government.name if is_provincial else None,
                    "label": label,
                    "amount": observation["amount"] if observation else None,
                    "financial_year": observation["financial_year"] if observation else None,
                    "budget_phase": observation["budget_phase"] if observation else None,
                    "has_matching_data": observation is not None,
                }
            )

        rows.sort(key=lambda row: (row["sphere"], row["province"] or "", row["department"]))
        has_data = any(row["has_matching_data"] for row in rows)
        answer = (
            "Audited outcomes are published about two financial years after the budget year. "
            "Results for matching departments for the selected {} budget are shown separately below, "
            "with each result labelled by its actual source financial year."
        ).format(selected_year)
        return {
            "status": "verified" if has_data else "data_not_found",
            "answer": answer,
            "query": query.to_dict(),
            "data": _json_safe(
                {
                    "values": rows,
                    "calculations": {},
                    "audited_outcome_availability": {
                        "selected_financial_year": selected_year,
                        "available_financial_years": years,
                    },
                    "fallback_used": True,
                }
            ),
            "sources": _json_safe(sources),
            "request_id": request_id,
            "_observability": {
                "scope": scope.decision.scope.value if scope.decision else None,
                "category": scope.decision.category if scope.decision else None,
                "confidence": scope.decision.confidence if scope.decision else None,
                "intent": Intent.AMOUNT_LOOKUP.value,
                "fallback_used": True,
                "output_failure": False,
            },
        }

    @staticmethod
    def _department_label(department):
        government = department.government
        if government.sphere.slug == "provincial":
            return "{} — {}".format(government.name, department.name)
        return "National — {}".format(department.name)

    @staticmethod
    def _format_amount(amount):
        value = Decimal(amount)
        rendered = format(value, ",f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return "R{}".format(rendered or "0")

    @staticmethod
    def _short_document_answer(text, maximum=600):
        """Keep a document response readable if the LLM service is unavailable."""
        if len(text) <= maximum:
            return text
        sentence_end = text.rfind(".", 0, maximum)
        return text[:sentence_end if sentence_end > 0 else maximum].rstrip() + "…"

    def _apply_context(self, query, context, question):
        context = context or {}
        explicit_department = query.department
        explicit_comparison_department = query.comparison_department
        effective_year = query.financial_year or context.get("financial_year")
        if effective_year is None:
            return query, {}, "Please specify a financial year such as 2024-25."
        year = self.entity_resolver.resolve_financial_year(effective_year)
        if year.status != ResolutionStatus.RESOLVED:
            return (
                query,
                {},
                "The requested financial year is not available in Vulekamali.",
            )
        if (
            context.get("financial_year")
            and context["financial_year"] != effective_year
        ):
            context_year = self.entity_resolver.resolve_financial_year(
                context["financial_year"]
            )
            if context_year.status != ResolutionStatus.RESOLVED:
                return (
                    query,
                    {},
                    "The supplied page context is not available in Vulekamali.",
                )
        query = replace(query, financial_year=year.canonical_name)
        page_context = {}
        context_sphere = None
        if context.get("sphere"):
            sphere = self.entity_resolver.resolve_sphere(context["sphere"], year.entity)
            if sphere.status != ResolutionStatus.RESOLVED:
                return query, {}, "Please specify a valid government sphere."
            context_sphere = sphere.entity

        context_department = None
        if context.get("department"):
            department = self.entity_resolver.resolve_department(
                context["department"], year.entity, sphere=context_sphere
            )
            if department.status != ResolutionStatus.RESOLVED:
                return (
                    query,
                    {},
                    "Please specify an unambiguous valid department context.",
                )
            context_department = department

        if context_department and (
            explicit_department is None
            or self._is_context_reference(explicit_department)
        ):
            query = replace(query, department=context_department.canonical_name)
            if context_sphere is not None:
                page_context["sphere"] = context_sphere
        if context_department and self._is_context_reference(
            explicit_comparison_department
        ):
            query = replace(
                query, comparison_department=context_department.canonical_name
            )
        return query, page_context, None

    @staticmethod
    def _is_screen_explanation_request(question):
        return question.strip().casefold().rstrip("?.!") in SCREEN_EXPLANATION_QUESTIONS

    def _screen_explanation_response(self, context, request_id):
        """Explain an allowlisted public screen without trusting browser text."""
        context = context or {}
        path = context.get("screen_path", "")
        if not _is_public_screen_path(path):
            return self._response(
                "needs_clarification",
                "Page explanations are available only for supported public Vulekamali pages.",
                request_id,
            )
        labels = {
            "/": "the Vulekamali home page",
            "/faq": "the Vulekamali frequently asked questions page",
            "/about": "the Vulekamali About page",
            "/resources": "the Vulekamali resources page",
            "/glossary": "the Vulekamali glossary",
            "/videos": "the Vulekamali videos page",
            "/learning-resources": "the Vulekamali learning resources page",
        }
        title = labels.get(path.rstrip("/") or "/", "a public Vulekamali page")
        answer = "You are viewing {}. Use the page controls and links to explore the published information shown.".format(title)
        return {
            "status": "verified",
            "answer": answer,
            "query": {"route": "screen_explanation"},
            "sources": (),
            "request_id": request_id,
        }

    @staticmethod
    def _portal_data_route(question):
        lowered = question.casefold()
        if "public entit" in lowered:
            return "public_entity"
        if "infrastructure" in lowered:
            return "infrastructure"
        return "performance"

    @staticmethod
    def _is_context_reference(value):
        return isinstance(value, str) and value.strip().casefold() in {
            "this",
            "this department",
            "current department",
            "current page",
        }

    @staticmethod
    def _canonicalise(query, validation):
        values = {}
        for field_name in (
            "department",
            "comparison_department",
            "province",
            "comparison_province",
            "programme",
            "subprogramme",
            "financial_year",
            "comparison_year",
        ):
            resolution = validation.resolved.get(field_name)
            if resolution and resolution.canonical_name:
                values[field_name] = resolution.canonical_name
        return replace(query, **values)

    @staticmethod
    def _scope_status(scope):
        if scope.decision and scope.decision.scope == Scope.OUT_OF_SCOPE:
            return "out_of_scope"
        return "needs_clarification"

    @staticmethod
    def _answerability_status(status):
        return (
            "unsupported_vulekamali_query"
            if status == "unsupported"
            else "data_not_found"
        )

    @staticmethod
    def _response(status, answer, request_id):
        return {"status": status, "answer": answer, "request_id": request_id}


def _validate_payload(request):
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_REQUEST_BODY_BYTES:
            return None, None, "Request body is too large."
    except (TypeError, ValueError):
        return None, None, "Request body is invalid."
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, None, "Request body must be valid JSON."
    if not isinstance(payload, dict) or set(payload) - {"question", "context"}:
        return None, None, "Request must contain only question and optional context."
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        return None, None, "question must be a non-empty string."
    if len(question) > MAX_QUESTION_LENGTH:
        return None, None, "question is too long."
    context = payload.get("context", {})
    if not isinstance(context, dict) or set(context) - ALLOWED_CONTEXT_FIELDS:
        return None, None, "context contains unsupported fields."
    for key, value in context.items():
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value)
            > MAX_CONTEXT_VALUE_LENGTH
        ):
            return (
                None,
                None,
                "context values must be non-empty strings of a safe length.",
            )
    return (
        question.strip(),
        {key: value.strip() for key, value in context.items()},
        None,
    )


def _rate_limited(request):
    # The client IP comes only from IIS when IIS is the loopback peer.
    limit = getattr(settings, "ASSISTANT_RATE_LIMIT_PER_MINUTE", 30)
    key = "vulekamali-assistant-rate:{}".format(_trusted_client_ip(request))
    try:
        if cache.add(key, 1, timeout=60):
            return False
        return cache.incr(key) > limit
    except Exception as error:
        logger.warning(
            "Assistant rate-limit cache unavailable error_type=%s",
            error.__class__.__name__,
        )
        # A paid public endpoint must fail closed if its shared limiter fails.
        return True


def _trusted_client_ip(request):
    peer = request.META.get("REMOTE_ADDR", "")
    if peer in ("127.0.0.1", "::1"):
        forwarded = request.META.get("HTTP_X_IIS_CLIENT_IP", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            return peer
    return peer


def _is_public_screen_path(path):
    return isinstance(path, str) and any(pattern.fullmatch(path) for pattern in PUBLIC_SCREEN_PATHS)


@csrf_exempt
@require_POST
def assistant_query(request):
    request_id = uuid.uuid4().hex
    request_started = perf_counter()
    question, context, error = _validate_payload(request)
    if error:
        OBSERVABILITY.request(
            request_id, "error", round((perf_counter() - request_started) * 1000, 2)
        )
        logger.info(
            "Assistant request rejected request_id=%s reason=input_validation",
            request_id,
        )
        return JsonResponse(
            {"status": "error", "answer": error, "request_id": request_id}, status=400
        )
    if _rate_limited(request):
        OBSERVABILITY.request(
            request_id, "error", round((perf_counter() - request_started) * 1000, 2)
        )
        logger.warning("Assistant request rate limited request_id=%s", request_id)
        return JsonResponse(
            {
                "status": "error",
                "answer": "Too many requests. Please try again later.",
                "request_id": request_id,
            },
            status=429,
        )
    # Prompt screening is deliberately before cache lookup: cached public
    # answers must never bypass the attack boundary.
    screen = PromptAttackScreen.from_settings().screen(question)
    if screen.status == PromptSecurityStatus.BLOCKED_PROMPT_ATTACK:
        return JsonResponse(
            {**BLOCKED_PROMPT_ATTACK_RESPONSE, "request_id": request_id},
            status=400,
        )
    safe_question = screen.question
    answer_cache = AssistantAnswerCache()
    cache_key = None
    try:
        if answer_cache.eligible(safe_question, context):
            cache_key = answer_cache.key(safe_question, context)
            claim = answer_cache.claim(cache_key)
            if claim.response is not None:
                response = dict(claim.response)
                response["request_id"] = request_id
                response["cache_hit"] = True
                return JsonResponse(response, encoder=DjangoJSONEncoder)
            if not claim.lock_token:
                response = answer_cache.wait_for_result(cache_key)
                if response is None:
                    return JsonResponse(
                        {"status": "error", "answer": "The assistant is busy. Please try again shortly.", "request_id": request_id},
                        status=503,
                    )
                response = dict(response)
                response["request_id"] = request_id
                response["cache_hit"] = True
                return JsonResponse(response, encoder=DjangoJSONEncoder)
        else:
            claim = None
        with foundry_request_guard():
            response = AssistantQueryService().process(safe_question, context, request_id)
        if cache_key is not None:
            answer_cache.store(cache_key, response)
            answer_cache.release(cache_key, claim.lock_token)
        event = response.pop("_observability", {})
        response["cache_hit"] = False
        OBSERVABILITY.request(
            request_id,
            response["status"],
            round((perf_counter() - request_started) * 1000, 2),
            **event
        )
        logger.info(
            "Assistant request completed request_id=%s status=%s",
            request_id,
            response["status"],
        )
        return JsonResponse(response, encoder=DjangoJSONEncoder)
    except AssistantCacheUnavailable:
        return JsonResponse(
            {"status": "error", "answer": "The assistant is temporarily unavailable.", "request_id": request_id},
            status=503,
        )
    except Exception as error:
        if isinstance(error, FoundryClientError):
            OBSERVABILITY.foundry_failure(request_id, "assistant_processing")
        OBSERVABILITY.request(
            request_id, "error", round((perf_counter() - request_started) * 1000, 2)
        )
        logger.error(
            "Assistant request failed request_id=%s error_type=%s",
            request_id,
            error.__class__.__name__,
        )
        return JsonResponse(
            {
                "status": "error",
                "answer": "The assistant is temporarily unavailable.",
                "request_id": request_id,
            },
            status=503,
        )
    finally:
        if cache_key is not None and 'claim' in locals() and claim.lock_token:
            try:
                answer_cache.release(cache_key, claim.lock_token)
            except AssistantCacheUnavailable:
                pass


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value
