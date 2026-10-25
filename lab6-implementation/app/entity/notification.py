"""Уведомление МВД и его доказательства (лаб. 2, класс ``УведомлениеМВД``).

ИНВ-8: уведомление и доказательства не удаляются. Поэтому у класса нет
операции удаления: меняется только статус и добавляются сведения о попытках.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.entity.enums import NotificationChannel, NotificationStatus
from app.entity.ids import new_id


@dataclass(kw_only=True)
class Notification:
    contract_id: str
    channel: NotificationChannel
    id: str = field(default_factory=new_id)
    status: NotificationStatus = NotificationStatus.PREPARED
    send_date: date | None = None
    receipt_number: str | None = None
    track_number: str | None = None
    inventory: str | None = None
    contract_copy_document_id: str | None = None
    evidence_document_ids: list[str] = field(default_factory=list)
    mvd_office_code: str | None = None
    attempts: int = 0
    return_reason: str | None = None
    late: bool = False
    created_at: datetime | None = None

    def mark_sent(
        self,
        *,
        send_date: date,
        receipt_number: str | None = None,
        track_number: str | None = None,
        inventory: str | None = None,
        mvd_office_code: str | None = None,
        late: bool = False,
    ) -> None:
        self.status = NotificationStatus.OVERDUE if late else NotificationStatus.SENT
        self.send_date = send_date
        self.receipt_number = receipt_number
        self.track_number = track_number
        self.inventory = inventory
        self.mvd_office_code = mvd_office_code
        self.late = late
        self.attempts += 1

    def mark_error(self, reason: str) -> None:
        self.status = NotificationStatus.ERROR
        self.return_reason = reason
        self.attempts += 1

    def mark_delivered(self) -> None:
        self.status = NotificationStatus.DELIVERED

    def may_be_returned(self) -> bool:
        return self.status in {
            NotificationStatus.SENT,
            NotificationStatus.OVERDUE,
            NotificationStatus.ERROR,
        }

    def evidence(self) -> dict:
        return {
            "receipt_number": self.receipt_number,
            "track_number": self.track_number,
            "inventory": self.inventory,
            "documents": list(self.evidence_document_ids),
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "send_date": self.send_date.isoformat() if self.send_date else None,
            "receipt_number": self.receipt_number,
            "track_number": self.track_number,
            "inventory": self.inventory,
            "mvd_office_code": self.mvd_office_code,
            "attempts": self.attempts,
            "return_reason": self.return_reason,
            "late": self.late,
            "contract_copy_document_id": self.contract_copy_document_id,
            "evidence_document_ids": list(self.evidence_document_ids),
        }
