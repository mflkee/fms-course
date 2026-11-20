"""Репозитории контрольных точек и напоминаний.

ИНВ-6 (композиция патента) обеспечивается структурно: точка создаётся только
для существующего патента, напоминание — только для существующей точки.
Удаления в репозиториях нет, поэтому «осиротевших» объектов не бывает.
"""

from __future__ import annotations

from app.entity.deadline import DeadlinePoint, Reminder
from app.entity.enums import OPEN_POINT_STATUSES, PointKind, ReminderStatus
from app.errors import ConflictError
from app.repository.base import InMemoryRepository
from app.repository.patents import PatentRepository


class DeadlinePointRepository(InMemoryRepository[DeadlinePoint]):
    entity_name = "контрольная точка"

    def __init__(self, patents: PatentRepository) -> None:
        super().__init__()
        self._patents = patents

    def add(self, item: DeadlinePoint) -> DeadlinePoint:
        if self._patents.find(item.patent_id) is None:
            raise ConflictError(
                f"контрольная точка не может существовать без патента: {item.patent_id}",
                code="INV-6",
            )
        return super().add(item)

    def by_patent(self, patent_id: str) -> list[DeadlinePoint]:
        return self.filter(lambda point: point.patent_id == patent_id)

    def open_by_patent(self, patent_id: str) -> list[DeadlinePoint]:
        return [
            point
            for point in self.by_patent(patent_id)
            if point.status in OPEN_POINT_STATUSES
        ]

    def open_points(self) -> list[DeadlinePoint]:
        return self.filter(lambda point: point.status in OPEN_POINT_STATUSES)

    def by_kind(self, patent_id: str, kind: PointKind) -> list[DeadlinePoint]:
        return self.filter(
            lambda point: point.patent_id == patent_id and point.kind is kind
        )

    def latest_by_kind(self, patent_id: str, kind: PointKind) -> DeadlinePoint | None:
        points = self.by_kind(patent_id, kind)
        return points[-1] if points else None


class ReminderRepository(InMemoryRepository[Reminder]):
    entity_name = "напоминание"

    def __init__(self, points: DeadlinePointRepository) -> None:
        super().__init__()
        self._points = points

    def add(self, item: Reminder) -> Reminder:
        if self._points.find(item.point_id) is None:
            raise ConflictError(
                f"напоминание не может существовать без контрольной точки: {item.point_id}",
                code="INV-6",
            )
        return super().add(item)

    def by_point(self, point_id: str) -> list[Reminder]:
        return self.filter(lambda reminder: reminder.point_id == point_id)

    def scheduled(self) -> list[Reminder]:
        return self.filter(lambda reminder: reminder.status is ReminderStatus.SCHEDULED)

    def skip_for_point(self, point_id: str, reason: str) -> int:
        skipped = 0
        for reminder in self.by_point(point_id):
            if reminder.status is ReminderStatus.SCHEDULED:
                reminder.skip(reason)
                skipped += 1
        return skipped

    def skip_for_patent(self, patent_id: str, reason: str) -> int:
        skipped = 0
        for point in self._points.by_patent(patent_id):
            skipped += self.skip_for_point(point.id, reason)
        return skipped
