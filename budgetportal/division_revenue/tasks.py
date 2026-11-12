"""Django-Q tasks for Division of Revenue workbook imports."""

import logging

from budgetportal.models import DivisionOfRevenueUpload

from .importer import import_official_schedules


logger = logging.getLogger(__name__)


def import_division_revenue_upload(upload_id):
    """Read a stored workbook and import its Schedules 1--3 in a worker."""
    upload = DivisionOfRevenueUpload.objects.get(pk=upload_id)
    if upload.status == DivisionOfRevenueUpload.STATUS_COMPLETE:
        return {"status": "already complete", "upload_id": upload.pk}

    upload.status = DivisionOfRevenueUpload.STATUS_PROCESSING
    upload.error_message = ""
    upload.save(update_fields=("status", "error_message"))
    try:
        upload.file.open("rb")
        try:
            bill = import_official_schedules(upload.file)
        finally:
            upload.file.close()
        upload.division_of_revenue = bill
        upload.status = DivisionOfRevenueUpload.STATUS_COMPLETE
        upload.save(update_fields=("division_of_revenue", "status"))
        return {"status": "complete", "upload_id": upload.pk, "bill_id": bill.pk}
    except Exception as error:
        logger.exception("Division of Revenue upload %s failed", upload.pk)
        upload.status = DivisionOfRevenueUpload.STATUS_FAILED
        upload.error_message = str(error)
        upload.save(update_fields=("status", "error_message"))
        raise
