"""Патент — центральная сущность темы (лаб. 2, класс ``Патент``).

Здесь живут правила, которые не зависят от сценария вызова:
срок трудоустройства (2 месяца), допустимость профессии (ИНВ-4),
непрерывность оплаты (ИНВ-5), очередной непокрытый период.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.entity.enums import CURRENT_PATENT_STATUSES, ArchiveBasis, PatentStatus
from app.entity.ids import new_id
from app.entity.periods import add_months, month_end, next_period, period_of, period_start


@dataclass(kw_only=True)
class Patent:
    series: str
    number: str
    issue_date: date
    valid_until: date
    region_code: str
    activity_codes: list[str]
    issuing_authority: str
    citizen_id: str
    id: str = field(default_factory=new_id)
    status: PatentStatus = PatentStatus.ACTIVE
    paid_until: date | None = None
    previous_patent_id: str | None = None
    archive_basis: str | None = None
    archived_at: date | None = None
    termination_date: date | None = None
    created_at: date | None = None

    # --- сроки ---------------------------------------------------------
    @property
    def employment_deadline(self) -> date:
        """``датаТрудоустройстваНеПозднее`` = дата выдачи + 2 календарных месяца."""
        return add_months(self.issue_date, 2)

    def days_left_for_employment(self, on_date: date) -> int:
        return (self.employment_deadline - on_date).days

    def is_current(self) -> bool:
        return self.status in CURRENT_PATENT_STATUSES

    def is_archived(self) -> bool:
        return self.status in {PatentStatus.ARCHIVED, PatentStatus.TERMINATED_NONPAYMENT}

    # --- профессия (ИНВ-4) ---------------------------------------------
    def allows_activity(self, activity_code: str) -> bool:
        return activity_code in self.activity_codes

    def allows_any(self, activity_codes: Iterable[str]) -> bool:
        return all(code in self.activity_codes for code in activity_codes)

    # --- оплата (ИНВ-5, ИНВ-7) -----------------------------------------
    def next_uncovered_period(self) -> str:
        """Первый месяц, за который авансовый платёж ещё не подтверждён."""
        if self.paid_until is None:
            return period_of(self.issue_date)
        return next_period(period_of(self.paid_until))

    def covers_period(self, period: str) -> bool:
        if self.paid_until is None:
            return False
        return period_of(self.paid_until) >= period

    def has_paid_period(self) -> bool:
        return self.paid_until is not None

    def covers_patent_term(self) -> bool:
        return self.paid_until is not None and self.paid_until >= self.valid_until

    def mark_paid_until(self, paid_until: date) -> None:
        if self.paid_until is None or paid_until > self.paid_until:
            self.paid_until = paid_until
        if self.is_current():
            self.status = PatentStatus.PAID_UNTIL

    def mark_expired(self) -> None:
        self.status = PatentStatus.EXPIRED

    # --- переходы состояния --------------------------------------------
    def archive(self, basis: ArchiveBasis, on_date: date) -> None:
        self.status = PatentStatus.ARCHIVED
        self.archive_basis = basis.value
        self.archived_at = on_date

    def terminate_nonpayment(self, on_date: date) -> None:
        self.status = PatentStatus.TERMINATED_NONPAYMENT
        self.termination_date = on_date

    # --- представление --------------------------------------------------
    def term_is_over(self, on_date: date) -> bool:
        return on_date > self.valid_until

    def days_left(self, on_date: date) -> int:
        return (self.valid_until - on_date).days

    def period_is_within_term(self, period: str) -> bool:
        return period_start(period) <= self.valid_until and period >= period_of(self.issue_date)

    def first_payment_due_date(self) -> date:
        """Срок платежа за очередной период: конец этого календарного месяца.

        Упрощение модели: авансовый платёж за месяц считается внесённым,
        если он подтверждён до конца этого месяца.
        """
        return month_end(period_start(self.next_uncovered_period()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "series": self.series,
            "number": self.number,
            "issue_date": self.issue_date.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "employment_deadline": self.employment_deadline.isoformat(),
            "paid_until": self.paid_until.isoformat() if self.paid_until else None,
            "region_code": self.region_code,
            "activity_codes": list(self.activity_codes),
            "issuing_authority": self.issuing_authority,
            "citizen_id": self.citizen_id,
            "status": self.status.value,
            "previous_patent_id": self.previous_patent_id,
            "archive_basis": self.archive_basis,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "termination_date": (
                self.termination_date.isoformat() if self.termination_date else None
            ),
        }


def default_valid_until(issue_date: date) -> date:
    """12 месяцев с даты выдачи минус день (ИНВ-6)."""
    return add_months(issue_date, 12) - timedelta(days=1)
