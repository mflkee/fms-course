"""Шлюз ФНС: сверка расчётов и передача сведений о платеже.

Ответы заглушки предсказуемы: по умолчанию платёж «найден». Режимы
``simulate_status`` (``found`` / ``not_found`` / ``returned``) позволяют
показать альтернативные ветви П05, не поднимая реальную интеграцию.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.entity.payment import TaxPayment
from app.gateway.base import FailurePolicy, FnsCheckResult


class FnsGateway:
    name = "fns"

    def __init__(self, policy: FailurePolicy | None = None) -> None:
        self._policy = policy or FailurePolicy()

    def check_payment(
        self,
        *,
        inn: str,
        period: str,
        amount: Decimal,
        on_date: date,
        simulate_status: str | None = None,
        simulate_failure: bool | None = None,
    ) -> FnsCheckResult:
        self._policy.require_available(self.name, simulate_failure)
        mode = (simulate_status or "found").lower()
        if mode == "found":
            detail = f"поступление {amount} за {period} подтверждено по ИНН {inn}"
            return FnsCheckResult(found=True, detail=detail, checked_at=on_date)
        if mode == "returned":
            detail = f"платёж за {period} возвращён плательщику"
            return FnsCheckResult(found=False, detail=detail, checked_at=on_date)
        detail = f"поступление за {period} по ИНН {inn} не найдено"
        return FnsCheckResult(found=False, detail=detail, checked_at=on_date)

    def transfer_payment(self, payment: TaxPayment) -> None:
        """Передать сведения о подтверждённом платеже в ФНС (заглушка)."""
        self._policy.require_available(self.name)

    def confirm_absence(self, *, inn: str, period: str, on_date: date) -> FnsCheckResult:
        """Подтвердить отсутствие платежа за период (операция 13)."""
        self._policy.require_available(self.name)
        return FnsCheckResult(
            found=False,
            detail=f"оплата за {period} по ИНН {inn} отсутствует",
            checked_at=on_date,
        )
