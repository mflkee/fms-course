"""Модуль отчётности (лаб. 5, ``МодульОтчётности``), операции 15 и 16.

Срез данных фиксируется на момент формирования и хранится как объект
``Report``. Право на отчёт и право на персональные данные — разные права:
без второго выгрузка выполняется обезличенной, а попытка выгрузить полный
отчёт фиксируется как отказ в журнале аудита.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date

from app.control.access_service import AccessService
from app.control.pdf import render_pdf
from app.entity.clock import Clock
from app.entity.contract import Contract
from app.entity.enums import ContractStatus, PatentStatus, PaymentStatus, ReportFormat
from app.entity.patent import Patent
from app.entity.periods import period_end
from app.entity.report import ExportRecord, Report, ReportRow
from app.entity.user import User
from app.errors import EmptySelectionError, ForbiddenError
from app.repository.audit import AuditRepository
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository
from app.repository.documents import ReportRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository
from app.repository.payments import PaymentRepository
from app.repository.people import CitizenRepository, EmployerRepository

CSV_DELIMITER = ";"
CSV_HEADER = [
    "ФИО",
    "Патент",
    "Регион",
    "Статус патента",
    "Работодатель",
    "Дата договора",
    "Дата уведомления",
    "Оплата",
    "Статус срока",
    "Критическая запись",
]


@dataclass(kw_only=True)
class ExportResult:
    content: bytes
    filename: str
    media_type: str
    sha256: str
    size: int
    anonymized: bool
    report: Report
    record: ExportRecord

    def headers(self) -> dict[str, str]:
        return {
            "Content-Disposition": f'attachment; filename="{self.filename}"',
            "X-Export-Hash": self.sha256,
            "X-Export-Anonymized": "true" if self.anonymized else "false",
            "X-Report-Id": self.report.id,
        }


class ReportService:
    def __init__(
        self,
        reports: ReportRepository,
        patents: PatentRepository,
        contracts: ContractRepository,
        notifications: NotificationRepository,
        payments: PaymentRepository,
        points: DeadlinePointRepository,
        citizens: CitizenRepository,
        employers: EmployerRepository,
        access: AccessService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._reports = reports
        self._patents = patents
        self._contracts = contracts
        self._notifications = notifications
        self._payments = payments
        self._points = points
        self._citizens = citizens
        self._employers = employers
        self._access = access
        self._clock = clock
        self._audit = audit

    # --- операция 15: сформировать реестр ---------------------------------
    def build(
        self,
        *,
        actor: User | None,
        period_from: date | None = None,
        period_to: date | None = None,
        region: str | None = None,
        status: PatentStatus | None = None,
        has_overdue: bool | None = None,
    ) -> Report:
        self._access.require_admin(actor)
        assert actor is not None

        patents = self._select(period_from, period_to, region, status)
        rows: list[ReportRow] = [
            self._row(patent, actor) for patent in patents
        ]
        if has_overdue:
            rows = [row for row in rows if row.critical]
        if not rows:
            raise EmptySelectionError(
                "по заданным параметрам записей не найдено: отчёт не формируется",
                code="EMPTY_SELECTION",
            )

        report = Report(
            parameters={
                "period_from": period_from.isoformat() if period_from else None,
                "period_to": period_to.isoformat() if period_to else None,
                "region": region,
                "status": status.value if status else None,
                "has_overdue": has_overdue,
            },
            snapshot_at=self._clock.now(),
            created_by=actor.login,
            rows=rows,
        )
        self._reports.add(report)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="build_report",
            entity_type="report",
            entity_id=report.id,
            details={"rows": len(rows), "parameters": report.parameters},
        )
        return report

    def _select(
        self,
        period_from: date | None,
        period_to: date | None,
        region: str | None,
        status: PatentStatus | None,
    ) -> list[Patent]:
        patents = self._patents.all()
        if period_from is not None:
            patents = [item for item in patents if item.issue_date >= period_from]
        if period_to is not None:
            patents = [item for item in patents if item.issue_date <= period_to]
        if region is not None:
            patents = [item for item in patents if item.region_code == region]
        if status is not None:
            patents = [item for item in patents if item.status is status]
        return sorted(patents, key=lambda item: item.issue_date)

    def _row(self, patent: Patent, actor: User) -> ReportRow:
        citizen = self._citizens.find(patent.citizen_id)
        contract = self._latest_contract(patent)
        employer = (
            self._employers.find(contract.employer_id) if contract is not None else None
        )
        notification = (
            self._notifications.by_contract(contract.id) if contract else None
        )
        points = self._points.by_patent(patent.id)
        overdue_points = [
            point for point in points if point.is_open() and point.planned_date < self._clock.today()
        ]
        next_point = min(
            (point.planned_date for point in points if point.is_open()),
            default=None,
        )
        payment_status = self._payment_status(patent)
        critical = bool(
            overdue_points
            or patent.status is PatentStatus.TERMINATED_NONPAYMENT
            or (notification is not None and notification.late)
        )
        name = "скрыто"
        if citizen is not None:
            name = (
                citizen.full_name
                if self._access.may_see_personal_data(actor)
                else f"ИГ-{citizen.id[:8]}"
            )
        return ReportRow(
            citizen_id=patent.citizen_id,
            citizen_name=name,
            patent_id=patent.id,
            patent_series=patent.series,
            patent_number=patent.number,
            region=patent.region_code,
            patent_status=patent.status.value,
            employer=employer.name if employer else None,
            contract_date=contract.conclusion_date if contract else None,
            notification_date=notification.send_date if notification else None,
            payment_status=payment_status,
            deadline_status=(
                "просрочено" if overdue_points else (
                    f"до {next_point.isoformat()}" if next_point else "нет открытых точек"
                )
            ),
            critical=critical,
        )

    def _latest_contract(self, patent: Patent) -> Contract | None:
        contracts = self._contracts.by_patent(patent.id)
        if not contracts:
            return None
        active = [item for item in contracts if item.is_active()]
        pool = active or [
            item for item in contracts if item.status is not ContractStatus.CANCELLED
        ]
        if not pool:
            return None
        return max(pool, key=lambda item: item.conclusion_date)

    def _payment_status(self, patent: Patent) -> str:
        last = self._payments.last_confirmed(patent.id)
        if last is None:
            return "нет подтверждённых платежей"
        if last.status is PaymentStatus.CONFIRMED:
            return f"оплачен до {period_end(last.period).isoformat()}"
        return last.status.value

    # --- операция 16: выгрузить реестр ------------------------------------
    def export(
        self,
        *,
        report_id: str,
        export_format: ReportFormat,
        anonymize: bool | None,
        actor: User | None,
    ) -> ExportResult:
        admin = self._access.require_export_right(actor)
        assert actor is not None
        report = self._reports.require(report_id)

        if anonymize is None:
            anonymize = not admin.may_see_personal_data()
        if anonymize is False and not admin.may_see_personal_data():
            self._audit.record(
                at=self._clock.now(),
                actor=actor.login,
                action="export_report_denied",
                outcome="failure",
                entity_type="report",
                entity_id=report.id,
                details={"reason": "нет права на персональные данные"},
            )
            raise ForbiddenError(
                "нет права на персональные данные: выгрузка в полном виде отклонена, "
                "доступна только обезличенная выгрузка",
                code="PERSONAL_DATA_FORBIDDEN",
            )

        rows = [row.to_dict() for row in report.rows]
        if anonymize:
            rows = [
                {**row, "citizen_name": f"ИГ-{row['citizen_id'][:8]}"}
                for row in rows
            ]
        stamp = report.snapshot_at.date().isoformat()
        if export_format is ReportFormat.CSV:
            content = self._render_csv(rows)
            filename = f"report-{report.id[:8]}-{stamp}.csv"
            media_type = "text/csv; charset=utf-8"
        else:
            header = (
                f"Report {report.id[:8]} from {stamp}, rows: {len(rows)}, "
                f"critical: {report.critical_count}"
            )
            lines = [header]
            for row in rows:
                lines.append(self._pdf_line(row))
            content = render_pdf(title="Patent registry report", lines=lines)
            filename = f"report-{report.id[:8]}-{stamp}.pdf"
            media_type = "application/pdf"

        digest = hashlib.sha256(content).hexdigest()
        record = ExportRecord(
            format=export_format.value,
            filename=filename,
            sha256=digest,
            size=len(content),
            anonymized=anonymize,
            exported_by=actor.login,
            exported_at=self._clock.now(),
        )
        report.exports.append(record)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="export_report",
            entity_type="report",
            entity_id=report.id,
            details={
                "format": export_format.value,
                "anonymized": anonymize,
                "sha256": digest,
                "size": len(content),
            },
        )
        return ExportResult(
            content=content,
            filename=filename,
            media_type=media_type,
            sha256=digest,
            size=len(content),
            anonymized=anonymize,
            report=report,
            record=record,
        )

    @staticmethod
    def _render_csv(rows: list[dict]) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=CSV_DELIMITER, lineterminator="\r\n")
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(
                [
                    row["citizen_name"],
                    row["patent"],
                    row["region"],
                    row["patent_status"],
                    row["employer"] or "",
                    row["contract_date"] or "",
                    row["notification_date"] or "",
                    row["payment_status"],
                    row["deadline_status"],
                    "да" if row["critical"] else "нет",
                ]
            )
        return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")

    @staticmethod
    def _pdf_line(row: dict) -> str:
        return (
            f"{row['citizen_name']} | {row['patent']} | region {row['region']} | "
            f"{row['patent_status']} | {row['employer'] or '-'} | "
            f"contract {row['contract_date'] or '-'} | "
            f"notified {row['notification_date'] or '-'} | "
            f"{row['payment_status']} | {row['deadline_status']} | "
            f"{'CRITICAL' if row['critical'] else 'ok'}"
        )

    # --- чтение -----------------------------------------------------------
    def get(self, report_id: str, *, actor: User | None) -> dict:
        self._access.require_admin(actor)
        return self._reports.require(report_id).to_dict()

    def list_reports(self, *, actor: User | None) -> list[dict]:
        self._access.require_admin(actor)
        return [report.to_dict() for report in self._reports.all()]
