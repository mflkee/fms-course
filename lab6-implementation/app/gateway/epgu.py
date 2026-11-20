"""Шлюз ЕПГУ: формирование комплекта и регистрация квитанции.

Уведомление через ЕПГУ подписывает и подаёт исполнитель. Система собирает
комплект и сохраняет номер квитанции, который исполнитель ввёл из ответа ЕПГУ.
"""

from __future__ import annotations

from datetime import date

from app.entity.catalogs import MvdOffice
from app.entity.notification import Notification
from app.gateway.base import FailurePolicy, Package, Receipt, utc_now


class EpguGateway:
    name = "epgu"

    def __init__(self, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    def build_package(
        self,
        *,
        addressee: MvdOffice,
        signed_at: date,
        contract_copy_attached: bool,
    ) -> Package:
        enclosures = ["уведомление МВД"]
        if contract_copy_attached:
            enclosures.append("копия договора")
        enclosures.append(f"электронная подпись от {signed_at.isoformat()}")
        return Package(channel=self.name, addressee=addressee.name, enclosures=enclosures)

    def register_receipt(
        self,
        notification: Notification,
        *,
        receipt_number: str,
        simulate_failure: bool | None = None,
    ) -> Receipt:
        self._policy.require_available(self.name, simulate_failure)
        return Receipt(
            number=receipt_number,
            registered_at=utc_now(),
            channel=self.name,
            detail=f"квитанция ЕПГУ, введённая исполнителем для уведомления {notification.id}",
        )
