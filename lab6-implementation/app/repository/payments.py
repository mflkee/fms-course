"""Репозиторий платежей (лаб. 5, ``РеестрПлатежей``)."""

from __future__ import annotations

from app.entity.enums import PaymentStatus
from app.entity.payment import TaxPayment
from app.repository.base import InMemoryRepository


class PaymentRepository(InMemoryRepository[TaxPayment]):
    entity_name = "платёж НДФЛ"

    def by_patent(self, patent_id: str) -> list[TaxPayment]:
        return self.filter(lambda payment: payment.patent_id == patent_id)

    def by_period(self, patent_id: str, period: str) -> TaxPayment | None:
        for payment in self.by_patent(patent_id):
            if payment.period == period:
                return payment
        return None

    def confirmed_by_period(self, patent_id: str, period: str) -> TaxPayment | None:
        payment = self.by_period(patent_id, period)
        if payment and payment.status is PaymentStatus.CONFIRMED:
            return payment
        return None

    def last_confirmed(self, patent_id: str) -> TaxPayment | None:
        confirmed = [
            payment
            for payment in self.by_patent(patent_id)
            if payment.status is PaymentStatus.CONFIRMED
        ]
        if not confirmed:
            return None
        return max(confirmed, key=lambda payment: payment.period)
