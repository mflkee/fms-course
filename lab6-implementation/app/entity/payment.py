"""Авансовый платёж НДФЛ (лаб. 2, класс ``ПлатёжНДФЛ``).

Платёж привязан к патенту и календарному периоду; сумма сверяется со
стоимостью патента в регионе (ИНВ-7), периоды не пропускаются (ИНВ-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.entity.enums import PaymentStatus
from app.entity.ids import new_id
from app.entity.money import money, money_str, shortfall


@dataclass(kw_only=True)
class TaxPayment:
    patent_id: str
    period: str
    amount: Decimal
    payment_date: date
    document_number: str
    id: str = field(default_factory=new_id)
    status: PaymentStatus = PaymentStatus.NOT_FOUND
    input_source: str | None = None
    manual: bool = False
    expected_amount: Decimal | None = None
    shortfall_amount: Decimal | None = None
    document_id: str | None = None
    fns_detail: str | None = None
    created_at: datetime | None = None
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.amount = money(self.amount)
        if self.expected_amount is not None:
            self.expected_amount = money(self.expected_amount)

    # --- проверки -------------------------------------------------------
    def matches_amount(self, expected: Decimal) -> bool:
        return self.amount == money(expected)

    def compute_shortfall(self, expected: Decimal) -> Decimal:
        return shortfall(expected, self.amount)

    # --- переходы состояния ---------------------------------------------
    def confirm(
        self,
        *,
        source: str,
        document_id: str | None,
        confirmed_at: datetime,
        manual: bool = True,
    ) -> None:
        self.status = PaymentStatus.CONFIRMED
        self.input_source = source
        self.manual = manual
        self.document_id = document_id
        self.confirmed_at = confirmed_at
        self.shortfall_amount = None

    def mark_not_found(self, detail: str) -> None:
        self.status = PaymentStatus.NOT_FOUND
        self.fns_detail = detail

    def mark_insufficient(self, expected: Decimal) -> None:
        self.status = PaymentStatus.INSUFFICIENT
        self.expected_amount = money(expected)
        self.shortfall_amount = self.compute_shortfall(expected)

    def mark_returned(self, detail: str) -> None:
        self.status = PaymentStatus.RETURNED
        self.fns_detail = detail

    def covers(self, period: str) -> bool:
        return self.status is PaymentStatus.CONFIRMED and self.period == period

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patent_id": self.patent_id,
            "period": self.period,
            "amount": money_str(self.amount),
            "expected_amount": money_str(self.expected_amount),
            "shortfall": money_str(self.shortfall_amount),
            "payment_date": self.payment_date.isoformat(),
            "document_number": self.document_number,
            "status": self.status.value,
            "input_source": self.input_source,
            "manual": self.manual,
            "document_id": self.document_id,
            "fns_detail": self.fns_detail,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }
