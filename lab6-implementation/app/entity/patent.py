"""Патент — центральная сущность темы (DESIGN.md, класс ``Патент``).

Здесь живут правила, которые не зависят от сценария вызова: срок
трудоустройства (2 месяца с даты выдачи) и допустимость профессии (ИНВ-4).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from app.entity.enums import CURRENT_PATENT_STATUSES, ArchiveBasis, PatentStatus
from app.entity.ids import new_id
from app.entity.periods import add_months, valid_until_for


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
    previous_patent_id: str | None = None
    archive_basis: str | None = None
    archived_at: date | None = None
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
        return self.status is PatentStatus.ARCHIVED

    # --- профессия (ИНВ-4) ---------------------------------------------
    def allows_activity(self, activity_code: str) -> bool:
        return activity_code in self.activity_codes

    def allows_any(self, activity_codes: Iterable[str]) -> bool:
        return all(code in self.activity_codes for code in activity_codes)

    # --- переходы состояния --------------------------------------------
    def archive(self, basis: ArchiveBasis, on_date: date) -> None:
        self.status = PatentStatus.ARCHIVED
        self.archive_basis = basis.value
        self.archived_at = on_date

    # --- представление --------------------------------------------------
    def term_is_over(self, on_date: date) -> bool:
        return on_date > self.valid_until

    def days_left(self, on_date: date) -> int:
        return (self.valid_until - on_date).days

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "series": self.series,
            "number": self.number,
            "issue_date": self.issue_date.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "employment_deadline": self.employment_deadline.isoformat(),
            "region_code": self.region_code,
            "activity_codes": list(self.activity_codes),
            "issuing_authority": self.issuing_authority,
            "citizen_id": self.citizen_id,
            "status": self.status.value,
            "previous_patent_id": self.previous_patent_id,
            "archive_basis": self.archive_basis,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


def default_valid_until(issue_date: date) -> date:
    """12 месяцев с даты выдачи минус день."""
    return valid_until_for(issue_date, 12)
