"""Сервис напоминаний (``СервисНапоминаний``), операция 8 ``настроитьНапоминания``.

Рассылки нет: напоминание отображается в личном кабинете гражданина
(``GET /reminders/due``). Напоминание существует только при контрольной точке
(ИНВ-6), поэтому сервис раскладывает моменты предупреждений (30/14/7/3/1 день
по умолчанию) по открытым точкам. Напоминания закрытых точек не создаются, а
запланированные — переводятся в «пропущено» с указанием причины.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.entity.clock import Clock
from app.entity.deadline import DeadlinePoint, Reminder, ReminderSettings
from app.entity.enums import NotificationChannel, PointKind, ReminderStatus
from app.entity.patent import Patent
from app.entity.people import ForeignCitizen
from app.errors import ValidationFailure
from app.repository.deadline_points import DeadlinePointRepository, ReminderRepository
from app.repository.patents import PatentRepository
from app.repository.people import CitizenRepository

DEFAULT_DAYS = [30, 14, 7, 3, 1]

SHOWABLE_STATUSES = frozenset({ReminderStatus.SCHEDULED, ReminderStatus.SHOWN})

POINT_TITLES = {
    PointKind.CONCLUDE_CONTRACT: "заключить договор",
    PointKind.SEND_NOTIFICATION: "направить уведомление МВД",
    PointKind.EXTEND_PATENT: "продлить патент",
    PointKind.CONTRACT_END: "окончание срока договора",
}


@dataclass(kw_only=True)
class ReminderPlan:
    settings: ReminderSettings
    created: list[Reminder]
    skipped_closed: int


class ReminderService:
    def __init__(
        self,
        reminders: ReminderRepository,
        points: DeadlinePointRepository,
        citizens: CitizenRepository,
        patents: PatentRepository,
        clock: Clock,
    ) -> None:
        self._reminders = reminders
        self._points = points
        self._citizens = citizens
        self._patents = patents
        self._clock = clock

    # --- настройки (операция 8) -----------------------------------------
    def configure(
        self,
        *,
        citizen: ForeignCitizen,
        channels: list[NotificationChannel],
        days: list[int],
        consent: bool,
    ) -> ReminderPlan:
        if not channels:
            raise ValidationFailure(
                "укажите хотя бы один канал напоминаний", code="REMINDER_CHANNELS_EMPTY"
            )
        if not days:
            raise ValidationFailure(
                "укажите хотя бы один момент напоминания (за сколько дней)",
                code="REMINDER_DAYS_EMPTY",
            )
        if any(day <= 0 for day in days):
            raise ValidationFailure(
                "моменты напоминаний задаются положительным числом дней",
                code="REMINDER_DAYS_INVALID",
            )
        settings = ReminderSettings(
            channels=list(channels),
            days=sorted(set(days), reverse=True),
            consent=consent,
            updated_at=self._clock.now(),
        )
        citizen.reminder_settings = settings

        created: list[Reminder] = []
        skipped_closed = 0
        for patent in self._patents.all_by_citizen(citizen.id):
            if not patent.is_current():
                continue
            closed = [
                point for point in self._points.by_patent(patent.id) if point.is_closed()
            ]
            skipped_closed += len(closed)
            if consent:
                created.extend(self._schedule_for_patent(patent, settings))
            else:
                self._reminders.skip_for_patent(
                    patent.id, "согласие на напоминания отозвано"
                )
        return ReminderPlan(settings=settings, created=created, skipped_closed=skipped_closed)

    def _schedule_for_patent(
        self, patent: Patent, settings: ReminderSettings
    ) -> list[Reminder]:
        """Пересоздать напоминания открытых точек без дублей."""
        created: list[Reminder] = []
        for point in self._points.open_by_patent(patent.id):
            self._reminders.skip_for_point(point.id, "заменено новым планом напоминаний")
            created.extend(self._schedule([point], settings))
        return created

    # --- планирование ----------------------------------------------------
    def settings_for_patent(self, patent: Patent) -> ReminderSettings | None:
        citizen = self._citizens.find(patent.citizen_id)
        if citizen is None or not citizen.has_reminder_consent():
            return None
        return citizen.reminder_settings

    def schedule_for_point(self, point: DeadlinePoint) -> list[Reminder]:
        patent = self._patents.find(point.patent_id)
        if patent is None or not point.is_open():
            return []
        settings = self.settings_for_patent(patent)
        if settings is None:
            return []
        self._reminders.skip_for_point(point.id, "заменено новым планом напоминаний")
        return self._schedule([point], settings)

    def _schedule(
        self, points: list[DeadlinePoint], settings: ReminderSettings
    ) -> list[Reminder]:
        created: list[Reminder] = []
        today = self._clock.today()
        for point in points:
            if not point.is_open():
                continue
            for days in settings.days:
                planned_at = point.planned_date - timedelta(days=days)
                if planned_at < today:
                    continue  # момент уже прошёл — «просроченное» напоминание не создаём
                reminder = Reminder(
                    point_id=point.id,
                    channel=NotificationChannel.PERSONAL_ACCOUNT,
                    days_before=days,
                    planned_at=planned_at,
                    text=self._text(point, days),
                )
                created.append(self._reminders.add(reminder))
        return created

    @staticmethod
    def _text(point: DeadlinePoint, days: int) -> str:
        title = POINT_TITLES.get(point.kind, point.kind.value)
        return (
            f"Через {days} дн. (до {point.planned_date.isoformat()}) нужно {title}"
        )

    def reschedule_for_patent(self, patent: Patent) -> list[Reminder]:
        """Перепланировать напоминания открытых точек (после пересчёта сроков)."""
        settings = self.settings_for_patent(patent)
        created: list[Reminder] = []
        for point in self._points.open_by_patent(patent.id):
            self._reminders.skip_for_point(point.id, "заменено пересчётом сроков")
            if settings is not None:
                created.extend(self._schedule([point], settings))
        return created

    def schedule_for_patent(self, patent: Patent) -> list[Reminder]:
        settings = self.settings_for_patent(patent)
        if settings is None:
            return []
        return self._schedule_for_patent(patent, settings)

    def skip_for_point(self, point_id: str, reason: str) -> int:
        return self._reminders.skip_for_point(point_id, reason)

    def skip_for_patent(self, patent_id: str, reason: str) -> int:
        return self._reminders.skip_for_patent(patent_id, reason)

    # --- личный кабинет --------------------------------------------------
    def show_due(self, citizen: ForeignCitizen) -> list[Reminder]:
        """Актуальные напоминания гражданина: момент наступил, точка открыта.

        Запланированные переводятся в «показано» (датаОтправки = момент показа).
        Уже показанные возвращаются повторно, пока точка открыта.
        """
        today = self._clock.today()
        now = self._clock.now()
        due: list[Reminder] = []
        for patent in self._patents.all_by_citizen(citizen.id):
            for point in self._points.open_by_patent(patent.id):
                for reminder in self._reminders.by_point(point.id):
                    if reminder.planned_at > today or reminder.status not in SHOWABLE_STATUSES:
                        continue
                    reminder.mark_shown(now)
                    due.append(reminder)
        return sorted(due, key=lambda item: (item.planned_at, item.point_id))

    # --- эскалация (операция 10) -----------------------------------------
    def escalate(self, *, point: DeadlinePoint, text: str) -> Reminder:
        """Эскалация нарушения срока: напоминание в кабинете, запланированное на сегодня."""
        reminder = Reminder(
            point_id=point.id,
            channel=NotificationChannel.PERSONAL_ACCOUNT,
            days_before=0,
            planned_at=self._clock.today(),
            text=text,
            escalation=True,
        )
        return self._reminders.add(reminder)

    # --- чтение ----------------------------------------------------------
    def list_for_point(self, point_id: str) -> list[Reminder]:
        return sorted(self._reminders.by_point(point_id), key=lambda item: item.planned_at)

    def scheduled(self) -> list[Reminder]:
        return sorted(self._reminders.scheduled(), key=lambda item: item.planned_at)

    def all(self) -> list[Reminder]:
        return sorted(self._reminders.all(), key=lambda item: item.planned_at)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for reminder in self._reminders.all():
            counts[reminder.status.value] = counts.get(reminder.status.value, 0) + 1
        return counts

    def today(self) -> date:
        return self._clock.today()

    def now(self) -> datetime:
        return self._clock.now()
