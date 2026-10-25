"""Календарная арифметика: месяцы, календарные периоды действия патента.

Правило «2 месяца с даты выдачи» из дорожной карты (п. 7.1) считается
календарными месяцами: 15.01 + 2 мес = 15.03; 31.01 + 1 мес = 28/29.02.
Период оплаты НДФЛ — календарный месяц, строкой ``YYYY-MM``.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def add_months(value: date, months: int) -> date:
    """Прибавить календарные месяцы с «прижатием» к концу месяца."""
    total = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def period_of(value: date) -> str:
    """Календарный период (месяц) даты в формате ``YYYY-MM``."""
    return f"{value.year:04d}-{value.month:02d}"


def parse_period(period: str) -> tuple[int, int]:
    match = _PERIOD_RE.match(period or "")
    if not match:
        raise ValueError(f"период должен быть в формате YYYY-MM, получено: {period!r}")
    return int(match.group(1)), int(match.group(2))


def period_start(period: str) -> date:
    year, month = parse_period(period)
    return date(year, month, 1)


def period_end(period: str) -> date:
    year, month = parse_period(period)
    return date(year, month, calendar.monthrange(year, month)[1])


def next_period(period: str) -> str:
    year, month = parse_period(period)
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


def previous_period(period: str) -> str:
    year, month = parse_period(period)
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def valid_until_for(issue_date: date, months: int = 12) -> date:
    """Срок действия патента: 12 месяцев с даты выдачи минус один день."""
    return add_months(issue_date, months) - timedelta(days=1)
