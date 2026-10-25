"""Сервис напоминаний (лаб. 5, ``СервисНапоминаний``).

Напоминание существует только при контрольной точке (ИНВ-9), поэтому сервис
не создаёт их «напрямую»: он раскладывает моменты предупреждений
(30/14/7/3/1 день по умолчанию) по открытым точкам. По закрытым и отменённым
точкам напоминания не создаются, а запланированные — снимаются.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.entity.clock import Clock
from app.entity.deadline import DeadlinePoint, Reminder
from app.entity.enums import NotificationChannel, PointKind
from app.entity.patent import Patent
from app.entity.user import CitizenUser, ReminderSettings
from app.errors import ValidationFailure
from app.repository.deadline_points import DeadlinePointRepository, ReminderRepository
from app.repository.patents import PatentRepository
from app.repository.people import UserRepository

DEFAULT_DAYS = [30, 14, 7, 3, 1]

POINT_TITLES = {
    PointKind.CONCLUDE_CONTRACT: "заключить договор",
    PointKind.SEND_NOTIFICATION: "направить уведомление МВД",
    PointKind.PAY_NDFL: "уплатить авансовый платёж НДФЛ",
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
        users: UserRepository,
        patents: PatentRepository,
        clock: Clock,
    ) -> None:
        self._reminders = reminders
        self._points = points
        self._users = users
        self._patents = patents
        self._clock = clock

    # --- настройки (операция 8) -----------------------------------------
    def configure(
        self,
        *,
        profile: CitizenUser,
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
        profile.reminder_settings = settings

        created: list[Reminder] = []
        skipped_closed = 0
        for patent in self._patents.all_by_citizen(profile.citizen_id):
            if not patent.is_current():
                continue
            closed = [
                point for point in self._points.by_patent(patent.id) if point.is_closed()
            ]
            skipped_closed += len(closed)
            if consent:
                created.extend(self._schedule_for_patent(patent, settings))
            else:
                # отзыв согласия останавливает уже запланированные напоминания
                self._reminders.cancel_for_patent(patent.id)
        return ReminderPlan(settings=settings, created=created, skipped_closed=skipped_closed)

    def _schedule_for_patent(
        self, patent: Patent, settings: ReminderSettings
    ) -> list[Reminder]:
        """Пересоздать напоминания открытых точек без дублей."""
        created: list[Reminder] = []
        for point in self._points.open_by_patent(patent.id):
            self._reminders.cancel_for_point(point.id)
            created.extend(self._schedule([point], settings))
        return created

    # --- планирование ----------------------------------------------------
    def settings_for_patent(self, patent: Patent) -> ReminderSettings | None:
        profile = self._users.citizen_profile(patent.citizen_id)
        if not isinstance(profile, CitizenUser) or not profile.has_reminder_consent():
            return None
        return profile.reminder_settings

    def schedule_for_point(self, point: DeadlinePoint) -> list[Reminder]:
        patent = self._patents.find(point.patent_id)
        if patent is None or not point.is_open():
            return []
        settings = self.settings_for_patent(patent)
        if settings is None:
            return []
        self._reminders.cancel_for_point(point.id)
        return self._schedule([point], settings)

    def _schedule(
        self, points: list[DeadlinePoint], settings: ReminderSettings
    ) -> list[Reminder]:
        created: list[Reminder] = []
        today = self._clock.today()
        channel = settings.channels[0]
        for point in points:
            if not point.is_open():
                continue
            for days in settings.days:
                planned_at = point.planned_date - timedelta(days=days)
                if planned_at < today:
                    continue  # момент уже прошёл — «просроченное» напоминание не создаём
                reminder = Reminder(
                    point_id=point.id,
                    channel=channel,
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
            self._reminders.cancel_for_point(point.id)
            if settings is not None:
                created.extend(self._schedule([point], settings))
        return created

    def schedule_for_patent(self, patent: Patent) -> list[Reminder]:
        settings = self.settings_for_patent(patent)
        if settings is None:
            return []
        return self._schedule_for_patent(patent, settings)

    def cancel_for_point(self, point_id: str) -> int:
        return self._reminders.cancel_for_point(point_id)

    def cancel_for_patent(self, patent_id: str) -> int:
        return self._reminders.cancel_for_patent(patent_id)

    # --- доставка и эскалация -------------------------------------------
    def deliver_due(self) -> list[Reminder]:
        today = self._clock.today()
        delivered: list[Reminder] = []
        for reminder in self._reminders.scheduled():
            if reminder.planned_at > today:
                continue
            reminder.mark_sent(self._clock.now())
            if reminder.channel in {
                NotificationChannel.EMAIL,
                NotificationChannel.PERSONAL_ACCOUNT,
                NotificationChannel.EPGU,
            }:
                reminder.mark_delivered()
            delivered.append(reminder)
        return delivered

    def escalate(self, *, point: DeadlinePoint, text: str) -> Reminder:
        """Эскалация нарушения срока (операция 10): критичное напоминание."""
        patent = self._patents.find(point.patent_id)
        profile = (
            self._users.citizen_profile(patent.citizen_id) if patent is not None else None
        )
        channel = (
            profile.preferred_channel
            if isinstance(profile, CitizenUser)
            else NotificationChannel.EMAIL
        )
        reminder = Reminder(
            point_id=point.id,
            channel=channel,
            days_before=0,
            planned_at=self._clock.today(),
            text=text,
            escalation=True,
        )
        reminder.mark_sent(self._clock.now())
        reminder.mark_delivered()
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

    def cancel_all_for_closed(self, patent: Patent) -> int:
        cancelled = 0
        for point in self._points.by_patent(patent.id):
            if point.is_closed():
                cancelled += self._reminders.cancel_for_point(point.id)
        return cancelled

    def today(self) -> date:
        return self._clock.today()
