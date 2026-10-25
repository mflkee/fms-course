"""Договор (абстрактный) и две его правовые формы (лаб. 2, лаб. 5).

Общие реквизиты и переходы состояния — в базовом классе; различие трудового
договора и ГПХ — в подклассах. ``kind`` — дискриминатор для сериализации.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from app.entity.enums import (
    ACTIVE_CONTRACT_STATUSES,
    ContractKind,
    ContractStatus,
    WorkMode,
)
from app.entity.ids import new_id


@dataclass(kw_only=True)
class Contract(ABC):
    number: str
    patent_id: str
    employer_id: str
    activity_code: str
    conclusion_date: date
    document_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    status: ContractStatus = ContractStatus.CONCLUDED
    end_date: date | None = None
    cancel_reason: str | None = None
    cancelled_at: date | None = None
    termination_date: date | None = None
    termination_reason: str | None = None
    termination_corrected: bool = False
    created_at: date | None = None

    @property
    @abstractmethod
    def kind(self) -> ContractKind:
        """Вид договора: ``employment`` или ``civil``."""

    def is_active(self) -> bool:
        return self.status in ACTIVE_CONTRACT_STATUSES

    def is_draft(self) -> bool:
        return self.status is ContractStatus.DRAFT

    def mark_notification_sent(self) -> None:
        if self.status is ContractStatus.CONCLUDED:
            self.status = ContractStatus.NOTIFICATION_SENT

    def cancel(self, reason: str, on_date: date) -> None:
        self.status = ContractStatus.CANCELLED
        self.cancel_reason = reason
        self.cancelled_at = on_date

    def terminate(self, on_date: date, reason: str, *, corrected: bool = False) -> None:
        self.status = ContractStatus.TERMINATED
        self.termination_date = on_date
        self.termination_reason = reason
        self.termination_corrected = corrected

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "kind": self.kind.value,
            "status": self.status.value,
            "patent_id": self.patent_id,
            "employer_id": self.employer_id,
            "activity_code": self.activity_code,
            "conclusion_date": self.conclusion_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "document_ids": list(self.document_ids),
            "cancel_reason": self.cancel_reason,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "termination_date": (
                self.termination_date.isoformat() if self.termination_date else None
            ),
            "termination_reason": self.termination_reason,
            "termination_corrected": self.termination_corrected,
        }


@dataclass(kw_only=True)
class EmploymentContract(Contract):
    position: str
    work_mode: WorkMode = WorkMode.FULL_DAY

    @property
    def kind(self) -> ContractKind:
        return ContractKind.EMPLOYMENT

    def working_conditions(self) -> dict:
        return {"position": self.position, "work_mode": self.work_mode.value}

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update(self.working_conditions())
        return payload


@dataclass(kw_only=True)
class CivilContract(Contract):
    subject: str
    work_deadline: date

    @property
    def kind(self) -> ContractKind:
        return ContractKind.CIVIL

    def scope(self) -> dict:
        return {"subject": self.subject, "work_deadline": self.work_deadline.isoformat()}

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update(self.scope())
        return payload
