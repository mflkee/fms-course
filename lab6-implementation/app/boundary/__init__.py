"""Граничный уровень (boundary): HTTP-экраны.

Каждый роутер соответствует «Экрану…» модели проектирования DESIGN.md
(раздел 6) и вызывает только управляющий слой — ни сущности, ни репозитории
из обработчиков не меняются (кроме чтения справочников для отображения).
"""

from app.boundary import contracts, deadlines, notifications, patents, reminders, system

__all__ = [
    "contracts",
    "deadlines",
    "notifications",
    "patents",
    "reminders",
    "system",
]
