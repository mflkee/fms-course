"""Планировщик задач (лаб. 5, ``ПланировщикЗадач``).

Ежедневный контроль — не отдельная системная операция: он вызывает уже
описанные операции 9 (пересчёт сроков) и доставку напоминаний. Решение о
прекращении патента из-за неуплаты планировщик только выявляет — операцию 13
выполняет администратор.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.control.deadline_service import DeadlineService
from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.enums import PointKind
from app.entity.patent import Patent
from app.repository.audit import AuditRepository
from app.repository.patents import PatentRepository


@dataclass(kw_only=True)
class DailyControlResult:
    processed: int
    recalculated: list[str] = field(default_factory=list)
    reminders_delivered: int = 0
    patents_with_unpaid_period: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "processed_patents": self.processed,
            "recalculated": self.recalculated,
            "reminders_delivered": self.reminders_delivered,
            "patents_with_unpaid_period": self.patents_with_unpaid_period,
        }


class Scheduler:
    def __init__(
        self,
        patents: PatentRepository,
        deadlines: DeadlineService,
        reminders: ReminderService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._patents = patents
        self._deadlines = deadlines
        self._reminders = reminders
        self._clock = clock
        self._audit = audit

    def run_daily_control(self, *, actor: str = "scheduler") -> DailyControlResult:
        result = DailyControlResult(processed=0)
        for patent in self._patents.current():
            result.processed += 1
            self._deadlines.recalculate(
                patent, reason="ежедневный контроль сроков", actor=actor
            )
            result.recalculated.append(patent.id)

        delivered = self._reminders.deliver_due()
        result.reminders_delivered = len(delivered)

        for patent in self._patents.current():
            for point in self._deadlines.overdue_open_points(patent):
                if point.kind is not PointKind.PAY_NDFL:
                    continue
                result.patents_with_unpaid_period.append(
                    {
                        "patent_id": patent.id,
                        "paid_until": (
                            patent.paid_until.isoformat() if patent.paid_until else None
                        ),
                        "next_period": patent.next_uncovered_period(),
                        "deadline_point_id": point.id,
                    }
                )
                break

        self._audit.record(
            at=self._clock.now(),
            actor=actor,
            action="daily_control",
            details=result.to_dict(),
        )
        return result

    def candidate_patents_for_nonpayment(self) -> list[Patent]:
        """Патенты, у которых истёк оплаченный период и нет подтверждённого платежа."""
        today = self._clock.today()
        candidates: list[Patent] = []
        for patent in self._patents.current():
            if patent.paid_until is None:
                continue
            if today > patent.paid_until and patent.paid_until < patent.valid_until:
                candidates.append(patent)
        return candidates
