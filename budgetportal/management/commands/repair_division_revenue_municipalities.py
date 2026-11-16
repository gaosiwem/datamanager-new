"""Repair municipality links on legacy Division of Revenue Schedule 3 rows."""

from django.core.management.base import BaseCommand, CommandError

from budgetportal.division_revenue.importer import repair_schedule_3_municipalities
from budgetportal.models import DivisionOfRevenue, DivisionOfRevenueUpload


class Command(BaseCommand):
    help = "Link legacy Schedule 3 allocations to municipalities from their upload workbook."

    def add_arguments(self, parser):
        parser.add_argument("bill_id", type=int)

    def handle(self, *args, **options):
        try:
            bill = DivisionOfRevenue.objects.get(pk=options["bill_id"])
        except DivisionOfRevenue.DoesNotExist:
            raise CommandError("Division of Revenue Bill %s does not exist." % options["bill_id"])
        upload = (
            DivisionOfRevenueUpload.objects.filter(
                division_of_revenue=bill,
                status=DivisionOfRevenueUpload.STATUS_COMPLETE,
            )
            .order_by("-uploaded_at")
            .first()
        )
        if upload is None:
            raise CommandError("No completed upload is linked to this bill.")

        upload.file.open("rb")
        try:
            repaired = repair_schedule_3_municipalities(bill, upload.file)
        finally:
            upload.file.close()
        self.stdout.write(self.style.SUCCESS("Repaired %s municipal allocations." % repaired))
