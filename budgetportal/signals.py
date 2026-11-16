from budgetportal import models, tasks
from django.db.models.signals import post_delete, post_save
from django.db import transaction
from wagtail.core.signals import page_published, page_unpublished
from django.dispatch import receiver
from django_q.tasks import async_task
from .models import InfrastructureProjectImportFile
from .tasks import import_infrastructure_data
from budgetportal.assistant.document_ingestion import (
    delete_faq_evidence,
    delete_portal_page_evidence,
    sync_faq,
    sync_portal_page,
)
from budgetportal.models import CustomPage, GuidePage, PostPage
from budgetportal.models.government import FAQ
from budgetportal.assistant.cache import AssistantAnswerCache, AssistantCacheUnavailable


def _invalidate_assistant_content_cache():
    """Make public assistant answers unreachable after content commits."""
    cache_service = AssistantAnswerCache()
    if not cache_service.enabled:
        return
    try:
        cache_service.increment_revision("assistant:content-revision")
    except AssistantCacheUnavailable:
        # Requests will fail closed while shared caching is required; a content
        # save itself must not be rolled back just because Redis is unavailable.
        return


@receiver(post_save, sender=InfrastructureProjectImportFile)
def trigger_import_on_upload(sender, instance, created, **kwargs):
    if created and not instance.processed:
        async_task(import_infrastructure_data, instance.id)


@receiver(post_save, sender=FAQ)
def sync_faq_assistant_evidence(sender, instance, raw=False, **kwargs):
    """Refresh searchable FAQ evidence only after the edit commits."""
    if not raw:
        def sync():
            sync_faq(instance)
            _invalidate_assistant_content_cache()
        transaction.on_commit(sync)


@receiver(post_delete, sender=FAQ)
def remove_deleted_faq_assistant_evidence(sender, instance, **kwargs):
    def remove():
        delete_faq_evidence(instance.pk)
        _invalidate_assistant_content_cache()
    transaction.on_commit(remove)


@receiver(page_published)
def sync_published_portal_assistant_evidence(sender, instance, **kwargs):
    page = instance.specific
    if isinstance(page, (CustomPage, GuidePage, PostPage)):
        def sync():
            sync_portal_page(page)
            _invalidate_assistant_content_cache()
        transaction.on_commit(sync)


@receiver(page_unpublished)
def remove_unpublished_portal_assistant_evidence(sender, instance, **kwargs):
    page = instance.specific
    if isinstance(page, (CustomPage, GuidePage, PostPage)):
        def remove():
            delete_portal_page_evidence(page)
            _invalidate_assistant_content_cache()
        transaction.on_commit(remove)


@receiver(post_delete, sender=GuidePage)
@receiver(post_delete, sender=CustomPage)
@receiver(post_delete, sender=PostPage)
def remove_deleted_portal_assistant_evidence(sender, instance, **kwargs):
    def remove():
        delete_portal_page_evidence(instance)
        _invalidate_assistant_content_cache()
    transaction.on_commit(remove)


@receiver(post_save, sender=models.ApprovedDocument)
@receiver(post_delete, sender=models.ApprovedDocument)
def invalidate_manual_assistant_document_cache(sender, instance, **kwargs):
    """Cover administrator-managed assistant evidence as well as CMS sources."""
    transaction.on_commit(_invalidate_assistant_content_cache)

# @receiver([post_save], sender=models.IRMSnapshot)
# def handle_irm_snapshot_post_save(
#     sender, instance, created, raw, using, update_fields, **kwargs
# ):
#     async_task(
#         tasks.import_irm_snapshot,
#         snapshot_id=instance.id,
#         task_name="Import IRM Snappshot file of infrastructue projects",
#     )


# @receiver([post_delete], sender=models.IRMSnapshot)
# def handle_irm_snapshot_post_delete(sender, instance, using, **kwargs):
#     async_task(
#         tasks.index_irm_projects,
#         snapshot_id=instance.id,
#         task_name="Update infrastructure projects search index following snapshot deletion",
#     )
