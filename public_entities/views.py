from decimal import Decimal
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView
from rest_framework.response import Response
from django.db.models.functions import Coalesce, Cast
from collections import Counter

from budgetportal.models import ENEData, FinancialYear, MainMenuItem
from public_entities.models import PublicEntity, PublicEntityExpenditure
import simplejson
import yaml
from public_entities.serializer import PublicEntitiesSerializer
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from django.contrib.postgres.search import SearchQuery
from django.db.models import Count, Q
from drf_excel.mixins import XLSXFileMixin
from django.http import StreamingHttpResponse

from django.db.models import (
    DecimalField,
    OuterRef,
    Subquery,
    Sum,
    Case,
    When,
    IntegerField,
    F,
    CharField,
)

import xlsx_streaming


COMMON_DESCRIPTION_ENDING = "from National Treasury in partnership with IMALI YETHU."

FIELD_MAP = {
    "department_name": "department__name",
    "financial_year_slug": "department__government__sphere__financial_year__slug",
    "government_name": "department__government__name",
    "sphere_name": "department__government__sphere__name",
    "name": "name",
    "slug": "slug",
    "intro": "intro",
    "pfma": "pfma",
    "functiongroup1": "functiongroup1",
    "amount": "amount",
}

XLSX_COLUMNS = [
    "department__government__name",
    "department__name",
    "name",
    "pfma",
    "functiongroup1",
    "amount"
]



def read_object_from_yaml(path_file):
    with open(path_file, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)
    

def format_values(value):
    # Auto-convert only if not Decimal
    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    def format_number(num):
        return f"{num:,.2f}".rstrip('0').rstrip('.')

    T = Decimal("1000000000000")
    B = Decimal("1000000000")
    M = Decimal("1000000")
    K = Decimal("1000")

    if value >= T:
        return f"{format_number(value / T)} Trillion"
    elif value >= B:
        return f"{format_number(value / B)} Billion"
    elif value >= M:
        return f"{format_number(value / M)} Million"
    elif value >= K:
        return f"{format_number(value / K)} Thousand"
    else:
        return f"{format_number(value)}"

def public_entity_page(request, financial_year_id, sphere_slug, government_slug, public_entity_slug):

    # Extract fiscal year (e.g. "2025-26" → "2025")
    start_year = financial_year_id.split("-")[0]

    # Get selected PublicEntity (no longer filtered by financialYear)
    selected_public_entity = (
        PublicEntity.objects
        .filter(
            slug=public_entity_slug,
            publicentityexpenditure__financialYear=start_year
        )
        .distinct()
        .first()
    )

    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    # ---------------------------------------------------------
    # 1. TOTAL ACROSS ALL PUBLIC ENTITIES FOR THIS YEAR
    # ---------------------------------------------------------
    total_amount = (
        PublicEntityExpenditure.objects
        .filter(financialYear=start_year)
        .aggregate(total=Sum("amount"))
        .get("total") or 0
    )

    # ---------------------------------------------------------
    # 2. TOTAL FOR THIS PUBLIC ENTITY (all rows for the year)
    # ---------------------------------------------------------
    entity_amount = (
        PublicEntityExpenditure.objects
        .filter(public_entity=selected_public_entity, financialYear=start_year)
        .aggregate(total=Sum("amount"))
        .get("total") or 0
    )

    # ---------------------------------------------------------
    # 3. TOTAL FOR THIS ENTITY'S DEPARTMENT (same year)
    # ---------------------------------------------------------
    department_amount = (
        ENEData.objects
        .filter(
            department=selected_public_entity.department.name,
            financialYear=start_year
        )
        .aggregate(total=Sum("value"))
        .get("total") or 0
    )

    # ---------------------------------------------------------
    # 4. LIST OF ALL PUBLIC ENTITIES IN SAME DEPARTMENT
    # ---------------------------------------------------------
    department_public_entities = (
        PublicEntity.objects.filter(
            department=selected_public_entity.department)
    )

    # Build chart dataset
    chart_data = []
    for pe in department_public_entities:
        pe_amount = (
            PublicEntityExpenditure.objects
            .filter(public_entity=pe, financialYear=start_year)
            .aggregate(total=Sum("amount"))
            .get("total") or 0
        )

        colour_group = 2 if pe == selected_public_entity else 1

        chart_data.append([
            colour_group,
            float(pe_amount),     # JSON safe
            pe.name,
            pe.id,
            pe.slug,
            financial_year_id,
        ])

    # ---------------------------------------------------------
    # 5. GET EXPENDITURE ROWS FOR SELECTED ENTITY
    # ---------------------------------------------------------
    public_entity_expenditure = (
        PublicEntityExpenditure.objects.filter(
            public_entity=selected_public_entity,
            financialYear=start_year
        )
    )

    # ---------------------------------------------------------
    # 6. SAFELY CALCULATE PERCENTAGES
    # ---------------------------------------------------------
    percentage_of_total_department = (
        (entity_amount / department_amount) * 100 if department_amount else 0
    )

    percentage_of_total_all = (
        (entity_amount / total_amount) * 100 if total_amount else 0
    )

    # ---------------------------------------------------------
    # 7. CONTEXT
    # ---------------------------------------------------------
    context = {
        "public_entity_id": selected_public_entity.id,
        "intro": selected_public_entity.intro,
        "name": selected_public_entity.name,
        "department": selected_public_entity.department.name,
        "department_slug": selected_public_entity.department.slug,
        "slug": selected_public_entity.slug,
        "selected_financial_year": selected_year.slug,
        "selected_tab": "public_entities",
        "title": f"{selected_public_entity.name} expenditure {selected_year.slug} - vulekamali",
        "description": f"{selected_public_entity.name} public entity: Expenditure data for the {selected_year.slug} financial year {COMMON_DESCRIPTION_ENDING}",

        # fixed amounts
        "public_entity_amount": format_values(entity_amount),
        "total_amount": format_values(total_amount),
        "total_department_amount": format_values(department_amount),

        # percentages
        "percentage_of_total_amount": percentage_of_total_all,
        "percentage_of_total_department_amount": percentage_of_total_department,

        "department_public_entities": department_public_entities,
        "chart_data": chart_data,
        "public_entity_expenditure": public_entity_expenditure,
    }

    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    context["global_values"] = read_object_from_yaml(
        str(settings.ROOT_DIR.path("_data/global_values.yaml"))
    )
    context["admin_url"] = reverse(
        "admin:budgetportal_department_change", args=(selected_public_entity.pk,)
    )

    return render(request, "public_entity.html", context)



# def latest_public_entity_list(request):
#     context = public_entity_list_data(FinancialYear.get_latest_year().slug)
#     context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
#     context["latest_year"] = FinancialYear.get_latest_year().slug
    
#     return render(request, "public_entity_list.html", context)



def latest_public_entity_list(request):
    department = request.GET.get("department", None)
    url = reverse("public-entity-list",
                  args=(FinancialYear.get_latest_year().slug,))
    url = f"{url}?department={department}" if department else url
    return redirect(url, permanent=False)


def public_entity_list_data(financial_year_id):
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    page_data = {
        "financial_years": [],
        "selected_financial_year": selected_year.slug,
        "selected_tab": "public_entities",
        "slug": "public-entities",
        "title": f"Public Entities Budgets for {selected_year.slug} - vulekamali",
        "public_entities": [],
        "description": (
            f"Public Entities budgets for the {selected_year.slug} financial year "
            f"{COMMON_DESCRIPTION_ENDING}"
        ),
    }

    # Year navigation
    for year in FinancialYear.get_available_years():
        page_data["financial_years"].append({
            "id": year.slug,
            "is_selected": year.slug == financial_year_id,
            "closest_match": {
                "is_exact_match": True,
                "url_path": f"/public-entities/{year.slug}",
            },
        })

    # Fetch only entities that have expenditure for this year
    start_year = selected_year.slug.split("-")[0]
    expenditures = (
        PublicEntityExpenditure.objects
        .filter(financialYear=start_year)
        .select_related("public_entity", "public_entity__department",
                        "public_entity__government",
                        "public_entity__government__sphere")
    )

    entity_map = {}

    for exp in expenditures:
        pe = exp.public_entity

        if pe.id not in entity_map:
            entity_map[pe.id] = {
                "name": pe.name,
                "url_path": pe.get_url_path(),
                "department": pe.department.name,
                "department_slug": pe.department.slug,
                "department_sphere": pe.department.government.sphere.slug,
                "functiongroup1": pe.functiongroup1,
                "selected_year_slug": selected_year.slug,
                "pfma": pe.pfma,
                "amount": int(exp.amount),
            }

    # Sort
    page_data["public_entities"] = sorted(
        entity_map.values(), key=lambda d: d["name"]
    )

    return page_data


def public_entity_list(request, financial_year_id):
    context = public_entity_list_data(financial_year_id)
    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    return render(request, "public_entity_list.html", context)


def text_search(qs, search_text):
    if search_text == "":
        return qs

    return qs.filter(
            Q(name__icontains=search_text)
            | Q(department__name__icontains=search_text)
            | Q(pfma__icontains=search_text)
            | Q(functiongroup1__icontains=search_text)
    )


def add_filters(qs, params):
    query_dict = {}
    for k, v in FIELD_MAP.items():
        if v in params:
            query_dict[v] = params[v]

    return qs.filter(**query_dict)


def get_filtered_queryset(queryset, search_text="", filters=None):
    # filters is a dict of additional filters
    if filters is None:
        filters = {}

    filtered_queryset = queryset.select_related(
        "department",
        "department__government",
        "department__government__sphere",
        "department__government__sphere__financial_year",
    )
    filtered_queryset = text_search(filtered_queryset, search_text)
    filtered_queryset = add_filters(filtered_queryset, filters)

    return filtered_queryset


class TenPerPagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = None


class PublicEntityListView(generics.ListAPIView):
    serializer_class = PublicEntitiesSerializer
    pagination_class = TenPerPagePagination

    SORT_ALLOWLIST = {"id", "name", "department", "functiongroup1", "amount"}

    def _start_year(self) -> int:
        financial_year_id = self.kwargs.get("financial_year_id")
        return int(financial_year_id.split("-")[0])

    def _pe_ids_sq(self, start_year: int):
        return (
            PublicEntityExpenditure.objects
            .filter(financialYear=start_year)
            .values("public_entity_id")
            .distinct()
        )

    def _amount_sq(self, start_year: int):
        return (
            PublicEntityExpenditure.objects
            .filter(public_entity_id=OuterRef("pk"), financialYear=start_year)
            .values("public_entity_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1]
        )

    def _get_sort(self, request):
        sort = (request.GET.get("sort") or "name").strip()
        direction = (request.GET.get("dir") or "asc").strip().lower()
        if sort not in self.SORT_ALLOWLIST:
            sort = "name"
        if direction not in ("asc", "desc"):
            direction = "asc"
        return sort, direction

    def get_queryset(self):
        start_year = self._start_year()
        return (
            PublicEntity.objects
            .filter(pk__in=Subquery(self._pe_ids_sq(start_year)))
            .select_related("department", "government", "government__sphere")
            .order_by("id")
        )

    def _build_facets_manual(self, base_qs):
        # IMPORTANT: base_qs must have NO annotations
        rows = base_qs.values_list("department__name", "functiongroup1")

        dept_counter = Counter()
        fg_counter = Counter()

        for dept_name, fg in rows:
            if dept_name:
                dept_counter[dept_name] += 1
            if fg:
                fg_counter[fg] += 1

        return {
            "department_name": [
                {"department__name": k, "count": v} for k, v in dept_counter.most_common()
            ],
            "functiongroup1": [
                {"functiongroup1": k, "count": v} for k, v in fg_counter.most_common()
            ],
        }

    def list(self, request, *args, **kwargs):
        start_year = self._start_year()
        sort, direction = self._get_sort(request)
        sign = "-" if direction == "desc" else ""

        # 1) base queryset (NO amount annotation)
        base_qs = (
            PublicEntity.objects
            .filter(pk__in=Subquery(self._pe_ids_sq(start_year)))
            .select_related("department", "government", "government__sphere")
        )

        # apply search + filters (exclude sort/dir/page)
        search_text = request.GET.get("q", "")
        filters = {
            k: v for k, v in request.GET.items()
            if k not in ("q", "sort", "dir", "page") and v is not None and str(v).strip() != ""
        }
        base_qs = get_filtered_queryset(base_qs, search_text, filters)

        # 2) facets from FULL filtered base_qs (before pagination)
        facets = self._build_facets_manual(base_qs)

        # 3) count
        total_count = base_qs.count()

        # 4) build globally ordered ID list (lightweight)
        if sort == "amount":
            amount_sq = self._amount_sq(start_year)
            id_qs = (
                base_qs.only("id")
                .annotate(
                    amount=Coalesce(
                        Subquery(amount_sq, output_field=DecimalField(
                            max_digits=20, decimal_places=2)),
                        Decimal("0"),
                    )
                )
                .order_by(f"{sign}amount", "id")
                .values_list("id", flat=True)
            )
        elif sort == "department":
            id_qs = (
                base_qs.only("id")
                .annotate(_dept=Cast(F("department__name"), output_field=CharField()))
                .order_by(f"{sign}_dept", "id")
                .values_list("id", flat=True)
            )
        elif sort == "functiongroup1":
            id_qs = (
                base_qs.only("id")
                .annotate(_fg=Cast(F("functiongroup1"), output_field=CharField()))
                .order_by(f"{sign}_fg", "id")
                .values_list("id", flat=True)
            )
        elif sort == "name":
            id_qs = (
                base_qs.only("id")
                .annotate(_name=Cast(F("name"), output_field=CharField()))
                .order_by(f"{sign}_name", "id")
                .values_list("id", flat=True)
            )
        else:
            id_qs = base_qs.only("id").order_by(
                f"{sign}id").values_list("id", flat=True)

        # 5) manual page slice
        page_size = 10
        page_number = int(request.GET.get("page") or 1)
        page_number = max(page_number, 1)
        start = (page_number - 1) * page_size
        end = start + page_size
        page_ids = list(id_qs[start:end])

        # 6) fetch page items with amount annotation
        amount_sq = self._amount_sq(start_year)
        items_qs = (
            PublicEntity.objects
            .filter(id__in=page_ids)
            .select_related("department", "government", "government__sphere")
            .annotate(
                amount=Coalesce(
                    Subquery(amount_sq, output_field=DecimalField(
                        max_digits=20, decimal_places=2)),
                    Decimal("0"),
                )
            )
        )

        order_case = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(page_ids)],
            output_field=IntegerField(),
        )
        items_qs = items_qs.order_by(order_case)

        serializer = self.get_serializer(items_qs, many=True)

        # 7) build next/previous links
        base_url = request.build_absolute_uri().split("?")[0]
        q = request.GET.copy()

        next_url = None
        if end < total_count:
            q["page"] = str(page_number + 1)
            next_url = f"{base_url}?{q.urlencode()}"

        prev_url = None
        if page_number > 1:
            q["page"] = str(page_number - 1)
            prev_url = f"{base_url}?{q.urlencode()}"

        return Response({
            "count": total_count,
            "next": next_url,
            "previous": prev_url,
            "results": {
                "items": serializer.data,
                "facets": facets,
            }
        })

class PublicEntityXLSXListView(XLSXFileMixin, generics.ListAPIView):
    pagination_class = None
    template_filename = "public_entities/template.xlsx"
    filename = "public-entities.xlsx"
    queryset = PublicEntity.objects.all()

    SORT_ALLOWLIST = {"id", "name", "department", "functiongroup1", "amount"}

    def _start_year(self) -> int:
        financial_year_id = self.kwargs.get("financial_year_id")
        return int(financial_year_id.split("-")[0])

    def _pe_ids_sq(self, start_year: int):
        return (
            PublicEntityExpenditure.objects
            .filter(financialYear=start_year)
            .values("public_entity_id")
            .distinct()
        )

    def _amount_sq(self, start_year: int):
        return (
            PublicEntityExpenditure.objects
            .filter(public_entity_id=OuterRef("pk"), financialYear=start_year)
            .values("public_entity_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1]
        )

    def _get_sort(self, request):
        sort = (request.GET.get("sort") or "name").strip()
        direction = (request.GET.get("dir") or "asc").strip().lower()
        if sort not in self.SORT_ALLOWLIST:
            sort = "name"
        if direction not in ("asc", "desc"):
            direction = "asc"
        return sort, direction

    def get_queryset(self):
        start_year = self._start_year()
        pe_ids_sq = self._pe_ids_sq(start_year)
        amount_sq = self._amount_sq(start_year)

        # Base: no join to expenditure table, no duplicates, no distinct needed
        qs = (
            PublicEntity.objects
            .filter(pk__in=Subquery(pe_ids_sq))
            .select_related(
                "department",
                "department__government",
                "department__government__sphere",
            )
            .annotate(
                amount=Coalesce(
                    Subquery(amount_sq, output_field=DecimalField(
                        max_digits=20, decimal_places=2)),
                    Decimal("0"),
                )
            )
        )

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        search_text = request.GET.get("q", "")
        filters = {k: v for k, v in request.GET.items(
        ) if k not in ("q", "sort", "dir", "page")}

        qs = get_filtered_queryset(qs, search_text, filters)

        # Sorting for export (SQL Server safe via casts for text-like fields)
        sort, direction = self._get_sort(request)
        sign = "-" if direction == "desc" else ""

        if sort == "amount":
            qs = qs.order_by(f"{sign}amount", "id")
        elif sort == "department":
            qs = qs.annotate(_dept=Cast(
                F("department__name"), output_field=CharField())).order_by(f"{sign}_dept", "id")
        elif sort == "functiongroup1":
            qs = qs.annotate(_fg=Cast(
                F("functiongroup1"), output_field=CharField())).order_by(f"{sign}_fg", "id")
        elif sort == "name":
            qs = qs.annotate(_name=Cast(F("name"), output_field=CharField())).order_by(
                f"{sign}_name", "id")
        else:
            qs = qs.order_by(f"{sign}id")

        # Stream export
        with open(self.template_filename, "rb") as template:
            stream = xlsx_streaming.stream_queryset_as_xlsx(
                qs.values_list(*XLSX_COLUMNS),
                xlsx_template=template,
                batch_size=200,
            )

        response = StreamingHttpResponse(
            stream,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={self.filename}"
        return response
