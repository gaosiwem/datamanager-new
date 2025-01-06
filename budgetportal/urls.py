
from django.contrib import admin
from django.conf import settings
from django.urls import re_path as url
from django.conf.urls import include, static, url
from django.contrib.sitemaps import views as sitemap_views
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import include, path
from django.views.decorators.cache import cache_page
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.core import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from . import views

CACHE_MINUTES_SECS = 60 * 5  # minutes

department_urlpatterns = [
    url(
        r"^$", cache_page(CACHE_MINUTES_SECS)(views.department_page), name="department"
    )]

urlpatterns = [
    # Homepage
    url(r"^$", cache_page(CACHE_MINUTES_SECS)
        (views.homepage), name="home"),
    url(
        r"^glossary/?$",
        cache_page(CACHE_MINUTES_SECS)(views.glossary),
        name="glossary",
    ),
    url(
        r"^learning-resources/?$",
        lambda request: redirect(
            "/videos/", permanent=True),
        name="learning-resources",
    ),
    url(
        r"^videos/?$",
        cache_page(CACHE_MINUTES_SECS)(views.videos),
        name="videos",
    ),
    url(
        r"^terms-and-conditions/?$",
        cache_page(CACHE_MINUTES_SECS)(views.terms_and_conditions),
        name="terms-and-conditions",
    ),
    url(
        r"^resources/?$",
        cache_page(CACHE_MINUTES_SECS)(views.resources),
        name="resources",
    ),
    url(r"^faq/?$", cache_page(CACHE_MINUTES_SECS)(views.faq), name="faq"),
    url(r"^about/?$", cache_page(CACHE_MINUTES_SECS)
        (views.about), name="about"),
    url(r"^spendingByProgramme/?$", cache_page(CACHE_MINUTES_SECS)
        (views.spendingByProgramme), name="spendingByProgramme"),
    # Department List
    url(
        r"^latest/departments$",
        views.latest_department_list,
        name="latest-department-list",
    ),
    url(
        r"^(?P<financial_year_id>\d{4}-\d{2})/departments$",
        cache_page(CACHE_MINUTES_SECS)(views.department_list),
        name="department-list",
    ),

    url(r"^performance/", include("performance.urls")),
    url(r"^public-entities/", include("public_entities.urls")),
    
    # Provincial Infrastructure projects
    url(r"^provincial-infrastructure/", include("provincial_infrastructure.urls")),

    # Infrastructure projects
    url(
        r"^infrastructure-projects/?$",
        cache_page(CACHE_MINUTES_SECS)(views.infrastructure_project_list),
        name="infrastructure-project-list",
    ),
    url(
        r"^json/infrastructure-projects.json$",
        cache_page(CACHE_MINUTES_SECS)(views.infrastructure_projects_overview_json),
    ),
    url(
        r"^json/infrastructure-projects/(?P<project_slug>[\w-]+).json$",
        cache_page(CACHE_MINUTES_SECS)(views.infrastructure_project_detail_json),
    ),
    # url(
    #     r"^infrastructure-projects/(?P<project_slug>[\w-]+)$",
    #     cache_page(CACHE_MINUTES_SECS)(views.infrastructure_project_detail),
    #     name="infrastructure-projects",
    # ),

    # Department detail
    # - National
    # url(
    #     r"^(?P<financial_year_id>\d{4}-\d{2})/national/departments/(?P<department_slug>[\w-]+)/",
    #     include((department_urlpatterns, "national"), namespace="national"),
    #     kwargs={"sphere_slug": "national", "government_slug": "south-africa"},
    #     name="national-department",
    # ),

    url(
        r"^(?P<financial_year_id>\d{4}-\d{2})/national/departments/(?P<department_slug>[\w-]+)/",
        include((department_urlpatterns, "national"), namespace="national"),
        kwargs={"sphere_slug": "national", "government_slug": "south-africa"},
        name="national-department",
    ),

    url(
        r"^datasets/?$",
        cache_page(CACHE_MINUTES_SECS)(views.dataset_category_list_page),
        name="dataset-landing-page",
    ),
    url(
        r"^datasets/(?P<category_slug>[-\w]+)/?$",
        cache_page(CACHE_MINUTES_SECS)(views.dataset_category_page),
        name="dataset-category",
    ),
    
    # Detaset detail
    url(
        r"^datasets/(?P<category_slug>[-\w]+)/(?P<dataset_slug>[-\w]+)/?$",
        cache_page(CACHE_MINUTES_SECS)(views.dataset_page),
        name="dataset",
    ),
     url(
        r"^datasets/(?P<category_slug>[-\w]+)/resources/(?P<datasetresource_file>[^/]+\.[a-zA-Z0-9]+)/?$",
        cache_page(CACHE_MINUTES_SECS)(views.download_resource),
        name="download_resource",
    ),
    # Admin
    url(r"^admin/", admin.site.urls),
    # url(r"^admin/bulk_upload/template", bulk_upload.template_view),

    # path('admin/', admin.site.urls),
    # path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('allauth.urls')),
    url(r"^cms/", include(wagtailadmin_urls)),
    url(r"^documents/", include(wagtaildocs_urls)),
    url(r"^", include(wagtail_urls)),
]
