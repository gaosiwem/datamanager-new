from django.contrib import admin
from django.conf.urls import url
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from public_entities import views
from django.views.decorators.cache import cache_page


CACHE_MINUTES_SECS = 60 * 5  # minutes

public_entity_urlpatterns = [
    url(
        r"^$", cache_page(CACHE_MINUTES_SECS)(views.public_entity_page), name="public-entity"
    ),
]

urlpatterns = [
    # Public Entities
    url(r"^$", views.latest_public_entity_list, name="public_entities"),
    
    #Public Entities List
    url(
        r"^latest/?$",
        views.latest_public_entity_list,
        name="latest-public-entity-list",
    ),
    url(
        r"^(?P<financial_year_id>\d{4}-\d{2})/?$",
        cache_page(CACHE_MINUTES_SECS)(views.public_entity_list),
        name="public-entity-list",
    ),
    # # Public Entity detail
    # # - National
    url(
        r"^(?P<financial_year_id>\d{4}-\d{2})/national/(?P<public_entity_slug>[\w-]+)/?$",
        include((public_entity_urlpatterns, "national"), namespace="national"),
        kwargs={"sphere_slug": "national", "government_slug": "south-africa"},
        name="national-public-entity",
    ),
    # # Public Entities List
    # path(
    #     r"^public-entities$",
    #     views.public_entity_list,
    #     name="public-entity-list",
    # ),
]
