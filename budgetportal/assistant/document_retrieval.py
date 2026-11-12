"""Approved-document retrieval for explanatory assistant questions.

The active deployment uses SQL Server, so this intentionally uses a small,
deterministic lexical retriever rather than pgvector.  It can be replaced by a
PostgreSQL/pgvector implementation later without changing the router contract.
"""

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from django.db.models import Q

from budgetportal.models import ApprovedDocumentChunk


STOP_WORDS = frozenset(
    (
        "what",
        "is",
        "the",
        "a",
        "an",
        "of",
        "and",
        "for",
        "why",
        "did",
        "does",
        "in",
        "to",
    )
)


@dataclass(frozen=True)
class RetrievedEvidence:
    title: str
    source: str
    financial_year: str
    document_type: str
    url: str
    page_section: str
    chunk_text: str
    score: int


def chunk_text(text, chunk_size=900, overlap=150):
    words = text.split()
    if chunk_size <= overlap or overlap < 0:
        raise ValueError("chunk_size must be greater than overlap.")
    chunks, start = [], 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


class ApprovedDocumentRetriever:
    def __init__(self, chunk_model=ApprovedDocumentChunk):
        self.chunk_model = chunk_model
        self.sync_static_glossary = chunk_model is ApprovedDocumentChunk

    def retrieve(self, question, limit=4):
        if self.sync_static_glossary:
            # The glossary is currently an application-managed JSON source,
            # so the next retrieval after a deployed file update refreshes it.
            from budgetportal.assistant.document_ingestion import (
                ensure_static_glossary_synced,
            )

            ensure_static_glossary_synced()
        tokens = self._tokens(question)
        if not tokens:
            return ()
        condition = Q()
        for token in tokens:
            condition |= Q(text__icontains=token)
        chunks = self.chunk_model.objects.filter(
            condition, document__approved=True
        ).select_related("document")
        return tuple(self.rank_chunks(question, chunks)[:limit])

    @classmethod
    def rank_chunks(cls, question, chunks: Iterable):
        tokens = set(cls._tokens(question))
        evidence = []
        for chunk in chunks:
            score = sum(token in chunk.text.casefold() for token in tokens)
            # Titles are editor-curated summaries. Weighting their overlap
            # makes a direct FAQ or guide question rank above generic portal
            # pages that happen to mention the same broad terms.
            score += 2 * sum(
                token in chunk.document.title.casefold() for token in tokens
            )
            if score:
                document = chunk.document
                evidence.append(
                    RetrievedEvidence(
                        title=document.title,
                        source=document.source,
                        financial_year=document.financial_year.slug
                        if document.financial_year
                        else "",
                        document_type=document.document_type,
                        url=document.url or "",
                        page_section=document.page_section or "",
                        chunk_text=chunk.text,
                        score=score,
                    )
                )
        return sorted(
            evidence, key=lambda item: (-item.score, item.title, item.page_section)
        )

    @staticmethod
    def _tokens(text):
        return tuple(
            token
            for token in re.findall(r"[a-z0-9]+", text.casefold())
            if len(token) > 2 and token not in STOP_WORDS
        )
