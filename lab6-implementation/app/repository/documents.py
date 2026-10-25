"""Репозитории документов и отчётов."""

from __future__ import annotations

from app.entity.documents import Document
from app.entity.report import Report
from app.repository.base import InMemoryRepository


class DocumentRepository(InMemoryRepository[Document]):
    entity_name = "документ"

    def by_owner(self, owner_type: str, owner_id: str) -> list[Document]:
        return self.filter(
            lambda document: document.owner_type == owner_type
            and document.owner_id == owner_id
        )


class ReportRepository(InMemoryRepository[Report]):
    entity_name = "отчёт"
