"""Шлюз ЕПГУ: отправка уведомления МВД с электронной подписью."""

from __future__ import annotations

from datetime import date

from app.entity.notification import Notification
from app.gateway.base import FailurePolicy, Receipt, deterministic_number, utc_now


class EpguGateway:
    name = "epgu"

    def __init__(self, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    def send(
        self,
        notification: Notification,
        *,
        signature: str | None,
        signed_at: date | None,
        simulate_failure: bool | None = None,
    ) -> Receipt:
        self._policy.require_available(self.name, simulate_failure)
        return Receipt(
            number=deterministic_number("EPGU", notification.id),
            issued_at=utc_now(),
            channel=self.name,
            detail=f"подпись ЭП от {signed_at.isoformat()}" if signed_at else "подпись ЭП",
        )

    def check_status(self, receipt_number: str) -> str:
        self._policy.require_available(self.name)
        return "delivered"
