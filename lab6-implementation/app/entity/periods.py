"""Календарная арифметика сроков.

Правило «2 месяца с даты выдачи» (DESIGN.md, 7.1) считается календарными
месяцами: 15.01 + 2 мес = 15.03; 31.01 + 1 мес = 28/29.02.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


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


def valid_until_for(issue_date: date, months: int = 12) -> date:
    """Срок действия патента: 12 месяцев с даты выдачи минус один день."""
    return add_months(issue_date, months) - timedelta(days=1)
