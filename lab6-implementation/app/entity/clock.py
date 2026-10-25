"""Источник времени.

Все сроки считаются от «сегодня», поэтому время вынесено в явную зависимость:
тесты подставляют ``FixedClock`` и получают воспроизводимые результаты, а
приложение — ``SystemClock``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    """Системные часы в UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


class FixedClock:
    """Неподвижные часы для тестов и демонстраций."""

    def __init__(self, today: date, now: datetime | None = None) -> None:
        self._today = today
        self._now = now or datetime(
            today.year, today.month, today.day, 12, 0, tzinfo=UTC
        )

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._today

    def set_today(self, today: date) -> None:
        self._today = today
        self._now = datetime(today.year, today.month, today.day, 12, 0, tzinfo=UTC)
