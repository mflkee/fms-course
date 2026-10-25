"""Граничный уровень (boundary): HTTP-экраны.

Каждый роутер соответствует «Экрану…» модели лаб. 5 и вызывает только
управляющий слой — ни сущности, ни репозитории из обработчиков не меняются
(кроме чтения справочников/точек для отображения).
"""

from app.boundary import (
    contracts,
    deadlines,
    notifications,
    patents,
    payments,
    reminders,
    reports,
    system,
)

__all__ = [
    "contracts",
    "deadlines",
    "notifications",
    "patents",
    "payments",
    "reminders",
    "reports",
    "system",
]
