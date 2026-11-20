"""Управляющий уровень (control): сервисы и инварианты.

Соответствие классам проектирования (DESIGN.md, раздел 6):
``PatentService`` — СервисПатентов, ``ContractService`` — СервисДоговоров,
``NotificationService`` — СервисУведомлений, ``DeadlineService`` —
СервисСроков, ``ReminderService`` — напоминания в составе сроков.
"""

from app.control.contract_service import ContractService
from app.control.deadline_service import DeadlineService
from app.control.notification_service import NotificationService
from app.control.patent_service import PatentService
from app.control.reminder_service import ReminderService

__all__ = [
    "ContractService",
    "DeadlineService",
    "NotificationService",
    "PatentService",
    "ReminderService",
]
