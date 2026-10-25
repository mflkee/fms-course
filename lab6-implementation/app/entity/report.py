"""Отчёт-реестр: срез данных с собственным жизненным циклом (лаб. 5, ``ОтчётРеестр``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.entity.ids import new_id


@dataclass(kw_only=True)
class ReportRow:
    citizen_id: str
    citizen_name: str
    patent_id: str
    patent_series: str
    patent_number: str
    region: str
    patent_status: str
    employer: str | None
    contract_date: date | None
    notification_date: date | None
    payment_status: str
    deadline_status: str
    critical: bool

    def to_dict(self) -> dict:
        return {
            "citizen_id": self.citizen_id,
            "citizen_name": self.citizen_name,
            "patent_id": self.patent_id,
            "patent": f"{self.patent_series} {self.patent_number}",
            "region": self.region,
            "patent_status": self.patent_status,
            "employer": self.employer,
            "contract_date": self.contract_date.isoformat() if self.contract_date else None,
            "notification_date": (
                self.notification_date.isoformat() if self.notification_date else None
            ),
            "payment_status": self.payment_status,
            "deadline_status": self.deadline_status,
            "critical": self.critical,
        }


@dataclass(kw_only=True)
class ExportRecord:
    format: str
    filename: str
    sha256: str
    size: int
    anonymized: bool
    exported_by: str
    exported_at: datetime

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "filename": self.filename,
            "sha256": self.sha256,
            "size": self.size,
            "anonymized": self.anonymized,
            "exported_by": self.exported_by,
            "exported_at": self.exported_at.isoformat(),
        }


@dataclass(kw_only=True)
class Report:
    parameters: dict
    snapshot_at: datetime
    created_by: str
    rows: list[ReportRow] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    exports: list[ExportRecord] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for row in self.rows if row.critical)

    def critical_rows(self) -> list[ReportRow]:
        return [row for row in self.rows if row.critical]

    def anonymize(self) -> None:
        """Обезличить срез: вместо ФИО — идентификатор гражданина."""
        for row in self.rows:
            row.citizen_name = f"ИГ-{row.citizen_id[:8]}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parameters": self.parameters,
            "snapshot_at": self.snapshot_at.isoformat(),
            "created_by": self.created_by,
            "rows": [row.to_dict() for row in self.rows],
            "critical_count": self.critical_count,
            "row_count": len(self.rows),
            "exports": [record.to_dict() for record in self.exports],
        }
