"""Документ — общее вложение предметной области (лаб. 2, класс ``Документ``)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.entity.enums import DocumentType
from app.entity.ids import new_id


@dataclass(kw_only=True)
class Document:
    """Файл-вложение: скан патента, договор, квитанция, опись, чек.

    ``owner_type``/``owner_id`` задают единственного владельца (агрегация в лаб. 2):
    документ не может висеть «сам по себе».
    """

    doc_type: DocumentType
    filename: str
    owner_type: str
    owner_id: str
    content_hash: str
    source: str = "manual_upload"
    id: str = field(default_factory=new_id)
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        doc_type: DocumentType,
        filename: str,
        owner_type: str,
        owner_id: str,
        content: bytes | None = None,
        content_hash: str | None = None,
        source: str = "manual_upload",
        uploaded_at: datetime | None = None,
    ) -> Document:
        if not filename or not filename.strip():
            raise ValueError("у документа должно быть имя файла")
        digest = content_hash or hashlib.sha256(content or filename.encode("utf-8")).hexdigest()
        document = cls(
            doc_type=doc_type,
            filename=filename.strip(),
            owner_type=owner_type,
            owner_id=owner_id,
            content_hash=digest,
            source=source,
        )
        if uploaded_at is not None:
            document.uploaded_at = uploaded_at
        return document

    def verify_integrity(self, content_hash: str) -> bool:
        return self.content_hash == content_hash

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.doc_type.value,
            "filename": self.filename,
            "hash": self.content_hash,
            "uploaded_at": self.uploaded_at.isoformat(),
            "source": self.source,
            "owner_type": self.owner_type,
            "owner_id": self.owner_id,
        }
