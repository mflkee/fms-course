"""Контрольная точка и напоминание (лаб. 2, классы ``КонтрольнаяТочка``, ``Напоминание``).

ИНВ-9: точка не существует без патента, напоминание — без точки. Это
обеспечивается репозиториями (создание только с существующим родителем) и
каскадной отменой при архивации/прекращении патента.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.entity.enums import (
    OPEN_POINT_STATUSES,
    NotificationChannel,
    PointKind,
    PointStatus,
    ReminderStatus,
)
from app.entity.ids import new_id


@dataclass(kw_only=True)
class DeadlinePoint:
    patent_id: str
    kind: PointKind
    planned_date: date
    id: str = field(default_factory=new_id)
    status: PointStatus = PointStatus.OPEN
    actual_date: date | None = None
    critical: bool = False
    late: bool = False
    violation_date: date | None = None
    cancel_reason: str | None = None

    def is_open(self) -> bool:
        return self.status in OPEN_POINT_STATUSES

    def is_closed(self) -> bool:
        return not self.is_open()

    def complete(self, on_date: date) -> None:
        self.status = PointStatus.DONE
        self.actual_date = on_date
        self.critical = False

    def mark_violation(self, on_date: date) -> None:
        self.status = PointStatus.OVERDUE
        self.critical = True
        self.violation_date = on_date

    def mark_critical(self) -> None:
        if self.status is PointStatus.OPEN:
            self.status = PointStatus.CRITICAL

    def mark_overdue(self) -> None:
        if self.is_open():
            self.status = PointStatus.OVERDUE
            self.critical = True

    def reopen(self, planned_date: date) -> None:
        self.status = PointStatus.OPEN
        self.actual_date = None
        self.critical = False
        self.violation_date = None
        self.cancel_reason = None
        self.planned_date = planned_date

    def cancel(self, reason: str) -> None:
        self.status = PointStatus.CANCELLED
        self.cancel_reason = reason
        self.critical = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patent_id": self.patent_id,
            "kind": self.kind.value,
            "planned_date": self.planned_date.isoformat(),
            "actual_date": self.actual_date.isoformat() if self.actual_date else None,
            "status": self.status.value,
            "critical": self.critical,
            "late": self.late,
            "violation_date": (
                self.violation_date.isoformat() if self.violation_date else None
            ),
            "cancel_reason": self.cancel_reason,
        }


@dataclass(kw_only=True)
class Reminder:
    point_id: str
    channel: NotificationChannel
    days_before: int
    planned_at: date
    text: str
    id: str = field(default_factory=new_id)
    status: ReminderStatus = ReminderStatus.SCHEDULED
    sent_at: datetime | None = None
    error: str | None = None
    escalation: bool = False

    def mark_sent(self, at: datetime) -> None:
        self.status = ReminderStatus.SENT
        self.sent_at = at

    def mark_delivered(self) -> None:
        if self.status is ReminderStatus.SENT:
            self.status = ReminderStatus.DELIVERED

    def mark_error(self, reason: str) -> None:
        self.status = ReminderStatus.ERROR
        self.error = reason

    def cancel(self) -> None:
        if self.status is ReminderStatus.SCHEDULED:
            self.status = ReminderStatus.CANCELLED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "point_id": self.point_id,
            "channel": self.channel.value,
            "days_before": self.days_before,
            "planned_at": self.planned_at.isoformat(),
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error": self.error,
            "escalation": self.escalation,
            "text": self.text,
        }
