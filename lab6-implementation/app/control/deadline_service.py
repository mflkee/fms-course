"""Модуль контроля сроков (лаб. 5, ``МодульКонтроляСроков``), операции 9 и 10.

Здесь в одном месте живёт правило «2 месяца с даты выдачи патента» и все
производные сроки. Сервисы патентов, договоров, уведомлений и НДФЛ не
дублируют расчёт — они вызывают этот модуль (как и записано в лаб. 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.contract import Contract
from app.entity.deadline import DeadlinePoint, Reminder
from app.entity.enums import PointKind, PointStatus
from app.entity.patent import Patent
from app.errors import ConflictError, ValidationFailure
from app.repository.audit import AuditRepository
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository
from app.repository.patents import PatentRepository

CRITICAL_DAYS_LEFT = 7
EXTEND_POINT_LEAD_DAYS = 30


@dataclass(kw_only=True)
class DeadlineSummary:
    patent_id: str
    employment_deadline: date
    open_points: list[DeadlinePoint]
    critical_points: list[DeadlinePoint]
    overdue_points: list[DeadlinePoint]

    def to_dict(self) -> dict:
        return {
            "patent_id": self.patent_id,
            "employment_deadline": self.employment_deadline.isoformat(),
            "open": [point.to_dict() for point in self.open_points],
            "critical": [point.to_dict() for point in self.critical_points],
            "overdue": [point.to_dict() for point in self.overdue_points],
            "counts": {
                "open": len(self.open_points),
                "critical": len(self.critical_points),
                "overdue": len(self.overdue_points),
            },
        }


class DeadlineService:
    def __init__(
        self,
        points: DeadlinePointRepository,
        patents: PatentRepository,
        contracts: ContractRepository,
        reminders: ReminderService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._points = points
        self._patents = patents
        self._contracts = contracts
        self._reminders = reminders
        self._clock = clock
        self._audit = audit

    # --- расчёт плановых дат ---------------------------------------------
    def planned_date_for(self, patent: Patent, kind: PointKind) -> date:
        if kind in {PointKind.CONCLUDE_CONTRACT, PointKind.SEND_NOTIFICATION}:
            return patent.employment_deadline
        if kind is PointKind.PAY_NDFL:
            return patent.first_payment_due_date()
        if kind is PointKind.EXTEND_PATENT:
            return patent.valid_until - timedelta(days=EXTEND_POINT_LEAD_DAYS)
        if kind is PointKind.CONTRACT_END:
            contract = self._contracts.active_by_patent(patent.id)
            return (contract.end_date if contract and contract.end_date else patent.valid_until)
        raise ValidationFailure(f"неизвестный вид контрольной точки: {kind}", code="POINT_KIND")

    def create_patent_points(self, patent: Patent) -> list[DeadlinePoint]:
        """Комплект точек при регистрации патента: минимум две (ИНВ-9)."""
        kinds = [
            PointKind.CONCLUDE_CONTRACT,
            PointKind.SEND_NOTIFICATION,
            PointKind.PAY_NDFL,
            PointKind.EXTEND_PATENT,
        ]
        points: list[DeadlinePoint] = []
        for kind in kinds:
            point = self._create(patent, kind, self.planned_date_for(patent, kind))
            points.append(point)
        return points

    def _create(
        self, patent: Patent, kind: PointKind, planned_date: date
    ) -> DeadlinePoint:
        today = self._clock.today()
        status = PointStatus.OPEN
        critical = (planned_date - today).days <= CRITICAL_DAYS_LEFT
        if planned_date < today:
            status = PointStatus.CRITICAL
            critical = True
        point = DeadlinePoint(
            patent_id=patent.id,
            kind=kind,
            planned_date=planned_date,
            status=status,
            critical=critical,
        )
        return self._points.add(point)

    def open_point(
        self, patent: Patent, kind: PointKind, planned_date: date | None = None
    ) -> DeadlinePoint:
        planned = planned_date or self.planned_date_for(patent, kind)
        return self._create(patent, kind, planned)

    def ensure_point(self, patent: Patent, kind: PointKind) -> DeadlinePoint:
        point = self._points.latest_by_kind(patent.id, kind)
        if point is None:
            return self.open_point(patent, kind)
        return point

    def close_point(
        self, patent: Patent, kind: PointKind, on_date: date, *, late: bool = False
    ) -> DeadlinePoint | None:
        point = self._points.latest_by_kind(patent.id, kind)
        if point is None or point.is_closed():
            return point
        point.actual_date = on_date
        point.status = PointStatus.DONE
        point.critical = False
        point.late = late
        point.violation_date = on_date if late else None
        self._reminders.cancel_for_point(point.id)
        return point

    def cancel_all(self, patent: Patent, reason: str) -> int:
        cancelled = 0
        for point in self._points.by_patent(patent.id):
            if point.is_open():
                point.cancel(reason)
                self._reminders.cancel_for_point(point.id)
                cancelled += 1
        return cancelled

    # --- операция 9: пересчёт сроков --------------------------------------
    def recalculate(
        self, patent: Patent, *, reason: str = "плановый пересчёт", actor: str = "scheduler"
    ) -> DeadlineSummary:
        today = self._clock.today()
        for point in self._points.by_patent(patent.id):
            if point.is_closed():
                continue
            point.planned_date = self.planned_date_for(patent, point.kind)
            if point.planned_date < today:
                point.mark_overdue()
            elif (point.planned_date - today).days <= CRITICAL_DAYS_LEFT:
                point.status = PointStatus.CRITICAL
                point.critical = True
            else:
                point.status = PointStatus.OPEN
                point.critical = False
        self._reminders.reschedule_for_patent(patent)
        self._audit.record(
            at=self._clock.now(),
            actor=actor,
            action="recalculate_deadlines",
            entity_type="patent",
            entity_id=patent.id,
            details={"reason": reason},
        )
        return self.summary(patent)

    def summary(self, patent: Patent) -> DeadlineSummary:
        points = self._points.by_patent(patent.id)
        open_points = [point for point in points if point.is_open()]
        critical = [
            point
            for point in open_points
            if point.critical or point.status is PointStatus.CRITICAL
        ]
        overdue = [point for point in open_points if point.status is PointStatus.OVERDUE]
        return DeadlineSummary(
            patent_id=patent.id,
            employment_deadline=patent.employment_deadline,
            open_points=open_points,
            critical_points=critical,
            overdue_points=overdue,
        )

    def points_for_patent(self, patent: Patent) -> list[DeadlinePoint]:
        return sorted(
            self._points.by_patent(patent.id),
            key=lambda point: point.planned_date,
        )

    def point(self, point_id: str) -> DeadlinePoint:
        return self._points.require(point_id)

    def latest_point(self, patent_id: str, kind: PointKind) -> DeadlinePoint | None:
        return self._points.latest_by_kind(patent_id, kind)

    def overdue_open_points(self, patent: Patent) -> list[DeadlinePoint]:
        return [
            point
            for point in self._points.open_by_patent(patent.id)
            if point.planned_date < self._clock.today()
        ]

    # --- операция 10: фиксация нарушения ---------------------------------
    def register_violation(
        self, point_id: str, detected_at: date, *, actor: str
    ) -> tuple[DeadlinePoint, Reminder]:
        if detected_at > self._clock.today():
            raise ValidationFailure(
                "дата обнаружения нарушения не может быть в будущем",
                code="DATE_IN_FUTURE",
                details={"detected_at": detected_at.isoformat()},
            )
        point = self._points.require(point_id)
        if point.is_closed():
            raise ConflictError(
                "нельзя зафиксировать нарушение по закрытой или отменённой точке: "
                "закрытие точки важнее отметки о нарушении",
                code="POINT_CLOSED",
                details={"point_id": point.id, "status": point.status.value},
            )
        if point.planned_date >= detected_at:
            raise ValidationFailure(
                "плановая дата точки ещё не наступила — нарушения срока нет",
                code="POINT_NOT_OVERDUE",
                details={
                    "planned_date": point.planned_date.isoformat(),
                    "detected_at": detected_at.isoformat(),
                },
            )
        point.mark_violation(detected_at)
        patent = self._patents.require(point.patent_id)
        reminder = self._reminders.escalate(
            point=point,
            text=(
                f"Нарушен срок «{point.kind.value}» по патенту "
                f"{patent.series} {patent.number}: плановая дата "
                f"{point.planned_date.isoformat()}, нарушение зафиксировано "
                f"{detected_at.isoformat()}. Риск аннулирования патента."
            ),
        )
        self._audit.record(
            at=self._clock.now(),
            actor=actor,
            action="register_deadline_violation",
            entity_type="deadline_point",
            entity_id=point.id,
            details={"detected_at": detected_at.isoformat()},
        )
        return point, reminder

    # --- вспомогательное --------------------------------------------------
    def contract_of(self, patent_id: str) -> Contract | None:
        return self._contracts.active_by_patent(patent_id)
