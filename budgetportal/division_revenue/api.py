"""Read-only data for the public Division of Revenue visualisations."""

from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from budgetportal.models import DivisionOfRevenue


SPHERE_LABELS = {
    "national": "National",
    "provincial": "Provincial",
    "local": "Local",
}
SPHERE_ORDER = ("national", "provincial", "local")
MUNICIPALITY_CATEGORY_LABELS = {
    "A": "Metropolitan municipality",
    "B": "Local municipality",
    "C": "District municipality",
}


def _latest_bill():
    """Use the latest imported version for the most recent available year."""
    return (
        DivisionOfRevenue.objects.select_related("financial_year")
        .order_by("-financial_year__slug", "-version")
        .first()
    )


@require_GET
def graph_data(request):
    """Return the three datasets already displayed on the learning-resource page."""
    bill = _latest_bill()
    if bill is None:
        return JsonResponse(
            {"error": "No Division of Revenue Bill has been imported."}, status=404
        )

    allocations = bill.allocations.all()
    sphere_totals = {
        item["schedule_1_recipient"]: int(item["amount"] or 0)
        for item in (
            allocations.filter(schedule_number=1)
            .values("schedule_1_recipient")
            .annotate(amount=Sum("amount_rands"))
        )
    }
    by_sphere = [
        {
            "label": SPHERE_LABELS[recipient],
            "amount_rands": sphere_totals[recipient],
        }
        for recipient in SPHERE_ORDER
        if recipient in sphere_totals
    ]

    by_province = [
        {
            "label": item["government__name"],
            "amount_rands": int(item["amount"] or 0),
        }
        for item in (
            allocations.filter(schedule_number=2, government__isnull=False)
            .values("government__name")
            .annotate(amount=Sum("amount_rands"))
            .order_by("government__name")
        )
    ]

    by_municipality = [
        {
            "code": item["municipality__code"],
            "name": item["municipality__name"],
            "province": item["municipality__province__name"],
            "category": item["municipality__category"],
            "category_label": MUNICIPALITY_CATEGORY_LABELS[item["municipality__category"]],
            "amount_rands": int(item["amount"] or 0),
        }
        for item in (
            allocations.filter(schedule_number=3, municipality__isnull=False)
            .values(
                "municipality__code",
                "municipality__name",
                "municipality__province__name",
                "municipality__category",
            )
            .annotate(amount=Sum("amount_rands"))
            .order_by("municipality__province__name", "municipality__name")
        )
    ]

    return JsonResponse(
        {
            "financial_year": bill.financial_year.slug,
            "version": bill.version,
            "allocation_by_sphere": by_sphere,
            "allocation_to_provinces": by_province,
            "allocation_to_municipalities": by_municipality,
        }
    )
