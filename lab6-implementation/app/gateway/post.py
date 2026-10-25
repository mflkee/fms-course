"""Шлюз Почты России: отправка заказного письма с описью вложения."""

from __future__ import annotations

from datetime import date

from app.entity.catalogs import MvdOffice
from app.entity.documents import Document
from app.entity.enums import DocumentType
from app.entity.notification import Notification
from app.gateway.base import FailurePolicy, Receipt, deterministic_number, utc_now


class PostGateway:
    name = "post"

    def __init__(self, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    def send(
        self,
        notification: Notification,
        *,
        addressee: MvdOffice,
        inventory: str | None,
        sent_at: date | None,
        simulate_failure: bool | None = None,
    ) -> Receipt:
        self._policy.require_available(self.name, simulate_failure)
        return Receipt(
            number=deterministic_number("RU", notification.id),
            issued_at=utc_now(),
            channel=self.name,
            detail=f"опись: {inventory or 'вложение'} → {addressee.name}",
        )

    def return_document(self, track_number: str) -> Document:
        """Сведения о возврате отправления (заглушка: документ-подтверждение)."""
        self._policy.require_available(self.name)
        return Document.create(
            doc_type=DocumentType.RECEIPT,
            filename=f"return-{track_number}.pdf",
            owner_type="notification",
            owner_id=track_number,
            source="post_gateway",
        )
