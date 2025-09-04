from django.conf import settings
from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView
from httplib2 import Response

from budgetportal.models import FinancialYear, MainMenuItem
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
    "department__government__sphere__financial_year__slug",
    "department__government__sphere__name",
    "department__government__name",
    "department__name",
    "name",
    "pfma",
    "functiongroup1",
    # "budget_phase",
    "amount"

]



def read_object_from_yaml(path_file):
    with open(path_file, "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)
    

def public_entity_page(
    request, financial_year_id, sphere_slug, government_slug, public_entity_slug
):
    
    start_year = financial_year_id.split("-")[0]

    # Get public entity by public_entity_slug
    selected_public_entity = PublicEntity.objects.filter(
        slug=public_entity_slug,
        financialYear=start_year
    ).first()
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    # Total up public entityies amount
    total_amount = 0
    for government in (
        selected_year.spheres.filter(slug="national").first().governments.all()
    ):
        for public_entity in government.public_entities.all():
            total_amount += public_entity.amount

    # Total up public entities in same department
    total_department_amount = 0
    department_public_entities = []
    chart_data = []
    
    print('Departments:', selected_public_entity.department)
    print('financialYear:', start_year)

    department_opublic_entities = PublicEntity.objects.filter(department=selected_public_entity.department,  financialYear=start_year)
    print('department entities:', len(department_opublic_entities))

    for department_public_entity in department_opublic_entities:
        
        total_department_amount += department_public_entity.amount
        print("amount:", total_department_amount)
        department_public_entities.append(department_public_entity)
        # if department_public_entity is selected_public_entity then color_group = 2 else 1
        colour_group = 2 if department_public_entity == selected_public_entity else 1
        chart_data.append(
            [
                colour_group,
                simplejson.dumps(
                    department_public_entity.amount, use_decimal=True),
                department_public_entity.name,
                simplejson.dumps(department_public_entity.id),
                department_public_entity.slug,
                financial_year_id
            ]
        )

    # Get public entity expenditure
    public_entity_expenditure = PublicEntityExpenditure.objects.filter(
        public_entity=selected_public_entity
    )

    # Public entity amount percentage of total department amount
    percentage_of_total_department_amount = (
        selected_public_entity.amount / total_department_amount
    ) * 100

    # Public entity amount percentage of total amount
    percentage_of_total_amount = (
        selected_public_entity.amount / total_amount) * 100

    context = {
        "public_entity_id": selected_public_entity.id,
        "intro": selected_public_entity.intro,
        "name": selected_public_entity.name,
        "department": selected_public_entity.department.name,
        "department_slug": selected_public_entity.department.slug,
        "slug": str(selected_public_entity.slug),
        "selected_financial_year": selected_year.slug,
        "selected_tab": "public_entities",
        "title": "%s expenditure %s  - vulekamali"
        % (selected_public_entity.name, selected_year.slug),
        "description": "%s public entity: Expenditure data for the %s financial year %s"
        % (
            selected_public_entity.name,
            selected_year.slug,
            COMMON_DESCRIPTION_ENDING,
        ),
        "public_entity": selected_public_entity,
        "total_amount": total_amount,
        "total_department_amount": total_department_amount,
        "percentage_of_total_amount": percentage_of_total_amount,
        "percentage_of_total_department_amount": percentage_of_total_department_amount,
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
        "title": "Public Entities Budgets for %s - vulekamali" % selected_year.slug,
        "public_entities": [],
        "description": "Public Entities budgets for the %s financial year %s"
        % (selected_year.slug, COMMON_DESCRIPTION_ENDING),
    }

    for year in FinancialYear.get_available_years():
        is_selected = year.slug == financial_year_id
        page_data["financial_years"].append(
            {
                "id": year.slug,
                "is_selected": is_selected,
                "closest_match": {
                    "is_exact_match": True,
                    "url_path": "/public-entities/%s" % year.slug,
                },
            }
        )

    # for government in (
    #     selected_year.spheres.filter(slug="national").first().governments.all()
    # ):
    #     public_entities = []
    #     for public_entity in government.public_entities.all()[:5]:
    #         public_entities.append(
    #             {
    #                 "name": public_entity.name,
    #                 "url_path": public_entity.get_url_path(),
    #                 "department": public_entity.department.name,
    #                 "department_slug": public_entity.department.slug,
    #                 "department_sphere": public_entity.department.government.sphere.slug,
    #                 "functiongroup1": public_entity.functiongroup1,
    #                 "selected_year_slug": selected_year.slug,
    #                 "pfma": public_entity.pfma,
    #                 "amount": int(public_entity.amount),
    #             }
    #         )
    #     public_entities = sorted(public_entities, key=lambda d: d["name"])
    #     page_data["public_entities"].append(public_entities)

    # page_data["public_entities"] = [
    #     item for sublist in page_data["public_entities"] for item in sublist
    # ]

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
    queryset = PublicEntity.objects.all()
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = PublicEntity.objects.all()
        financial_year_id = self.kwargs.get("financial_year_id")
        print("financial year excel", financial_year_id)
        if financial_year_id:
            start_year = financial_year_id.split("-")[0]
            queryset = queryset.filter(
                financialYear=start_year).order_by("-amount")
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())  # ✅ DRF filters

        search_text = self.request.GET.get("q", "")

        filters = {k: v for k, v in request.GET.items() if k != "q"}
        queryset = get_filtered_queryset(queryset, search_text, filters)   # ✅ your custom filters

        facets = self.get_facets(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = {
                "items": serializer.data,
                "facets": facets,
            }
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "items": serializer.data,
            "facets": facets,
        })

    def get_facets(self, qs):
        def facet_query(field, label=None):
            label = label or field
            return (

                qs.values(field).annotate(count=Count(field)).order_by()
            )

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
