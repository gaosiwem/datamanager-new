

from collections import defaultdict
from .models import AENEData, BudgetVSActualNationalData, ConsolidationData, FinancialYear, MainMenuItem
from django.utils.text import slugify
import json
from django.conf import settings
import requests
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from slugify import slugify
from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.urls import reverse
from django.db.models import F
import os
from decimal import Decimal
from django.http import JsonResponse
from operator import itemgetter

from budgetportal.utils.Infra_Coordinates import (CoordinateUtils)


# import numpy as np

# import plotly.express as px
# import plotly.graph_objects as go
# import plotly.io as pio
# from plotly.subplots import make_subplots

# import pandas as pd
import json
from django.shortcuts import render
from django.db.models import Sum

from public_entities.models import PublicEntity

from .models import (
    FAQ,
    # CategoryGuide,
    Department,
    # Event,
    Government,
    Sphere,
    Video,
    FinancialYear,
    Homepage,
    MainMenuItem,
    ShowcaseItem,
    InfrastructureProjectPart,
    DatasetCategory,
    Dataset,
    DatasetResource,
    BudgetVSActualNationalData,
    ConsolidationData,
    BudgetVSActualProvincialData,
    VoteDocument,
    EPREData,
    ENEData
)

COMMON_DESCRIPTION = "South Africa's National and Provincial budget data "
COMMON_DESCRIPTION_ENDING = "from National Treasury in partnership with IMALI YETHU."
DEPARTMENT_SLUG_ALIASES = {
    "science-technology-and-innovation": "science-and-innovation",
}


def get_department_by_slug_or_alias(government, department_slug):
    requested_slug = slugify(department_slug)
    department = government.departments.filter(slug=requested_slug).first()
    if department:
        return department

    aliased_slug = DEPARTMENT_SLUG_ALIASES.get(requested_slug)
    if aliased_slug:
        return government.departments.filter(slug=aliased_slug).first()

    return None


def serialize_showcase(showcase_items):
    showcase_items_dicts = [
        {
            "name": i.name,
            "description": i.description,
            "cta_text_1": i.cta_text_1,
            "cta_link_1": i.cta_link_1,
            "cta_text_2": i.cta_text_2,
            "cta_link_2": i.cta_link_2,
            "second_cta_type": i.second_cta_type,
            "thumbnail_url": i.file.url,
        }
        for i in showcase_items
    ]
    return json.dumps(
        showcase_items_dicts, cls=DjangoJSONEncoder, sort_keys=True, indent=4
    )


def homepage(request):
    year = FinancialYear.get_latest_year()
    titles = {
        "whyBudgetIsImportant",
        "howCanTheBudgetPortalHelpYou",
        "theBudgetProcess",
    }
    videos = Video.objects.filter(title_id__in=titles)

    page_data = Homepage.objects.first()
    latest_provincial_year = (
        FinancialYear.objects.filter(spheres__slug="provincial")
        # .annotate(num_depts=Count("spheres__governments__departments"))
        # .filter(num_depts__gt=0)
        .first()
    )

    showcase_items = ShowcaseItem.objects.all()

    context = {
        "selected_financial_year": None,
        "financial_years": [],
        "selected_tab": "homepage",
        "slug": year.slug,
        "title": "South African Government Budgets %s - vulekamali" % year.slug,
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "url_path": year.get_url_path(),
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "videos": videos,
        "latest_year": year.slug,
        "latest_provincial_year": latest_provincial_year
        and latest_provincial_year.slug,
        "main_heading": page_data.main_heading,
        "sub_heading": page_data.sub_heading,
        "primary_button_label": page_data.primary_button_label,
        "primary_button_url": page_data.primary_button_url,
        "secondary_button_label": page_data.secondary_button_label,
        "secondary_button_url": page_data.secondary_button_url,
        "call_to_action_sub_heading": page_data.call_to_action_sub_heading,
        "call_to_action_heading": page_data.call_to_action_heading,
        "call_to_action_link_label": page_data.call_to_action_link_label,
        "call_to_action_link_url": page_data.call_to_action_link_url,
        "showcase_items_json": serialize_showcase(showcase_items),
    }
    

    return render(request, "homepage.html", context)


def glossary(request):
    context = {
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "selected_tab": "learning-centre",
        "selected_sidebar": "glossary",
        "title": "Glossary - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "latest_year": FinancialYear.get_latest_year().slug,
        "selected_financial_year": None,
        "financial_years": [],
    }
    return render(request, "glossary.html", context)


def about(request):
    context = {
        "title": "About - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "selected_tab": "about",
        "selected_financial_year": None,
        "financial_years": [],
        "video": Video.objects.get(title_id="onlineBudgetPortal"),
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "latest_year": FinancialYear.get_latest_year().slug,
    }
    return render(request, "about.html", context)


def faq(request):
    faq_list = FAQ.objects.all()
    context = {
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "title": "FAQ - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "selected_tab": "faq",
        "latest_year": FinancialYear.get_latest_year().slug,
        "selected_financial_year": None,
        "financial_years": [],
        "faq_list": faq_list,
    }
    return render(request, "faq.html", context)


def videos(request):
    context = {
        "title": "Videos - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "selected_tab": "learning-centre",
        "selected_sidebar": "videos",
        "videos": Video.objects.all(),
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "latest_year": FinancialYear.get_latest_year().slug,
        "admin_url": reverse("admin:budgetportal_video_changelist"),
    }
    return render(request, "videos.html", context)


def terms_and_conditions(request):
    context = {
        "title": "Terms of use - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "latest_year": FinancialYear.get_latest_year().slug,
    }
    return render(request, "terms-and-conditions.html", context)


def resources(request):
    titles = {"theBudgetProcess", "participate"}

    context = {
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "videos": Video.objects.filter(title_id__in=titles),
        "latest_year": FinancialYear.get_latest_year().slug,
        "title": "Resources - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "selected_tab": "learning-centre",
        "selected_sidebar": "resources",
    }
    return render(request, "resources.html", context)


def department_list_data(financial_year_id):
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)
    page_data = {
        "financial_years": [],
        "selected_financial_year": selected_year.slug,
        "selected_tab": "departments",
        "slug": "departments",
        "title": "Department Budgets for %s - vulekamali" % selected_year.slug,
        "description": "Department budgets for the %s financial year %s"
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
                    "url_path": "/%s/departments" % year.slug,
                },
            }
        )

    for sphere_name in ("national", "provincial"):
        page_data[sphere_name] = []
        print(selected_year.spheres)
        for government in (
            selected_year.spheres.filter(
                slug=sphere_name).first().governments.all()
        ):
            departments = []
            for department in government.departments.all():
                departments.append(
                    {
                        "name": department.name,
                        "slug": str(department.slug),
                        "vote_number": department.vote_number,
                        "url_path": department.get_url_path(),
                        "website_url": department.get_latest_website_url(),
                    }
                )
            departments = sorted(departments, key=lambda d: d["vote_number"])
            page_data[sphere_name].append(
                {
                    "name": government.name,
                    "slug": str(government.slug),
                    "departments": departments,
                }
            )

    return page_data


def infrastructure_projects_overview(request):
    """Overview page to showcase all featured infrastructure projects"""
    infrastructure_projects = InfrastructureProjectPart.objects.filter(
        featured=True
    ).order_by("project_slug").annotate(
        unique_slug=F("project_slug")
    )
    if infrastructure_projects is None:
        raise Http404()
    projects = []
    for project in infrastructure_projects:
        departments = Department.objects.filter(
            slug=slugify(project.government_institution),
            government__sphere__slug="national",
        )
        department_url = None
        if departments:
            department_url = (
                departments[0].get_latest_department_instance().get_url_path()
            )
        projects.append(
            {
                "name": project.project_name,
                "coordinates": CoordinateUtils.clean_coordinates(project.gps_code),
                "projected_budget": project.calculate_projected_expenditure(),
                "stage": project.current_project_stage,
                "description": project.project_description,
                "provinces": project.provinces.split(","),
                "total_budget": project.project_value_rands,
                "detail": project.get_url_path(),
                "slug": project.get_url_path(),
                "page_title": "{} - vulekamali".format(project.project_name),
                "government_institution": {
                    "name": project.government_institution,
                    "url": department_url,
                },
                "nature_of_investment": project.nature_of_investment,
                "infrastructure_type": project.infrastructure_type,
                "expenditure": sorted(
                    project.build_complete_expenditure(), key=lambda e: e["year"]
                ),
                "administration_type": project.administration_type,
                "partnership_type": project.partnership_type,
                "date_of_close": project.date_of_close,
                "duration": project.duration,
                "financing_structure": project.financing_structure,
                "project_value_rand_million": project.project_value_rand_million,
                "form_of_payment": project.form_of_payment,
            }
        )
    projects = sorted(projects, key=lambda p: p["name"])
    return {
        # "dataset_url": reverse("dataset-category", args=("infrastructure-projects",)),
        "projects": projects,
        "description": "National department Infrastructure projects in South Africa",
        "slug": "infrastructure-projects",
        "selected_tab": "infrastructure-projects",
        "title": "Infrastructure Projects - vulekamali",
    }


def infrastructure_projects_overview_json(request):
    response_json = json.dumps(
        infrastructure_projects_overview(request),
        sort_keys=True,
        indent=4,
        separators=(",", ": "),
    )
    return HttpResponse(response_json, content_type="application/json")


def infrastructure_project_list(request):
    context = {
        "page": {"layout": "about", "data_key": "about"},
        "site": {"latest_year": FinancialYear.get_latest_year().slug},
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        
    }
    return render(request, "infrastructure_project_list.html", context)


def infrastructure_project_detail_data(project_slug):
    project = InfrastructureProjectPart.objects.filter(
        project_slug=project_slug
    ).first()
    if not project:
        return HttpResponse(status=404)

    departments = Department.objects.filter(
        slug=slugify(project.government_institution),
        government__sphere__slug="national",
    )
    department_url = None
    if departments:
        department_url = departments[0].get_latest_department_instance().get_url_path()
    # dataset_url = reverse("dataset-category", args=("infrastructure-projects",))

    project_dict = {
        "name": project.project_name,
        "coordinates": CoordinateUtils.clean_coordinates(project.gps_code),
        "projected_budget": project.calculate_projected_expenditure(),
        "stage": project.current_project_stage,
        "description": project.project_description,
        "provinces": project.provinces.split(","),
        "total_budget": project.project_value_rands,
        "detail": project.get_url_path(),
        # "dataset_url": dataset_url,
        "slug": project.get_url_path(),
        "page_title": "{} - vulekamali".format(project.project_name),
        "government_institution": {
            "name": project.government_institution,
            "url": department_url,
        },
        "nature_of_investment": project.nature_of_investment,
        "infrastructure_type": project.infrastructure_type,
        "expenditure": sorted(
            project.build_complete_expenditure(), key=lambda e: e["year"]
        ),
        "administration_type": project.administration_type,
        "partnership_type": project.partnership_type,
        "date_of_close": project.date_of_close,
        "duration": project.duration,
        "financing_structure": project.financing_structure,
        "project_value_rand_million": project.project_value_rand_million,
        "form_of_payment": project.form_of_payment,
    }
    return {
        # "dataset_url": dataset_url,
        "projects": [project_dict],
        "description": project.project_description
        or "Infrastructure projects in South Africa",
        "slug": "infrastructure-projects",
        "selected_tab": "infrastructure-projects",
        "title": f"{project.project_name} - Infrastructure Projects - vulekamali",
    }


def infrastructure_project_detail_json(request, project_slug):
    response = infrastructure_project_detail_data(project_slug)
    # For 404 - not sure why not raising a 404 exception.
    if isinstance(response, HttpResponse):
        return response

    response_json = json.dumps(
        response, sort_keys=True, indent=4, separators=(",", ": ")
    )
    return HttpResponse(response_json, content_type="application/json")


def infrastructure_project_detail(request, project_slug):
    dataset_response = infrastructure_project_detail_data(project_slug)
    # For 404 - not sure why not raising a 404 exception.
    if isinstance(dataset_response, HttpResponse):
        return dataset_response
    latest_year_slug = FinancialYear.get_latest_year().slug

    context = {
        "page": {"layout": "infrastructure_project", "data_key": "dataset"},
        "site": {
            "data": {
                "navbar": MainMenuItem.objects.prefetch_related("children").all(),
                "dataset": dataset_response,
            },
            "latest_year": latest_year_slug,
        },
        "debug": settings.DEBUG,
    }
    return render(request, "infrastructure_project.html", context)


def spendingByProgramme(request):
    return render(request, "spending_by_programme_subprogramme.html")


def latest_department_list(request):
    url = reverse("department-list",
                  args=(FinancialYear.get_latest_year().slug,))
    return redirect(url, permanent=False)


def department_list(request, financial_year_id):
    context = department_list_data(financial_year_id)
    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    return render(request, "department_list.html", context)


def search_result_page(request, financial_year_id):
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    context = {
        "title": "Search Results - vulekamali",
        "description": COMMON_DESCRIPTION + COMMON_DESCRIPTION_ENDING,
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "latest_year": FinancialYear.get_latest_year().slug,
        "selected_financial_year": selected_year.slug,
        "financial_years": [],
    }

    for year in FinancialYear.get_available_years():
        context["financial_years"].append(
            {
                "id": year.slug,
                "is_selected": year.slug == selected_year.slug,
                "closest_match": {
                    "is_exact_match": True,
                    "url_path": "/%s/search-result" % year.slug,
                },
            }
        )

    return render(request, "search-result.html", context)


def latest_search_result_redirect(request):
    latest_year = FinancialYear.get_latest_year()
    if latest_year is None:
        raise Http404("No financial years available for search results")

    destination = "/%s/search-result/" % latest_year.slug
    query_string = request.GET.urlencode()
    if query_string:
        destination = "%s?%s" % (destination, query_string)

    return redirect(destination)


def department_list_json(request, financial_year_id):
    response_json = json.dumps(
        department_list_data(financial_year_id),
        sort_keys=True,
        indent=4,
        separators=(",", ": "),
        cls=DjangoJSONEncoder,
    )
    return HttpResponse(response_json, content_type="application/json")


def department_page(
    request, financial_year_id, sphere_slug, government_slug, department_slug
):
    department = None
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    years = FinancialYear.get_available_years()
    for year in years:
        if year.slug == financial_year_id:
            selected_year = year
            sphere = selected_year.spheres.filter(slug=sphere_slug).first()
            if not sphere:
                raise Http404("Sphere not found")
            government = sphere.governments.filter(
                slug=government_slug).first()
            if not government:
                raise Http404("Government not found")
            department = get_department_by_slug_or_alias(government, department_slug)

    if not department:
        raise Http404("Department not found")

    if department.slug != department_slug:
        return redirect("/%s" % department.get_url_path(), permanent=True)

    financial_years_context = []
    for year in years:
        closest_match, closest_is_exact = year.get_closest_match(department)
        financial_years_context.append(
            {
                "id": year.slug,
                "is_selected": year.slug == financial_year_id,
                "closest_match": {
                    "url_path": closest_match.get_url_path(),
                    "is_exact_match": closest_is_exact,
                },
            }
        )

    # contributed_datasets = []
    # for dataset in department.get_contributed_datasets():
    #     contributed_datasets.append(
    #         {
    #             "name": dataset.name,
    #             "contributor": dataset.get_organization()["name"],
    #             "url_path": dataset.get_url_path(),
    #         }
    #     )

    # ======= main budget docs =========================
    voteDocuments = VoteDocument.objects.filter(
        department__name=department.name, financialYear=selected_year,
        dataset_category__slug="estimates-of-national-expenditure"
    )
    pdf_link = ""
    excel_link = ""
    for doc in voteDocuments:
        if doc.document_type == "PDF":
            pdf_link = doc.document_url
        else:
            excel_link = doc.document_url

    department_budget = {
        "name": department.name,
        "pdf_link": pdf_link,
        "excel_link": excel_link,
    }

    # ======= adjusted budget docs =========================
    
    adjusted_budget = VoteDocument.objects.filter(
        department__name=department.name, financialYear=selected_year,
        dataset_category__slug="adjusted-budget-vote-documents"
    )

    if adjusted_budget:
        for doc in adjusted_budget:
            if doc.document_type == "PDF":
                pdf_link = doc.document_url
            else:
                excel_link = doc.document_url

        department_adjusted_budget = {
            "name": department.name,
            "pdf_link": pdf_link,
            "excel_link": excel_link,
        }
    else:
        department_adjusted_budget = None

    print("department_adjusted_budget: ", department_adjusted_budget)


    # budget_dataset = department.get_dataset(group_name="budget-vote-documents")
    # if budget_dataset:
    #     document_resource = budget_dataset.get_resource(format="PDF")
    #     if document_resource:
    #         document_resource = resource_fields(document_resource)
    #     tables_resource = budget_dataset.get_resource(
    #         format="XLS"
    #     ) or budget_dataset.get_resource(format="XLSX")
    #     if tables_resource:
    #         tables_resource = resource_fields(tables_resource)
    #     department_budget = {
    #         "name": budget_dataset.name,
    #         "document": document_resource,
    #         "tables": tables_resource,
    #     }
    # else:
    #     department_budget = None

    

    primary_department = department.get_primary_department()

    if department.government.sphere.slug == "national":
        govt_label = "National"
    elif department.government.sphere.slug == "provincial":
        govt_label = department.government.name

    budget_actual_programmes = list(
        BudgetVSActualNationalData.objects.filter(
            department=department.name,
            financialYear=selected_year.slug[:4]
        ).values_list('programme', flat=True).distinct()
    )

    intro = department.intro or ""

    context = {
        "comments_enabled": True,
        # "subprogramme_viz_data": DepartmentSubprogrammes(department),
        # "subprog_treemap_url": get_viz_url(
        #     department, "department-viz-subprog-treemap"
        # ),
        # "prog_econ4_circles_data": DepartmentProgrammesEcon4(department),
        # "prog_econ4_circles_url": get_viz_url(
        #     department, "department-viz-subprog-econ4-circles"
        # ),
        # "subprog_econ4_bars_data": DepartmentSubprogEcon4(department),
        # "subprog_econ4_bars_url": get_viz_url(
        #     department, "department-viz-subprog-econ4-bars"
        # ),
        # "expenditure_over_time": department.get_expenditure_over_time(),
        # "budget_actual": department.get_expenditure_time_series_summary(),
        "budget_actual_programmes": budget_actual_programmes,
        "adjusted_budget_summary": get_adjusted_budget_summary(selected_year.slug, department.name),
        # "contributed_datasets": contributed_datasets if contributed_datasets else None,
        "financial_years": financial_years_context,
        "government": {
            "name": department.government.name,
            "label": govt_label,
            "slug": str(department.government.slug),
        },
        # "government_functions": [f.name for f in department.get_govt_functions()],
        "intro":intro,
        # "infra_enabled": IRMSnapshot.objects.filter(
        #      sphere__slug=department.government.sphere.slug
        # ).count(),

        "is_vote_primary": department.is_vote_primary,
        "name": department.name,
        # "projects": get_department_project_summary(govt_label, department),
        "slug": str(department.slug),
        "sphere": {
            "name": department.government.sphere.name,
            "slug": department.government.sphere.slug,
        },
        "selected_financial_year": financial_year_id,
        "selected_tab": "departments",
        "title": "%s budget %s  - vulekamali" % (department.name, selected_year.slug),
        "description": "%s department: %s budget data for the %s financial year %s"
        % (
            govt_label,
            department.name,
            selected_year.slug,
            COMMON_DESCRIPTION_ENDING,
        ),
        "department_budget": department_budget,
        "department_adjusted_budget": department_adjusted_budget,
        # "procurement_resource_links": ProcurementResourceLink.objects.filter(
        #     sphere_slug__in=(
        #         "all",
        #         department.government.sphere.slug,
        #     )
        # ),
        # "performance_resource_links": PerformanceResourceLink.objects.filter(
        #     sphere_slug__in=(
        #         "all",
        #         department.government.sphere.slug,
        #     )
        # ),
        # "in_year_monitoring_resource_links": InYearMonitoringResourceLink.objects.filter(
        #     sphere_slug__in=(
        #         "all",
        #         department.government.sphere.slug,
        #     )
        # ),
        "vote_number": department.vote_number,
        "treemap_chart": treemap_chart(selected_year.slug[:4], department.name,  govt_label),
        "bubble_graph": bubble_graph(selected_year.slug[:4], department.name,  govt_label),
        "historical_expenditure": historical_expenditure(department.name,  govt_label),
        "budget_actual_programme": budget_actual_programme(department.name,  selected_year.slug[:4], govt_label),
        "budget_actual_spending": budget_actual_spending(department.name,  govt_label),
        
        # "horizontal_bar_graph": horizontal_bar_graph(selected_year.slug[:4], department.name),
        # "histogram_graph": histogram_graph(department.name),
        # "spend_programme_graph": spend_programme_graph(department.name),
        
        
        
        "vote_primary": {
            "url_path": primary_department.get_url_path(),
            "name": primary_department.name,
            "slug": primary_department.slug,
        },
        "website_url": department.get_latest_website_url(),
    }
    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    # context["global_values"] = read_object_from_yaml(
    #     str(settings.ROOT_DIR.path("_data/global_values.yaml"))
    # )
    # context["admin_url"] = reverse(
    #     "admin:budgetportal_department_change", args=(department.pk,)
    # )
    # context["eqprs_data_enabled"] = config.EQPRS_DATA_ENABLED
    context["eqprs_data_enabled"] = True
    # context["in_year_spending_enabled"] = config.IN_YEAR_SPENDING_ENABLED

    context["public_entities"] = []

    for public_entity in PublicEntity.objects.filter(
        department__slug=department.slug,
        government=department.government
    ):
        context["public_entities"].append(
            {
                "name": public_entity.name,
                "url_path": public_entity.get_url_path(),
            }
        )

    return render(request, "department.html", context)


def category_fields(category):
    return {
        "title": category.title,
        "slug": category.slug,
        "url_path": category.get_url_path(),
        "description": category.description,
    }


def dataset_category_list(request,category_slug,financial_year_id):
    # Get the dataset
    
    
    originalBudgetGroups = [
        'appropriation-bills',
        'budget-highlights',
        'budget-reviews',
        'budget-speeches',
        'division-of-revenue-bills',
        'estimates-of-national-expenditure',
        'estimates-of-provincial-revenue-and-expenditure',
        'provincial-allocations',
        'occasional-budget-documents',
        'people-s-guides',
        'tax-pocket-guides']
    
    adjustedBudgetGroups = [
        'adjusted-estimates-of-national-expenditure',
        'adjusted-estimates-of-provincial-revenue-and-expenditure',
        'adjustments-appropriation-bills',
        'division-of-revenue-amendment-bills',
        'medium-term-budget-policy-statements',
        'medium-term-budget-policy-statement-speeches',
        'rates-and-monetary-amounts-and-amendment-of-revenue-laws-bills',
        'tax-administration-laws-amendment-bills',
        'taxation-laws-amendment-bills']
    
    category = originalBudgetGroups + adjustedBudgetGroups

    datasets = (
        Dataset.objects
        .select_related('dataset_category', 'tags', 'organisation', 'financial_year', 'sphere')
        .filter(dataset_category__slug__in = category,financial_year__slug=financial_year_id )
    )

    if not datasets.exists():
        return JsonResponse({"error": "Dataset not found"}, status=404)

    output = []

    original_categories = DatasetCategory.objects.filter(type="Original Budget").values_list("slug", flat=True)
    adjusted_categories = DatasetCategory.objects.filter(type="Adjusted Budget").values_list("slug", flat=True)

    for dataset in datasets:
        # Fetch related resources
        datasetResources = DatasetResource.objects.filter(
            dataset_id=dataset.id)
        resources_data = [
            {
                "name": r.fileName,
                "format": r.format,
                "url": r.file.path.replace("/app", "") if r.file else r.path,
            }
            for r in datasetResources
        ]

        # Prepare dataset object for JS reducer
        groups = []
        if dataset.dataset_category.slug in original_categories:
            groups.append({
                "name": dataset.dataset_category.slug,
                "type": "Original Budget"
            })
        if dataset.dataset_category.slug in adjusted_categories:
            groups.append({
                "name": dataset.dataset_category.slug,
                "type": "Adjusted Budget"
            })

        dataset_obj = {
            "sphere": [dataset.sphere.name.lower()] if dataset.sphere else [],
            "province": [dataset.province] if dataset.province else [],
            "groups": groups,
            "resources": resources_data
        }

        output.append(dataset_obj)

    return JsonResponse(output, safe=False)

def dataset_category_list_page(request):
    categories = DatasetCategory.get_all()
    context = {
        "categories":  [category_fields(c) for c in categories],
        "selected_tab": "datasets",
        "slug": "datasets",
        "name": "Datasets and Analysis",
        "title": "Datasets and Analysis - vulekamali",
        "url_path": "/datasets",
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "latest_year": FinancialYear.get_latest_year().slug,
    }
    return render(request, "datasets.html", context)

def resource_fields(resource):

    print("path: ", resource.path if resource.file == "" else resource.path)
    print("path: ", resource.path)
    print("file: ", resource.file)
    return {
        "fileName": resource.fileName,
        "file": resource.file,
        "format": resource.format,
        "path": resource.path if resource.file == "" else resource.file,
    }

def dataset_fields(dataset):
    return {
        "slug": dataset.slug,
        "title": dataset.title,
        "url_path": dataset.get_url_path(),
        "resources": [resource_fields(r) for r in dataset.resources.all()],
        "financial_year": dataset.financial_year.slug if dataset.financial_year.slug else ""
        # "organization": dataset.get_organization(),
        # "author": dataset.author,
        # "created": dataset.created_date,
        # "last_updated": dataset.last_updated_date,
        # "license": dataset.license,
        # "intro": dataset.intro,
        # "intro_short": dataset.intro_short,
        # "key_points": dataset.key_points,
        # "importance": dataset.importance,
        # "use_for": dataset.use_for,
        # "usage": dataset.usage,
        # "methodology": dataset.methodology,
       
        # "category": category_fields(dataset.category),
    }

def dataset_category_context(category_slug):
    category = DatasetCategory.objects.filter(slug=slugify(category_slug)).first()
    
    if category:
        context = {
            "datasets": [],
            "selected_tab": "datasets",
            "slug": category.slug,
            "title": category.title,
            "description": category.description,
            "url_path": category.get_url_path(),
        }
        datasets = Dataset.objects.filter(dataset_category=category)

        for dataset in datasets:
            print("dataset:", dataset.slug)
            print("dataset:", dataset.financial_year.slug)
            
            field_subset = dataset_fields(dataset)
            context["datasets"].append(field_subset)
                    
    else:
        context = {
            "datasets": [],
            "selected_tab": "datasets",
            "slug": "",
            "title": "Category Not Found",
            "description": "",
            "url_path": "/datasets",
         }
    return context

def dataset_context(category_slug, dataset_slug):
    dataset = Dataset.objects.filter(slug=slugify(dataset_slug)).first()
    # assert dataset.dataset_category.slug == category_slug

    context = {
        "selected_tab": "datasets",
        "title": "%s - vulekamali" % dataset,
        "description": dataset.description,
    }

    context.update(dataset_fields(dataset))
    
    return context

def dataset_page(request, category_slug, dataset_slug):
    
    context = dataset_context(category_slug, dataset_slug)
    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    # context["created"] = datetime.strptime(context["created"], "%Y-%m-%dT%H:%M:%S.%f")
    # context["last_updated"] = datetime.strptime(
    #     context["last_updated"], "%Y-%m-%dT%H:%M:%S.%f"
    # )
    external_resource_slugs = [
        "socio-economic-data",
        "performance-resources",
        "procurement-portals-and-resources",
    ]
    # context["guide"] = CategoryGuide.objects.filter(category_slug=category_slug).first()
    context["external_resource_page"] = category_slug in external_resource_slugs
    # context["comments_enabled"] = settings.COMMENTS_ENABLED
    return render(request, "government_dataset.html", context)

def dataset_category_page(request, category_slug):
    context = dataset_category_context(category_slug)
    context["navbar"] = MainMenuItem.objects.prefetch_related("children").all()
    context["latest_year"] = FinancialYear.get_latest_year().slug
    # context["guide"] = CategoryGuide.objects.filter(category_slug=category_slug).first()
    return render(request, "government_dataset_category.html", context)


def download_resource(request, category_slug, datasetresource_file):
    try:
        resource = DatasetResource.objects.get(file='resources/' + datasetresource_file)
        # file = str(resource.file).replace('resources/', '')
        # Construct the full file path
        file_path = os.path.join(settings.MEDIA_ROOT, str(resource.file))
    
        # Open and serve the file using FileResponse
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' does not exist.")

        # Open the file and serve it as a downloadable response
        response = FileResponse(open(file_path, 'rb'),
                                as_attachment=True, filename=resource.file.name)
        return response

    except DatasetResource.DoesNotExist:
        raise Http404("Resource not found.")
    except FileNotFoundError:
        raise Http404("File not found.")
      
def bubble_graph(financialYear, department, govt_label):    

    # Convert queryset to list of dictionaries
        
    queryset = None

    if govt_label == "National":
        queryset = ENEData.objects.filter(financialYear=financialYear, department=department) \
            .values("economicClassification4", "programme") \
            .annotate(total_value=Sum("value"))
    else:
        queryset = EPREData.objects.filter(financialYear=financialYear, department=department, government=govt_label) \
            .values("economicClassification4", "programme") \
            .annotate(total_value=Sum("value"))

    # Convert queryset to list of dictionaries
    data_list = list(queryset)

    # data_list = get_bubble_graph_items(financialYear, department, govt_label)

    # if(len(data_list) == 0):
    #     data_list = get_bubble_graph_items(financialYear, mappedDeptName, govt_label)

    # Sort by total_value (ascending order)
    sorted_data = sorted(data_list, key=itemgetter("total_value"))

    # Prepare data for the bubble chart
    data = {
        "children": [
            {
                "Name": item["economicClassification4"],
                "Programme" : item["programme"],
                "Count": float(item["total_value"]),
            }
            for item in sorted_data
        ],
        "links": []  # If you need links
    }

    return json.dumps(data).replace("'","")

def treemap_chart(financialYear, department, govt_label):

    queryset = None
    subprogrammes = None
    if govt_label == "National":
        queryset = ENEData.objects.filter(financialYear=financialYear, department=department) \
            .values("programme") \
            .annotate(total_value=Sum("value"))

        # Fetch subprogrammes and their total values
        subprogrammes = ENEData.objects.filter(financialYear=financialYear, department=department) \
            .values("programme", "subprogramme") \
            .annotate(total_value=Sum("value"))

    else:
        queryset = EPREData.objects.filter(financialYear=financialYear, department=department, government=govt_label, budgetPhase='Main appropriation') \
            .values("programme") \
            .annotate(total_value=Sum("value"))

        # Fetch subprogrammes and their total values
        subprogrammes = EPREData.objects.filter(financialYear=financialYear, department=department, government=govt_label, budgetPhase='Main appropriation') \
            .values("programme", "subprogramme") \
            .annotate(total_value=Sum("value"))

    programme_list = list(queryset)

    print("programme list: ", len(programme_list))

    subprogramme_list = list(subprogrammes)

    # Sort by total_value (ascending order)
    sorted_programmes = sorted(programme_list, key=itemgetter("total_value"))

    programme_dict = {}
    for item in sorted_programmes:
        programme_dict[item["programme"]] = {
            "name": item["programme"],
            "value": float(item["total_value"]),
            "children": []  # Placeholder for subprogrammes
        }

    # Add subprogrammes to their respective programmes
    for sub in subprogramme_list:
        programme_name = sub["programme"]
        if programme_name in programme_dict:
            programme_dict[programme_name]["children"].append({
                "name": sub["subprogramme"],
                "value": float(sub["total_value"])
            })

    # Prepare data for the bubble chart
    data = {
        "name": "root",
        "children": list(programme_dict.values()),
    }
    
    return json.dumps(data)

def get_horizontal_bar_data(request):
    subprogramme_list = []

    # Get 'econ' and 'prog' from GET parameters, defaulting to 'All' if not provided
    department = get_department_name(request)
    
    prov = request.GET.get('province', '').strip() 
    province = ''

    if prov != '':
        province = get_province(prov)
    
    econ = request.GET.get('econ', '').strip() 
    prog = request.GET.get('prog', '').strip() 
    financialYear = request.GET.get('financialYear', '').split("-")[0]; 
    queryset = None

    # Check the conditions based on 'econ' and 'prog'
    if econ == '' and prog == '':

        if province == '':
            queryset = ENEData.objects.filter(financialYear=financialYear, department=department) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))
        else:
            
            queryset = EPREData.objects.filter(financialYear=financialYear, department=department, government = province) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))
        subprogramme_list = list(queryset)
    
    elif econ != '' and prog == '':
        if province == '':
            queryset = ENEData.objects.filter(financialYear=financialYear, department=department, economicClassification4=econ) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))

        else:
            queryset = EPREData.objects.filter(financialYear=financialYear, department=department, economicClassification4=econ, government = province) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))

        subprogramme_list = list(queryset)

    elif econ == '' and prog != '':

        if province == '':
            queryset = ENEData.objects.filter(financialYear=financialYear, department=department, programme=prog) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))

        else:
            queryset = EPREData.objects.filter(financialYear=financialYear, department=department, programme=prog, government=province) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))
        subprogramme_list = list(queryset)

    elif econ != '' and prog != '':

        if province == '':
            queryset = ENEData.objects.filter(financialYear=financialYear, department=department, economicClassification4=econ, programme=prog) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))

        else:
            queryset = EPREData.objects.filter(financialYear=financialYear, department=department, economicClassification4=econ, programme=prog, government=province) \
                .values("subprogramme", "value") \
                .annotate(total_value=Sum("value"))
        subprogramme_list = list(queryset)

    # Sort the results by total_value in ascending order
    sorted_subprogrammes = sorted(subprogramme_list, key=itemgetter("total_value"))

    # Create the dictionary to send as response
    subprogramme_dict = {}
    for item in sorted_subprogrammes:
        total_value = float(item["total_value"])
        if total_value != 0:  # Only include the item if the total_value is not 0
            subprogramme_dict[item["subprogramme"]] = {
                "name": item["subprogramme"],
                "value": total_value,
            }

    # Prepare the response data for the bubble chart
    data = {
        "name": "root",
        "children": list(subprogramme_dict.values()),
    }

    # Return the data as JSON response
    return JsonResponse(data, safe=False)

def get_economicClassification(request):
    
    financial_year = request.GET.get('financialYear', '').split("-")[0]; 
    prov = request.GET.get('province', '').strip() 
    department = get_department_name(request)

    econ_classifications = None
    
    if prov == '':
        econ_classifications = ENEData.objects.filter(financialYear=financial_year, department=department).values_list("economicClassification4", flat=True).distinct()
    else:
        province = get_province(prov)
        econ_classifications = EPREData.objects.filter(financialYear=financial_year, department=department, government = province).values_list("economicClassification4", flat=True).distinct()

    econList = list(econ_classifications)
    data = json.dumps(econList)

    return JsonResponse(data, safe=False)

def get_programmes(request):
    
    department = get_department_name(request)

    prov = request.GET.get('province', '').strip()
    if prov in ['undefined', 'null', 'datasets']:
        return JsonResponse("[]", safe=False)

    econ = request.GET.get('econ', '').strip() 
    financialYear = request.GET.get('financialYear', '').strip()
    if financialYear in ['', 'undefined', 'null'] or not department:
        return JsonResponse("[]", safe=False)

    province = ''
    if prov:
        province = get_province(prov)
        if province is None:
            return JsonResponse("[]", safe=False)

    financialYear = financialYear.split("-")[0]
    prog = None

    if(econ == ''):
        if prov == '':
            prog = ENEData.objects.filter(financialYear=financialYear, department=department).values_list("programme", flat=True).distinct()
       
        else:
            prog =  EPREData.objects.filter(financialYear=financialYear, department=department, government = province).values_list("programme", flat=True).distinct()
    else:
        if prov == '':
            prog = ENEData.objects.filter(financialYear=financialYear, department=department, economicClassification4 = econ).values_list("programme", flat=True).distinct()

        else:
            prog = EPREData.objects.filter(financialYear=financialYear, department=department,
                                           economicClassification4=econ, government=province).values_list("programme", flat=True).distinct()

    progList = list(prog)
    data = json.dumps(progList)

    return JsonResponse(data, safe=False)

def get_historical_expenditure(department, govt_label):

    if govt_label == "National":
        queryset = BudgetVSActualNationalData.objects.filter(department=department) \
            .values("financialYear", "budgetPhase") \
            .annotate(total_value=Sum("value"))
    else:
        queryset = BudgetVSActualProvincialData.objects.filter(department=department, government=govt_label) \
            .values("financialYear", "budgetPhase") \
            .annotate(total_value=Sum("value"))

    return list(queryset)

def historical_expenditure(department, govt_label):

    history_list = get_historical_expenditure(department, govt_label)

    phase_priority = {
        "Audit Outcome": 5,
        "Audited Outcome": 4,
        "Final Appropriation": 3,
        "Adjusted appropriation": 2,
        "Main appropriation": 1,
    }

    filtered_history = {}
    for item in history_list:
        year = item["financialYear"]
        current = filtered_history.get(year)

        if current is None or phase_priority.get(item["budgetPhase"], 0) > phase_priority.get(
            current["budgetPhase"], 0
        ):
            filtered_history[year] = item

    sorted_history = sorted(filtered_history.values(), key=itemgetter("financialYear"))

    data = {
        "children": [
            {
                "Name": item["financialYear"],
                "Count": float(item["total_value"]),
                "BudgetPhase": item["budgetPhase"],
                "SeriesType": (
                    "historical"
                    if item["budgetPhase"] in ("Audit Outcome", "Audited Outcome", "Final Appropriation")
                    else "planned"
                ),
            }
            for item in sorted_history
        ],
        "links": []  # If you need links
    }
    return json.dumps(data).replace("'","")

def budget_actual_spending(department, govt_label):

    if govt_label == "National":
        queryset = BudgetVSActualNationalData.objects.filter(department=department) \
            .values("financialYear","budgetPhase") \
            .annotate(total_value=Sum("value"))

    else:
        queryset = BudgetVSActualProvincialData.objects.filter(department=department, government=govt_label) \
            .values("financialYear","budgetPhase") \
            .annotate(total_value=Sum("value"))

    budget_actual_list = list(queryset)

    budget_actual_data = sorted(budget_actual_list, key=itemgetter("financialYear"))

    data = {
        "children": [           
            {
                "name": item["financialYear"],
                "value": float(item["total_value"]),
                "budgetPhase": item["budgetPhase"],
            }
            for item in budget_actual_data
        ],        
    } 

    return json.dumps(data).replace("'","").strip()

def get_budget_actual_programmes(department, financialYear, govt_label):

    if govt_label == "National":
        progQueryset = (
            BudgetVSActualNationalData.objects
            .filter(department=department, financialYear=financialYear)
            .values_list("programme", flat=True)
            .distinct()
        )
    else:
        progQueryset = (
            BudgetVSActualProvincialData.objects
            .filter(department=department, financialYear=financialYear, government=govt_label)
            .values_list("programme", flat=True)
            .distinct()
        )
    return list(progQueryset)


def budget_actual_programme(department, financialYear, govt_label):
                        
    prog_list = get_budget_actual_programmes(
        department, financialYear, govt_label)

    data_list = []

    for prog in prog_list:

        if govt_label == "National":
            queryset = (
                BudgetVSActualNationalData.objects
                .filter(department=department, programme=prog)
                .values("financialYear", "budgetPhase")
                .annotate(total_value=Sum("value"))
            )
        else:
            queryset = (
                BudgetVSActualProvincialData.objects
                .filter(department=department, programme=prog, government=govt_label)
                .values("financialYear", "budgetPhase")
                .annotate(total_value=Sum("value"))
            )

        budget_actual_list = list(queryset)

        budget_actual_data = sorted(budget_actual_list, key=itemgetter("financialYear"))

        data = {
            "children": [           
                {
                    "programme": prog,
                    "name": item["financialYear"],
                    "value": float(item["total_value"]),
                    "budgetPhase": item["budgetPhase"],
                }
                for item in budget_actual_data
            ],        
        }

        data_list.append(data)    

    return json.dumps(data_list).replace("'","").strip()


def format_values(value):
    def format_number(num):
        # Keep up to 3 decimals, remove trailing zeros
        return f"{num:,.2f}".rstrip('0').rstrip('.')

    if value >= 1e12:
        return f"R {format_number(value / 1e12)} Trillion"
    elif value >= 1e9:
        return f"R {format_number(value / 1e9)} Billion"
    elif value >= 1e6:
        return f"R {format_number(value / 1e6)} Million"
    elif value >= 1e3:
        return f"R {format_number(value / 1e3)} Thousand"
    else:
        return f"R {format_number(value)}"


def consolidation_budget_year_queryset(financial_year_start):
    base_queryset = ConsolidationData.objects.filter(
        financialYear=financial_year_start,
    )

    queryset = base_queryset.filter(
        financialYear=financial_year_start,
        budgetYear=financial_year_start,
    )
    if queryset.exists():
        return queryset

    queryset = base_queryset.filter(Q(budgetYear__isnull=True) | Q(budgetYear=""))
    if queryset.exists():
        return queryset

    tagged_queryset = base_queryset.exclude(Q(budgetYear__isnull=True) | Q(budgetYear=""))
    selected_budget_year = (
        tagged_queryset.filter(budgetYear__lte=financial_year_start)
        .order_by("-budgetYear")
        .values_list("budgetYear", flat=True)
        .first()
    )
    if selected_budget_year is None:
        selected_budget_year = (
            tagged_queryset.order_by("-budgetYear")
            .values_list("budgetYear", flat=True)
            .first()
        )

    if selected_budget_year is None:
        return base_queryset.none()

    return base_queryset.filter(budgetYear=selected_budget_year)


def consolidation_function_group_queryset(function_group, financial_year_start):
    return consolidation_budget_year_queryset(financial_year_start).filter(
        functionGroup__iexact=function_group,
    )


def consolidation_function_group_history(function_group):
    yearly_data = []
    financial_years = (
        ConsolidationData.objects.filter(functionGroup__iexact=function_group)
        .values_list("financialYear", flat=True)
        .distinct()
        .order_by("financialYear")
    )

    for financial_year in financial_years:
        year_total = (
            consolidation_function_group_queryset(function_group, financial_year)
            .aggregate(total=Sum("value"))
            .get("total")
        )
        if year_total is None:
            continue
        yearly_data.append(
            {
                "financialYear": financial_year,
                "year_total": float(year_total),
            }
        )

    return yearly_data


def budget_actual_year_queryset(model_class, financial_year_start, budget_phases=None):
    budget_phases = budget_phases or ["Main appropriation"]

    for budget_phase in budget_phases:
        base_queryset = model_class.objects.filter(
            financialYear=financial_year_start,
            budgetPhase=budget_phase,
        )

        queryset = base_queryset.filter(Q(budgetYear__isnull=True) | Q(budgetYear=""))
        if queryset.exists():
            return queryset

        queryset = base_queryset.filter(budgetYear=financial_year_start)
        if queryset.exists():
            return queryset

        tagged_queryset = base_queryset.exclude(Q(budgetYear__isnull=True) | Q(budgetYear=""))
        selected_budget_year = (
            tagged_queryset.filter(budgetYear__lte=financial_year_start)
            .order_by("-budgetYear")
            .values_list("budgetYear", flat=True)
            .first()
        )
        if selected_budget_year is None:
            selected_budget_year = (
                tagged_queryset.order_by("-budgetYear")
                .values_list("budgetYear", flat=True)
                .first()
            )

        if selected_budget_year is not None:
            return base_queryset.filter(budgetYear=selected_budget_year)

    return model_class.objects.none()


def national_budget_year_queryset(financial_year_start):
    return budget_actual_year_queryset(BudgetVSActualNationalData, financial_year_start)


def provincial_budget_year_queryset(financial_year_start):
    target_year = int(financial_year_start)
    expected_province_count = 9

    for year in range(target_year, 0, -1):
        queryset = budget_actual_year_queryset(
            BudgetVSActualProvincialData,
            str(year),
            budget_phases=["Main appropriation", "Baseline"],
        )

        province_count = queryset.values("government").distinct().count()
        if province_count >= expected_province_count:
            return queryset

    return BudgetVSActualProvincialData.objects.none()


def budget_actual_history(model_class, extra_filters=None):
    yearly_data = []
    extra_filters = extra_filters or {}
    financial_years = (
        model_class.objects.filter(**extra_filters)
        .values_list("financialYear", flat=True)
        .distinct()
        .order_by("financialYear")
    )

    for financial_year in financial_years:
        year_total = (
            budget_actual_year_queryset(model_class, financial_year)
            .filter(**extra_filters)
            .aggregate(total=Sum("value"))
            .get("total")
        )
        if year_total is None:
            continue
        yearly_data.append(
            {
                "financialYear": financial_year,
                "year_total": float(year_total),
            }
        )

    return yearly_data


def consolidated_spending(financialYear):
    financial_year_start = financialYear.split("-")[0]
    
    queryset = consolidation_budget_year_queryset(financial_year_start) \
        .values("functionGroup") \
        .annotate(total_value=Sum("value"))

    data_list = list(queryset)

    # Sort by total_value (ascending order)
    sorted_data = sorted(data_list, key=itemgetter("total_value"))

    total_budget = sum([item["total_value"] for item in queryset])

    print("total budget:", total_budget)

    # Prepare data for the bubble chart
    data = {
        "children": [
            {
                "id": slugify(item["functionGroup"]),
                "name": item["functionGroup"],
                "value": float(item["total_value"]),
                "percentage": float(item["total_value"]) / float(total_budget) * 100 if total_budget else 0,
                "url": f"/budget-summary/consolidated_spending_details/{financialYear}/{slugify(item['functionGroup'])}/"
            }
            for item in sorted_data
        ],
        "links": []  # If you need links
    }    
    return json.dumps(data)

def consolidated_spending_total(financialYear):
    financial_year_start = financialYear.split("-")[0]

    queryset = consolidation_budget_year_queryset(financial_year_start) \
        .values("functionGroup") \
        .annotate(total_value=Sum("value"))

    data_list = list(queryset)
    total = 0

    for item in data_list:
        total += int(item["total_value"])
    
    return format_values(total)


def consolidated_spending_details(request, financial_year_id, focus_slug):

    try:
        # Latest financial year
        financialYear = financial_year_id.split("-")[0]

        function_group = focus_slug.replace('-', ' ').title()

        # Get queryset for the selected Function Group
        qs = consolidation_function_group_queryset(function_group, financialYear)
        # if not qs.exists():
        #     raise Http404(f"No data found for {function_group}")

        # Group by Economic Classification for bar chart
        summary = list(
            qs.values('economicClassification3')
              .annotate(total_value=Sum('value'))
              .order_by('-total_value')
        )

        total_budget = qs.aggregate(total=Sum('value'))['total'] or Decimal(0)
        total_budget_float = float(total_budget)

        # Category-level data for the bar chart
        category_data = []
        for item in summary:
            econ_name = item['economicClassification3']
            total_val_float = float(item['total_value'])
            category_data.append({
                "id": slugify(econ_name),
                "name": econ_name,
                "value": total_val_float,
                "percentage": (total_val_float / total_budget_float * 100) if total_budget_float else 0
            })

        # category_data = {
        # "children": [
        #         {
        #             "id": slugify(item['economicClassification3']),
        #             "name": item['economicClassification3'],
        #             "value": float(item['total_value']),
        #             "percentage": round((float(item['total_value']) / total_budget_float * 100), 1) if total_budget_float else 0
        #         }
        #         for item in summary
        #     ],
        # }               

        # Yearly trend for line chart
        yearly_data = consolidation_function_group_history(function_group)
        
        # Context
        context = {
            'function_group': function_group,
            'financial_year': financial_year_id,
            'total_budget': format_values(int(total_budget_float)),
            'category_data': json.dumps(category_data),
            'yearly_data': json.dumps(yearly_data),
            'navbar': MainMenuItem.objects.prefetch_related("children").all(),
        }
        
        return render(request, "budgetsummary/consolidated_focus_detail.html", context)

    except Exception as e:
        print(f"Error in budget_summary_detail: {e}")
        raise


def national_spending_details(request, financial_year_id, department):
    try:
        # --- Get the latest financial year ---
        financialYear = financial_year_id.split("-")[0]

        department_query = Department.objects.filter(slug=department).values("name")
        department_name = list(department_query)[0].get('name')

        # --- Query base dataset ---
        qs = national_budget_year_queryset(financialYear).filter(department=department_name)

        # =========== Pie graph

        function_summary = (
            qs.values("functionGroup1")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")
        )

        function_data = [
            {
                "name": item["functionGroup1"],
                "value": float(item["total_value"]),
            }
            for item in function_summary
        ]

        # ============ Bar Graph

        econ_summary = (
            qs.values("economicClassification1")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")
        )

        econ_data = [
            {
                "name": item["economicClassification1"],
                "value": float(item["total_value"]),
            }
            for item in econ_summary
        ]

        # =============Horizontal Bar graph
        item_summary = (
            qs.values("economicClassification3")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")[:10]
        )

        top_items_data = [
            {
                "id": slugify(item["economicClassification3"]),
                "name": item["economicClassification3"],
                "value": float(item["total_value"]),
            }
            for item in item_summary
        ]

        # ==========Line Graph 
        yearly_data = budget_actual_history(
            BudgetVSActualNationalData,
            {"department": department_name},
        )

        total_budget = qs.aggregate(total=Sum("value"))["total"] or Decimal(0)
        total_budget_float = float(total_budget)

        national_budget_summary = {
            
            "function_data": json.dumps(function_data),
            "econ_data": json.dumps(econ_data),
            "top_items_data": json.dumps(top_items_data),
            "yearly_data": json.dumps(yearly_data),
        }

        context = {
            "budget_type": "National Budget Summary",
            "department": department_name,
            "total_budget": national_budget_spending_total(financial_year_id, department_name),
            "financial_year": financial_year_id,
            "national_budget_summary": json.dumps(national_budget_summary),
            "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        }

        return render(request, "budgetsummary/national_provincial_focus_detail.html", context)

    except Exception as e:
        print(f"Error in budget_summary_detail: {e}")
        raise   
    
def provincial_spending_details(request, financial_year_id, province):
    try:
        # --- Get the latest financial year ---
        financialYear = financial_year_id.split("-")[0]

        government_name = Government.objects.filter(slug=province).values("name")[0].get('name')
        print('government name', government_name)

        # --- Query base dataset ---
        qs = BudgetVSActualProvincialData.objects.filter(
            government=government_name,
            financialYear=financialYear,
        )

        # =========== Pie graph

        function_summary = (
            qs.values("functionGroup1")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")
        )

        function_data = [
            {
                "name": item["functionGroup1"],
                "value": float(item["total_value"]),
            }
            for item in function_summary
        ]

        # ============ Bar Graph

        econ_summary = (
            qs.values("economicClassification1")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")
        )

        econ_data = [
            {
                "name": item["economicClassification1"],
                "value": float(item["total_value"]),
            }
            for item in econ_summary
        ]

        # =============Horizontal Bar graph
        item_summary = (
            qs.values("economicClassification3")
            .annotate(total_value=Sum("value"))
            .order_by("-total_value")[:10]
        )

        top_items_data = [
            {
                "id": slugify(item["economicClassification3"]),
                "name": item["economicClassification3"],
                "value": float(item["total_value"]),
            }
            for item in item_summary
        ]

        # ==========Line Graph 
        yearly_data = budget_actual_history(
            BudgetVSActualProvincialData,
            {"government": government_name},
        )

        national_budget_summary = {            
            "function_data": json.dumps(function_data),
            "econ_data": json.dumps(econ_data),
            "top_items_data": json.dumps(top_items_data),
            "yearly_data": json.dumps(yearly_data),
        }

        context = {
            "budget_type": "Provincial Budget Summary",
            "total_budget": provincial_budget_spending_total(financial_year_id, government_name),
            "department": government_name,
            "financial_year": financial_year_id,
            "national_budget_summary": json.dumps(national_budget_summary),
            "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        }

        return render(request, "budgetsummary/national_provincial_focus_detail.html", context)

    except Exception as e:
        print(f"Error in budget_summary_detail: {e}")
        raise   
    

def national_budget_spending(financialYear):
    financial_year_start = financialYear.split("-")[0]

    queryset = national_budget_year_queryset(financial_year_start) \
        .values("department") \
        .annotate(total_value=Sum("value"))

    data_list = list(queryset)

    # Sort by total_value (ascending order)
    sorted_data = sorted(data_list, key=itemgetter("total_value"))

    # Prepare data for the bubble chart
    data = {
        "children": [
            {
                "name": item["department"],
                "value": float(item["total_value"]),
                "url": f"/budget-summary/national_budget_summary/{financialYear}/{slugify(item['department'])}/"
            }
            for item in sorted_data
        ],
        "links": []  # If you need links
    }
    
    return json.dumps(data)

def national_budget_spending_total(financialYear, department=None):
    financial_year_start = financialYear.split("-")[0]

    if department:
        queryset = national_budget_year_queryset(financial_year_start).filter(department=department) \
            .values("department") \
            .annotate(total_value=Sum("value"))
    else:
        queryset = national_budget_year_queryset(financial_year_start) \
            .values("department") \
            .annotate(total_value=Sum("value"))

    data_list = list(queryset)
    total = 0

    for item in data_list:
        total += int(item["total_value"])

    return format_values(total)


def provincial_budget_spending_total(financialYear, province= None):
    financial_year_start = financialYear.split("-")[0]

    if province:
        queryset = provincial_budget_year_queryset(financial_year_start).filter(government=province) \
            .values("government") \
            .annotate(total_value=Sum("value"))
    else:
        queryset = provincial_budget_year_queryset(financial_year_start) \
            .values("government") \
            .annotate(total_value=Sum("value"))

    data_list = list(queryset)
    total = 0

    for item in data_list:
        total += int(item["total_value"])

    return format_values(total)


def provincial_budget_spending(financialYear):
    financial_year_start = financialYear.split("-")[0]

    queryset = provincial_budget_year_queryset(financial_year_start) \
        .values("government") \
        .annotate(total_value=Sum("value"))

    data_list = list(queryset)

    # Sort by total_value (ascending order)
    sorted_data = sorted(data_list, key=itemgetter("total_value"))

    # Prepare data for the bubble chart
    data = {
        "children": [
            {
                "name": item["government"],
                "value": float(item["total_value"]),
                "url": f"/budget-summary/provincial_budget_summary/{financialYear}/{slugify(item['government'])}/"
            }
            for item in sorted_data
        ],
        "links": []  # If you need links
    }
    
    return json.dumps(data)


def budget_summary(request, financial_year_id= None):

    if financial_year_id is None:
        financial_year_id = FinancialYear.get_latest_year().slug
    selected_year = get_object_or_404(FinancialYear, slug=financial_year_id)

    context = {
        "consolidated_spending": consolidated_spending(selected_year.slug),
        "consolidated_spending_total": consolidated_spending_total(selected_year.slug),
        "national_budget_spending_total": national_budget_spending_total(selected_year.slug),
        "provincial_budget_spending_total": provincial_budget_spending_total(selected_year.slug),
        "national_budget_spending" : national_budget_spending(selected_year.slug),
        "provincial_budget_spending" : provincial_budget_spending(selected_year.slug),
        "navbar": MainMenuItem.objects.prefetch_related("children").all(),
        "financial_years": [],
        "selected_financial_year": selected_year.slug,
        "latest_year": FinancialYear.get_latest_year().slug
    }

    for year in FinancialYear.get_available_years():
        is_selected = year.slug == financial_year_id
        context["financial_years"].append(
            {
                "id": year.slug,
                "is_selected": is_selected,
                "closest_match": {
                    "is_exact_match": True,
                    "url_path": "/budget-summary/%s" % year.slug,
                },
            }
        )
    
    return render(request, "budget-summary.html", context)


def budget_summary_detail(request, focus_slug):

    try:
        # Latest financial year
        financialYear = FinancialYear.get_latest_year().slug
        financialYearFormatted = financialYear.split("-")[0]

        function_group = focus_slug.replace('-', ' ').title()

        # Get queryset for the selected Function Group
        qs = consolidation_function_group_queryset(function_group, financialYearFormatted)
        if not qs.exists():
            raise Http404(f"No data found for {function_group}")

        # Group by Economic Classification for bar chart
        summary = list(
            qs.values('economicClassification3')
              .annotate(total_value=Sum('value'))
        )

        total_budget = qs.aggregate(total=Sum('value'))['total'] or Decimal(0)
        total_budget_float = float(total_budget)

        # Category-level data for the bar chart
        category_data = []
        for item in summary:
            econ_name = item['economicClassification3']
            total_val_float = float(item['total_value'])
            category_data.append({
                "id": slugify(econ_name),
                "name": econ_name,
                "value": total_val_float,
                "financialYear": financialYear,
                "percentage": (total_val_float / total_budget_float * 100) if total_budget_float else 0
            })

        # Yearly trend for line chart
        yearly_data = consolidation_function_group_history(function_group)

        # Context
        context = {
            'function_group': function_group,
            'financial_year': financialYearFormatted,
            'total_budget': total_budget_float,
            'category_data': json.dumps(category_data),
            'yearly_data': json.dumps(yearly_data),
            'navbar': MainMenuItem.objects.prefetch_related("children").all(),
        }

        return render(request, "budgetsummary/consolidated_focus_detail.html", context)

    except Exception as e:
        print(f"Error in budget_summary_detail: {e}")
        raise


def get_department_name(request):
    dep = request.GET.get('department', '') 
    
    department_query= Department.objects.filter(slug=dep).values("name")
    if not department_query.exists():
        return ""

    department_name = list(department_query)[0].get('name')
    return department_name

def get_province(prov):    
    government = Government.objects.filter(slug=prov).first()
    return government.name if government else None

def get_adjusted_budget_summary(financialYear, department):
    queryset = AENEData.objects.filter(department=department, financialYear=financialYear.split("-")[0]) \
        .values("amountKind", "budgetPhase", "programme", "subprogramme", "economicClassification2", "economicClassification3", "value")

    data_list = list(queryset)

    if not data_list:
        return None

    # 1. Adjustment by type
    adjustment_by_type =  defaultdict(float)
    for item in data_list:
        budgetPhase = item["budgetPhase"]
        value = float(item["value"])
        adjustment_by_type[budgetPhase] += value

    adjustment_by_type = [
        {
            "name": k,
            "value": v,
            "type": "kind"
        }
        for k, v in adjustment_by_type.items()
    ]

    # 2. Adjustment by programme
    adjustment_by_programme = defaultdict(float)
    for item in data_list:
        programme = item["programme"]
        value = float(item["value"])
        adjustment_by_programme[programme] += value

    adjustment_by_prog = [
        {
            "name": k,
            "value": v,
        }
        for k, v in adjustment_by_programme.items()
    ]
    
    # 3. Adjustment by economic classification
    econ = defaultdict(float)
    for item in data_list:
        # econ2 = item["economicClassification2"]
        econ3 = item["economicClassification3"]
        value = float(item["value"] or 0)
        econ[econ3] += value

    # adjustment_by_econ = [
    #     {
    #         "economicClassification2": k, "economicClassification3": dict(v)
    #     }
    #     for k, v in econ.items()
    # ]

    adjustment_by_econ = [
        {
            "name": k,
            "value": v,
        }
        for k, v in econ.items()
    ]

    # 4. Veriments

    def filter_rows(**kwargs):

        def norm(v):
            return str(v).strip().lower() if v is not None else ""

        results = []
        for row in data_list:
            match = True
            for key, val in kwargs.items():
                actual = norm(row.get(key))
                expected = norm(val)

                if actual != expected:
                    match = False
                    break

            if match:
                results.append(row)

        return results

    veriments = filter_rows(
        budgetPhase="Utilisation of unspend funds - Virements & Shifts")
    tota_virements = sum(float(item["value"]) for item in veriments)

    # 5. Special approipriations
    special_approp = filter_rows(budgetPhase="Special appropriation")
    total_special_approp = sum(float(item["value"]) for item in special_approp)

    # 6. Direct charges
    direct_charges_by_subprogramme = defaultdict(float)
    direct_charges_filter = filter_rows(programme="Direct charge against the National Revenue Fund")
    for item in direct_charges_filter:
        subProgramme = item["subprogramme"]
        value = float(item["value"])
        direct_charges_by_subprogramme[subProgramme] += value

    total = sum(float(item["value"]) for item in direct_charges_filter)
    direct_charges = [
        {
            "label": k,
            "amount": v,
            "percentage": (float(v) / total) * 100 if total else 0,
        }
        for k, v in direct_charges_by_subprogramme.items()
    ]

    # 7. Total adjustmenst

    total_voted = sum(float(
        item["value"]) for item in data_list if item["budgetPhase"] == 'Appropriation')
    total_adjustment = sum(float(
        item["value"]) for item in data_list if item["budgetPhase"] == 'Total adjustments')
    total_unforeseeable = sum(float(
        item["value"]) for item in data_list if item["budgetPhase"] == 'Unforeseeable/unavoidable')
    # total_adjustment = total_adjusted - total_voted
    percent_change = (total_adjustment / total_voted * 100) if total_voted != 0 else 0

    summary = {
        "by_type": json.dumps(adjustment_by_type) if adjustment_by_type else None,
        "total_change": {
            "amount": total_adjustment,
            "percentage": percent_change,
        },
        "econ_classes": json.dumps(adjustment_by_econ) if adjustment_by_econ else None,
        "programmes": json.dumps(adjustment_by_prog) if adjustment_by_prog else None,
        # "virements": {
        #     "label": "virements and shifts",
        #     "amount": tota_virements,
        #     "percentage": 100
        #     * (tota_virements / float(total_voted)) if total_voted != 0 else 0,
        # },
        "unforeseeable":{
            "label": "Unforeseeable / Unavoidable",
            "amount": total_unforeseeable,
            "percentage": (float(total_unforeseeable) / float(total_voted)) * 100 if total_voted != 0 else 0,
        },
        "special_appropriation": {
            "amount": total_special_approp,
            "percentage": (float(total_special_approp) / float(total_voted)) * 100 if total_voted != 0 else 0,
        },
        "direct_charges": direct_charges,        
        "department_data_csv": None,
        "dataset_detail_page": None,
    }

    return summary
