from decimal import Decimal
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView
from httplib2 import Response

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
from django.db.models import Sum

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
    "financialYear",
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

# def public_entity_page(
#     request, financial_year_id, sphere_slug, government_slug, public_entity_slug
# ):
    
#     start_year = financial_year_id.split("-")[0]

#     # Get public entity by public_entity_slug
#     selected_public_entity = PublicEntity.objects.filter(
#         slug=public_entity_slug,
#         financialYear=start_year
#     ).first()
#     selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

#     # Total up public entityies amount
#     total_amount = 0
#     for government in (
#         selected_year.spheres.filter(slug="national").first().governments.all()
#     ):
#         for public_entity in government.public_entities.all():
#             total_amount += public_entity.amount

#     # Total up public entities in same department
#     total_department_amount = 0
#     department_public_entities = []
#     chart_data = []
    
#     print('Departments:', selected_public_entity.department)
#     print('financialYear:', start_year)

#     department_opublic_entities = PublicEntity.objects.filter(department=selected_public_entity.department,  financialYear=start_year)
#     department_data = ENEData.objects.filter(
#         department=selected_public_entity.department.name, financialYear=start_year)

#     for dept_total in department_data:
#         total_department_amount += dept_total.value

#     print('department entities:', len(department_opublic_entities))

#     for department_public_entity in department_opublic_entities:
        
#         # total_department_amount += department_public_entity.amount
#         # print("amount:", total_department_amount)
#         department_public_entities.append(department_public_entity)
#         # if department_public_entity is selected_public_entity then color_group = 2 else 1
#         colour_group = 2 if department_public_entity == selected_public_entity else 1
#         chart_data.append(
#             [
#                 colour_group,
#                 simplejson.dumps(
#                     department_public_entity.amount, use_decimal=True),
#                 department_public_entity.name,
#                 simplejson.dumps(department_public_entity.id),
#                 department_public_entity.slug,
#                 financial_year_id
#             ]
#         )

#     # Get public entity expenditure
#     public_entity_expenditure = PublicEntityExpenditure.objects.filter(
#         public_entity=selected_public_entity
#     )

#     # Public entity amount percentage of total department amount
#     percentage_of_total_department_amount = (
#         selected_public_entity.amount / total_department_amount
#     ) * 100

#     # Public entity amount percentage of total amount
#     percentage_of_total_amount = (
#         selected_public_entity.amount / total_amount) * 100

#     context = {
#         "public_entity_id": selected_public_entity.id,
#         "intro": selected_public_entity.intro,
#         "name": selected_public_entity.name,
#         "department": selected_public_entity.department.name,
#         "department_slug": selected_public_entity.department.slug,
#         "slug": str(selected_public_entity.slug),
#         "selected_financial_year": selected_year.slug,
#         "selected_tab": "public_entities",
#         "title": "%s expenditure %s  - vulekamali"
#         % (selected_public_entity.name, selected_year.slug),
#         "description": "%s public entity: Expenditure data for the %s financial year %s"
#         % (
#             selected_public_entity.name,
#             selected_year.slug,
#             COMMON_DESCRIPTION_ENDING,
#         ),
#         "public_entity": selected_public_entity,
#         "public_entity_amount": format_values(selected_public_entity.amount),
#         "total_amount": format_values(total_amount),
#         "total_department_amount": format_values(total_department_amount),
#         "percentage_of_total_amount": percentage_of_total_amount,
#         "percentage_of_total_department_amount": percentage_of_total_department_amount,
#         "department_public_entities": department_public_entities,
#         "chart_data": chart_data,
#         "public_entity_expenditure": public_entity_expenditure,
#     }
#     context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
#     context["latest_year"] = FinancialYear.get_latest_year().slug
#     context["global_values"] = read_object_from_yaml(
#         str(settings.ROOT_DIR.path("_data/global_values.yaml"))
#     )
#     context["admin_url"] = reverse(
#         "admin:budgetportal_department_change", args=(selected_public_entity.pk,)
#     )

#     return render(request, "public_entity.html", context)


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

    print('Selected Public Entity:', selected_public_entity)

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
        PublicEntityExpenditure.objects
        .filter(
            public_entity__department=selected_public_entity.department,
            financialYear=start_year
        )
        .aggregate(total=Sum("amount"))
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


class PublicEntityListView(generics.ListAPIView):
    serializer_class = PublicEntitiesSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        financial_year_id = self.kwargs.get("financial_year_id")
        start_year = financial_year_id.split("-")[0]

        expenditures = (
            PublicEntityExpenditure.objects
            .filter(financialYear=start_year)
            .select_related(
                "public_entity",
                "public_entity__department",
                "public_entity__government",
                "public_entity__government__sphere"
            )
        )

        public_entity_ids = expenditures.values_list(
            "public_entity_id", flat=True
        )

        return PublicEntity.objects.filter(id__in=public_entity_ids)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        search_text = self.request.GET.get("q", "")
        filters = {k: v for k, v in request.GET.items() if k != "q"}

        queryset = get_filtered_queryset(queryset, search_text, filters)

        facets = self.get_facets(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "items": serializer.data,
                "facets": facets,
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "items": serializer.data,
            "facets": facets,
        })

    def get_facets(self, qs):
        def facet_query(field):
            return qs.values(field).annotate(count=Count(field)).order_by()

        return {
            "department_name": facet_query("department__name"),
            "functiongroup1": facet_query("functiongroup1"),
        }


class PublicEntityXLSXListView(XLSXFileMixin, generics.ListAPIView):
    pagination_class = None
    template_filename = "public_entities/template.xlsx"
    filename = "public-entities.xlsx"
    queryset = PublicEntity.objects.all()

    def get_queryset(self):
        queryset = PublicEntity.objects.all()
        financial_year_id = self.kwargs.get("financial_year_id")

        if financial_year_id:
            start_year = financial_year_id.split("-")[0]
            queryset = queryset.filter(
                financialYear=start_year).order_by("-amount")
        return queryset

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(self.get_queryset())

        search_text = self.request.GET.get("q", "")

        filters = {k: v for k, v in request.GET.items() if k != "q"}
        excel_data = get_filtered_queryset(queryset, search_text, filters)

        with open(self.template_filename, "rb") as template:
            stream = xlsx_streaming.stream_queryset_as_xlsx(
                self.filter_queryset(excel_data).values_list(*XLSX_COLUMNS),
                xlsx_template=template,
                batch_size=50,
            )
        response = StreamingHttpResponse(
            stream,
            content_type="application/vnd.xlsxformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={self.filename}"
        return response
