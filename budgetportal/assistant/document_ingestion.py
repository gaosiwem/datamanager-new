"""Keep approved assistant evidence in step with application-managed content."""

import hashlib
import json
import logging
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils.html import strip_tags

from budgetportal.assistant.document_retrieval import chunk_text
from budgetportal.models import (
    ApprovedDocument,
    ApprovedDocumentChunk,
    CustomPage,
    GuidePage,
    PostPage,
)


FAQ_SOURCE = "Vulekamali FAQ"
FAQ_URL = "/faq"
GLOSSARY_SOURCE = "Vulekamali glossary"
GLOSSARY_URL = "/learning-resources/glossary"
GUIDE_SOURCE = "Vulekamali guide"
PORTAL_SOURCE = "Vulekamali portal"
ABOUT_SOURCE_KEY = "portal:about"
ABOUT_URL = "/about"
logger = logging.getLogger(__name__)
_glossary_signature = None


def sync_faq(faq):
    """Replace the approved evidence for one saved FAQ, atomically.

    FAQ is edited in the Vulekamali application by authorised staff, so its
    published content is an approved first-party source.  Chunks are replaced
    rather than appended, ensuring a changed answer cannot retrieve stale text.
    """
    text = _plain_text(faq.content)
    source_key = "faq:{}".format(faq.pk)
    with transaction.atomic():
        document, _ = ApprovedDocument.objects.update_or_create(
            source_key=source_key,
            defaults={
                "title": faq.title,
                "source": FAQ_SOURCE,
                "document_type": "help",
                "url": FAQ_URL,
                "page_section": faq.title,
                "approved": True,
                "text": text,
            },
        )
        document.chunks.all().delete()
        ApprovedDocumentChunk.objects.bulk_create(
            [
                ApprovedDocumentChunk(
                    document=document, chunk_index=index, text=chunk
                )
                for index, chunk in enumerate(chunk_text(text))
            ]
        )


def delete_faq_evidence(faq_id):
    """Remove evidence immediately when the corresponding public FAQ is deleted."""
    ApprovedDocument.objects.filter(source_key="faq:{}".format(faq_id)).delete()


def sync_guide_by_id(guide_id):
    """Refresh evidence only for a GuidePage that remains publicly live."""
    guide = GuidePage.objects.filter(pk=guide_id, live=True).first()
    if guide is not None:
        sync_guide(guide)


def sync_guide(guide):
    body = guide.body
    rendered = body.render_as_block() if hasattr(body, "render_as_block") else str(body)
    _sync_document(
        source_key="guide:{}".format(guide.pk),
        title=guide.title,
        source=GUIDE_SOURCE,
        document_type="help",
        url=getattr(guide, "url", "") or "",
        page_section=guide.title,
        text=_plain_text(rendered),
    )


def delete_guide_evidence(guide_id):
    ApprovedDocument.objects.filter(source_key="guide:{}".format(guide_id)).delete()


def sync_portal_page(page):
    """Index public editorial pages managed in the portal CMS.

    Only page types with an editor-managed ``body`` field are included. This
    keeps the assistant grounded in approved portal content without ingesting
    navigation, user data, or unreviewed external pages.
    """
    if isinstance(page, GuidePage):
        return sync_guide(page)
    if not isinstance(page, (CustomPage, PostPage)):
        return None
    body = page.body
    rendered = body.render_as_block() if hasattr(body, "render_as_block") else str(body)
    return _sync_document(
        source_key="portal:{}:{}".format(page._meta.model_name, page.pk),
        title=page.title,
        source=PORTAL_SOURCE,
        document_type="help",
        url=getattr(page, "url", "") or "",
        page_section=page.title,
        text=_plain_text(rendered),
    )


def sync_about_page():
    """Index the public, template-managed About page as approved portal content."""
    about_directory = Path(settings.BASE_DIR) / "assets" / "js" / "components" / "about"
    try:
        fragments = sorted(about_directory.rglob("*.html"))
        text = "\n".join(
            fragment.read_text(encoding="utf-8") for fragment in fragments
        )
    except OSError as error:
        logger.warning("Assistant about-page sync skipped error_type=%s", error.__class__.__name__)
        return None
    return _sync_document(
        source_key=ABOUT_SOURCE_KEY,
        title="About Vulekamali",
        source=PORTAL_SOURCE,
        document_type="help",
        url=ABOUT_URL,
        page_section="About",
        text=_plain_text(text),
    )


def delete_portal_page_evidence(page):
    """Remove indexed evidence when a portal editorial page is unpublished."""
    if isinstance(page, GuidePage):
        delete_guide_evidence(page.pk)
    elif isinstance(page, (CustomPage, PostPage)):
        ApprovedDocument.objects.filter(
            source_key="portal:{}:{}".format(page._meta.model_name, page.pk)
        ).delete()


def sync_all_application_content():
    """Backfill all approved, application-owned assistant evidence.

    Safe to run repeatedly: each source is upserted and chunks are changed only
    when the underlying content changes.
    """
    from budgetportal.models import FAQ

    counts = {"faq": 0, "guide": 0, "portal_page": 0, "about": 0}
    # django-mssql's server-side iterator can fail with HY010 during batched
    # fetches, so use ordinary queryset evaluation for this small CMS corpus.
    for faq in FAQ.objects.all():
        sync_faq(faq)
        counts["faq"] += 1
    for guide in GuidePage.objects.live():
        sync_guide(guide)
        counts["guide"] += 1
    for page_model in (CustomPage, PostPage):
        for page in page_model.objects.live():
            sync_portal_page(page)
            counts["portal_page"] += 1
    if sync_about_page() is not None:
        counts["about"] = 1
    ensure_static_glossary_synced()
    counts["glossary"] = ApprovedDocument.objects.filter(
        source_key__startswith="glossary:"
    ).count()
    return counts


def ensure_static_glossary_synced():
    """Synchronise the application-owned glossary on its next use after a change."""
    global _glossary_signature
    path = Path(settings.BASE_DIR) / "_data" / "glossary.json"
    try:
        signature = (path.stat().st_mtime_ns, path.stat().st_size)
        if signature == _glossary_signature:
            return
        with path.open(encoding="utf-8") as glossary_file:
            payload = json.load(glossary_file)
        sync_glossary_items(payload.get("items", {}))
        _glossary_signature = signature
    except (OSError, ValueError, TypeError) as error:
        # Retain the last approved glossary evidence rather than making an
        # assistant request fail because a deployment has a malformed file.
        logger.warning("Assistant glossary sync skipped error_type=%s", error.__class__.__name__)


def sync_glossary_items(items):
    """Upsert glossary entries and remove entries deleted from the source file."""
    if not isinstance(items, dict):
        raise ValueError("Glossary items must be an object.")
    source_keys = set()
    with transaction.atomic():
        for term, definition in items.items():
            if not isinstance(term, str) or not isinstance(definition, str):
                continue
            source_key = "glossary:" + hashlib.sha256(
                term.casefold().encode("utf-8")
            ).hexdigest()
            source_keys.add(source_key)
            _sync_document(
                source_key=source_key,
                title=term,
                source=GLOSSARY_SOURCE,
                document_type="glossary",
                url=GLOSSARY_URL,
                page_section=term,
                text=_plain_text(definition),
            )
        stale = ApprovedDocument.objects.filter(source_key__startswith="glossary:")
        if source_keys:
            stale.exclude(source_key__in=source_keys).delete()
        else:
            stale.delete()


def _sync_document(source_key, title, source, document_type, url, page_section, text):
    """Update chunks only when application-managed evidence actually changed."""
    values = {
        "title": title,
        "source": source,
        "document_type": document_type,
        "url": url,
        "page_section": page_section,
        "approved": True,
        "text": text,
    }
    document = ApprovedDocument.objects.filter(source_key=source_key).first()
    if document is not None and all(
        getattr(document, field) == value for field, value in values.items()
    ):
        return document
    if document is None:
        document = ApprovedDocument.objects.create(source_key=source_key, **values)
    else:
        for field, value in values.items():
            setattr(document, field, value)
        document.save(update_fields=list(values))
    document.chunks.all().delete()
    ApprovedDocumentChunk.objects.bulk_create(
        [
            ApprovedDocumentChunk(document=document, chunk_index=index, text=chunk)
            for index, chunk in enumerate(chunk_text(text))
        ]
    )
    return document


def _plain_text(value):
    # Template fragments are application source files. Remove Django template
    # directives before stripping HTML so implementation details cannot become
    # assistant evidence.
    value = re.sub(r"{%.*?%}|{{.*?}}", " ", value or "", flags=re.DOTALL)
    return re.sub(r"\s+", " ", strip_tags(value)).strip()
