"""Шлюз Почты России: формирование комплекта и регистрация трек-номера.

Заказное письмо с описью исполнитель отправляет сам. Система собирает комплект
и сохраняет трек-номер и опись, которые исполнитель внёс после отправки.
"""

from __future__ import annotations

from datetime import date

from app.entity.catalogs import MvdOffice
from app.entity.notification import Notification
from app.gateway.base import FailurePolicy, Package, Receipt, utc_now


class PostGateway:
    name = "post"

    def __init__(self, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    def build_package(
        self,
        *,
        addressee: MvdOffice,
        inventory: str,
        sent_at: date,
        contract_copy_attached: bool,
    ) -> Package:
        enclosures = ["уведомление МВД"]
        if contract_copy_attached:
            enclosures.append("копия договора")
        enclosures.append(f"опись вложения: {inventory} (отправка {sent_at.isoformat()})")
        return Package(channel=self.name, addressee=addressee.name, enclosures=enclosures)

    def register_track(
        self,
        notification: Notification,
        *,
        track_number: str,
        simulate_failure: bool | None = None,
    ) -> Receipt:
        self._policy.require_available(self.name, simulate_failure)
        return Receipt(
            number=track_number,
            registered_at=utc_now(),
            channel=self.name,
            detail=f"трек-номер почтового отправления для уведомления {notification.id}",
        )
