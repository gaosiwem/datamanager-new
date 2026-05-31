import logging
from urllib.parse import quote

from django.http import JsonResponse
from haystack.query import SearchQuerySet

from .models import Dataset, Department, FinancialYear

logger = logging.getLogger(__name__)

LANDING_PAGE_SIZE = 3
FACET_PAGE_SIZE = 5
VALID_VIEWS = {"departments", "datasets"}


def _clean_phrase(raw_phrase):
    return (raw_phrase or "").strip()


def _serialise_result(result):
    url = getattr(result, "url_path", "") or ""
    if url and not url.startswith("/"):
        url = "/%s" % url

    return {
        "title": getattr(result, "title", "") or "",
        "url": url,
        "snippet": getattr(result, "snippet", "") or "",
        "contributor": getattr(result, "contributor", "") or "",
        "source": {
            "text": getattr(result, "source_text", "") or "",
            "url": getattr(result, "source_url", "") or "",
        },
    }


def _normalise_facet_counts(raw_counts):
    if isinstance(raw_counts, dict):
        return {str(key): int(value) for key, value in raw_counts.items()}

    counts = {}
    for item in raw_counts or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            counts[str(item[0])] = int(item[1])
        elif isinstance(item, dict):
            key = item.get("name") or item.get("value")
            if key is not None:
                counts[str(key)] = int(item.get("count", 0))
    return counts


def _build_other_years(model, phrase, current_year, result_group=None):
    search = SearchQuerySet().models(model).auto_query(phrase).facet("financial_year")
    if result_group:
        search = search.filter(result_group=result_group)

    try:
        facet_counts = search.facet_counts()
        raw_year_counts = facet_counts.get("fields", {}).get("financial_year", [])
        year_counts = _normalise_facet_counts(raw_year_counts)
    except Exception:
        logger.exception("Falling back to per-year search counts for %s", model.__name__)
        year_counts = {}
        base_search = SearchQuerySet().models(model).auto_query(phrase)
        if result_group:
            base_search = base_search.filter(result_group=result_group)
        for year in FinancialYear.get_available_years():
            year_counts[year.slug] = base_search.filter(financial_year=year.slug).count()

    output = []
    for year in FinancialYear.get_available_years():
        if year.slug == current_year:
            continue

        count = year_counts.get(year.slug, 0)
        if count < 1:
            continue

        output.append(
            {
                "count": count,
                "name": year.slug,
                "url": "/%s/search-result?search=%s&view=%s"
                % (year.slug, quote(phrase), model.__name__.lower() + "s"),
            }
        )

    return output


def _build_search_queryset(model, phrase, year, result_group=None):
    queryset = SearchQuerySet().models(model).auto_query(phrase).filter(financial_year=year)
    if result_group:
        queryset = queryset.filter(result_group=result_group)
    return queryset


def _build_result_block(queryset, start=0, limit=None):
    total = queryset.count()
    if limit is None:
        results = queryset[start:]
    else:
        results = queryset[start : start + limit]

    return {
        "count": total,
        "items": [_serialise_result(result) for result in results],
    }


def build_search_landing_results(phrase, year):
    departments = _build_result_block(
        _build_search_queryset(Department, phrase, year),
        limit=LANDING_PAGE_SIZE,
    )
    departments["otherYears"] = _build_other_years(Department, phrase, year)

    datasets = _build_result_block(
        _build_search_queryset(Dataset, phrase, year, result_group="official"),
        limit=LANDING_PAGE_SIZE,
    )
    datasets["otherYears"] = _build_other_years(
        Dataset, phrase, year, result_group="official"
    )

    total = departments["count"] + datasets["count"]

    return {
        "count": total,
        "items": {
            "departments": departments,
            "datasets": datasets,
        },
    }


def build_search_facet_results(phrase, year, view, start=0):
    model_map = {
        "departments": (Department, None),
        "datasets": (Dataset, "official"),
    }
    model, result_group = model_map[view]
    result_block = _build_result_block(
        _build_search_queryset(model, phrase, year, result_group=result_group),
        start=start,
        limit=FACET_PAGE_SIZE,
    )
    return {
        "count": result_block["count"],
        view: result_block,
    }


def search_landing_api(request):
    phrase = _clean_phrase(request.GET.get("q") or request.GET.get("search"))
    year = (request.GET.get("year") or "").strip()

    if not FinancialYear.objects.filter(slug=year).exists():
        return JsonResponse({"error": "Financial year not found"}, status=404)

    if not phrase:
        return JsonResponse(
            {
                "count": 0,
                "items": {
                    "departments": {"count": 0, "items": [], "otherYears": []},
                    "datasets": {"count": 0, "items": [], "otherYears": []},
                },
            }
        )

    try:
        return JsonResponse(build_search_landing_results(phrase, year))
    except Exception:
        logger.exception("Search landing API failed")
        return JsonResponse({"error": "Search unavailable"}, status=500)


def search_facet_api(request):
    phrase = _clean_phrase(request.GET.get("q") or request.GET.get("search"))
    year = (request.GET.get("year") or "").strip()
    view = (request.GET.get("view") or "").strip()

    try:
        start = int(request.GET.get("start", 0))
    except (TypeError, ValueError):
        start = 0
    start = max(start, 0)

    if not FinancialYear.objects.filter(slug=year).exists():
        return JsonResponse({"error": "Financial year not found"}, status=404)

    if view not in VALID_VIEWS:
        return JsonResponse({"error": "Unsupported search view"}, status=400)

    if not phrase:
        return JsonResponse({"count": 0, view: {"count": 0, "items": []}})

    try:
        return JsonResponse(build_search_facet_results(phrase, year, view, start=start))
    except Exception:
        logger.exception("Search facet API failed")
        return JsonResponse({"error": "Search unavailable"}, status=500)
