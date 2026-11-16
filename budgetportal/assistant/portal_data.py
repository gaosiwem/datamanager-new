"""Deterministic answers for non-budget portal datasets.

These records have different schemas from the budget tables, so they are kept
out of ``BudgetQueryEngine``.  This adapter exposes only fields that are
published by the corresponding Vulekamali models.
"""

import re
from decimal import Decimal

from django.db.models import Sum

from budgetportal.models import InfrastructureProjectPart
from budgetportal.models.government import Department
from performance.models import Indicator
from public_entities.models import PublicEntity, PublicEntityExpenditure
from budgetportal.assistant.schemas import PortalDataQuery, PortalDataset, PortalIntent


class PortalDataService:
    """Answer Public Entity, infrastructure and performance requests safely."""

    def respond(self, query, original_question=None):
        """Execute a validated portal query using a dataset-specific adapter.

        ``original_question`` is retained for backwards-compatible callers;
        adapters use the validated query plan only.
        """
        if not isinstance(query, PortalDataQuery):
            raise TypeError("PortalDataService requires a PortalDataQuery.")
        if query.dataset == PortalDataset.PUBLIC_ENTITY:
            return self._public_entity(query)
        if query.dataset == PortalDataset.INFRASTRUCTURE:
            return self._infrastructure(query)
        return self._performance(query)

    @staticmethod
    def _normalise(value):
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @staticmethod
    def _source(title, url):
        return ({"title": title, "url": url},)

    @staticmethod
    def _amount(value):
        value = Decimal(value or 0)
        return "R{:,.0f}".format(value)

    def _unique_name_match(self, question, queryset, field="name"):
        normalised_question = self._normalise(question)
        matches = []
        for name in queryset.values_list(field, flat=True).distinct():
            normalised_name = self._normalise(name or "")
            if len(normalised_name) > 3 and normalised_name in normalised_question:
                matches.append(name)
        matches = sorted(set(matches), key=lambda name: len(self._normalise(name)), reverse=True)
        if len(matches) != 1:
            return None
        return matches[0]

    def _requested_phase(self, question, phases):
        normalised_question = self._normalise(question)
        for phase in phases:
            if self._normalise(phase) in normalised_question:
                return phase
        return None

    def _public_entity(self, query):
        if query.intent == PortalIntent.RANKING:
            return self._rank_public_entities(query)

        name = query.entity_name
        if not name:
            return {
                "status": "needs_clarification",
                "answer": "Public Entity data is available. Please specify the public entity name, for example a named entity and financial year.",
                "sources": self._source("Public entities", "/public-entities"),
            }
        year = query.financial_year
        entities = PublicEntity.objects.filter(name=name).select_related(
            "department", "government__sphere__financial_year"
        )
        if year:
            entities = entities.filter(government__sphere__financial_year__slug=year)
        entity = entities.order_by("-government__sphere__financial_year__slug").first()
        if entity is None:
            return {
                "status": "data_not_found",
                "answer": "The requested public entity is not available for the selected financial year.",
                "sources": self._source("Public entities", "/public-entities"),
            }
        entity_year = entity.get_financial_year().slug
        answer = "{} is a public entity associated with {} for {}.".format(
            entity.name, entity.department.name, entity_year
        )
        if entity.functiongroup1:
            answer += " Its function group is {}.".format(entity.functiongroup1)
        if query.intent == PortalIntent.AMOUNT_LOOKUP:
            spending = PublicEntityExpenditure.objects.filter(public_entity=entity)
            phases = list(
                spending.exclude(budget_phase__isnull=True).exclude(budget_phase="")
                .values_list("budget_phase", flat=True).distinct()
            )
            phase = self._requested_phase(query.budget_phase or "", phases)
            if phase:
                total = spending.filter(budget_phase=phase).aggregate(total=Sum("amount"))["total"]
                if total is not None:
                    answer += " The published {} amount is {}.".format(
                        phase, self._amount(total)
                    )
            elif len(phases) == 1:
                total = spending.aggregate(total=Sum("amount"))["total"]
                if total is not None:
                    answer += " The published {} amount is {}.".format(
                        phases[0], self._amount(total)
                    )
            elif phases:
                answer += " Available expenditure phases are: {}. Please specify one phase to avoid combining different measures.".format(
                    ", ".join(sorted(phases))
                )
        return {
            "status": "verified",
            "answer": answer,
            "sources": self._source(entity.name, entity.get_url_path()),
        }

    def _rank_public_entities(self, query):
        expenditures = PublicEntityExpenditure.objects.select_related(
            "public_entity__department",
            "public_entity__government__sphere__financial_year",
        )
        year = query.financial_year
        if year:
            expenditures = expenditures.filter(
                public_entity__government__sphere__financial_year__slug=year
            )
        else:
            year = expenditures.order_by(
                "-public_entity__government__sphere__financial_year__slug"
            ).values_list(
                "public_entity__government__sphere__financial_year__slug", flat=True
            ).first()
            if year:
                expenditures = expenditures.filter(
                    public_entity__government__sphere__financial_year__slug=year
                )

        if not year or not expenditures.exists():
            return {
                "status": "data_not_found",
                "answer": "No published public-entity expenditure data is available for that financial year.",
                "sources": self._source("Public entities", "/public-entities"),
            }

        phases = list(
            expenditures.exclude(budget_phase__isnull=True).exclude(budget_phase="")
            .values_list("budget_phase", flat=True).distinct()
        )
        phase = self._requested_phase(query.budget_phase or "", phases)
        # A dataset with one published measure is unambiguous.  This commonly
        # occurs for public entities, where a release may publish only MTEF
        # values.  Use it rather than asking the user to choose a non-existent
        # alternative, and always name the actual phase in the answer.
        if phase is None and len(phases) == 1:
            phase = phases[0]
        if not phase:
            return {
                "status": "needs_clarification",
                "answer": "Please specify a budget phase to rank public entities without combining different measures. Available phases are: {}.".format(
                    ", ".join(sorted(phases)) or "none"
                ),
                "sources": self._source("Public entities", "/public-entities"),
            }

        ranked = expenditures.filter(budget_phase=phase).values(
            "public_entity__name", "public_entity__department__name"
        ).annotate(total=Sum("amount")).order_by(
            "-total" if query.descending else "total", "public_entity__name"
        )[:query.limit]
        highest = ranked.first()
        if highest is None:
            return {
                "status": "data_not_found",
                "answer": "No public-entity amounts are available for {} in {}.".format(phase, year),
                "sources": self._source("Public entities", "/public-entities"),
            }

        return {
            "status": "verified",
            "answer": "The {} public entity for {} is {} ({}): {} ({}).".format(
                "highest" if query.descending else "lowest",
                year,
                highest["public_entity__name"],
                highest["public_entity__department__name"],
                self._amount(highest["total"]),
                phase,
            ),
            "sources": self._source("Public entities", "/public-entities"),
        }

    def _infrastructure(self, query):
        if query.intent == PortalIntent.RANKING:
            return self._rank_infrastructure(query)
        name = query.entity_name
        if not name:
            return {
                "status": "needs_clarification",
                "answer": "Infrastructure project data is available. Please specify the project name and, where relevant, the financial year.",
                "sources": self._source("Infrastructure projects", "/infrastructure-projects/"),
            }
        source_year = query.financial_year[:4] if query.financial_year else None
        projects = InfrastructureProjectPart.objects.filter(project_name=name)
        if source_year:
            projects = projects.filter(financial_year=source_year)
        project = projects.order_by("-financial_year").first()
        if project is None:
            return {
                "status": "data_not_found",
                "answer": "The requested infrastructure project is not available for the selected financial year.",
                "sources": self._source("Infrastructure projects", "/infrastructure-projects/"),
            }
        answer = "{} is an infrastructure project for {} in {}. Its published stage is {}.".format(
            project.project_name,
            project.government_institution,
            project.financial_year,
            project.current_project_stage,
        )
        if project.provinces:
            answer += " It is listed for {}.".format(project.provinces)
        if query.intent == PortalIntent.AMOUNT_LOOKUP:
            if project.amount_rands is not None:
                answer += " The published {} amount is {}.".format(
                    project.budget_phase, self._amount(project.amount_rands)
                )
            if project.project_value_rands:
                answer += " The published project value is {}.".format(
                    self._amount(project.project_value_rands)
                )
        return {
            "status": "verified",
            "answer": answer,
            "sources": self._source(project.project_name, project.get_url_path()),
        }

    def _rank_infrastructure(self, query):
        projects = InfrastructureProjectPart.objects.exclude(project_value_rands__isnull=True)
        if query.financial_year:
            projects = projects.filter(financial_year=query.financial_year[:4])
        ordering = "-project_value_rands" if query.descending else "project_value_rands"
        project = projects.order_by(ordering, "project_name").first()
        if project is None:
            return {
                "status": "data_not_found",
                "answer": "No published infrastructure project values are available for the selected financial year.",
                "sources": self._source("Infrastructure projects", "/infrastructure-projects/"),
            }
        direction = "most expensive" if query.descending else "least expensive"
        return {
            "status": "verified",
            "answer": "The {} published infrastructure project{} is {}: {}.".format(
                direction,
                " for {}".format(query.financial_year) if query.financial_year else "",
                project.project_name,
                self._amount(project.project_value_rands),
            ),
            "sources": self._source(project.project_name, project.get_url_path()),
        }

    def _performance(self, query):
        name = query.entity_name
        if not name:
            return {
                "status": "needs_clarification",
                "answer": "Performance data is available by department. Please specify a department and, if needed, a financial year or indicator.",
                "sources": self._source("Performance monitoring", "/performance/"),
            }
        year = query.financial_year
        indicators = Indicator.objects.filter(department__name=name).select_related(
            "source__financial_year"
        )
        if year:
            indicators = indicators.filter(source__financial_year__slug=year)
        latest = indicators.order_by("-source__financial_year__slug")
        first = latest.first()
        if first is None:
            return {
                "status": "data_not_found",
                "answer": "No published performance indicators are available for that department and financial year.",
                "sources": self._source("Performance monitoring", "/performance/"),
            }
        selected_year = first.source.financial_year.slug
        current = latest.filter(source__financial_year__slug=selected_year)
        examples = list(current.values_list("indicator_name", flat=True)[:3])
        answer = "Performance data for {} in {} contains {} published indicators.".format(
            name, selected_year, current.count()
        )
        if examples:
            answer += " Examples include: {}.".format("; ".join(examples))
        return {
            "status": "verified",
            "answer": answer,
            "sources": self._source("Performance monitoring", "/performance/"),
        }
