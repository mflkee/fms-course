"""Управляющий уровень (control): сервисы, инварианты, планировщик.

Соответствие классам лаб. 5: ``PatentService`` — СервисПатентов,
``ContractService`` — СервисДоговоров, ``NotificationService`` —
СервисУведомлений, ``TaxService`` — СервисНДФЛ, ``DeadlineService`` —
МодульКонтроляСроков, ``ReminderService`` — СервисНапоминаний,
``ReportService`` — МодульОтчётности, ``AccessService`` — МодульПравДоступа,
``Scheduler`` — ПланировщикЗадач.
"""

from app.control.access_service import AccessService
from app.control.contract_service import ContractService
from app.control.deadline_service import DeadlineService
from app.control.notification_service import NotificationService
from app.control.patent_service import PatentService
from app.control.reminder_service import ReminderService
from app.control.report_service import ReportService
from app.control.scheduler import Scheduler
from app.control.tax_service import TaxService

__all__ = [
    "AccessService",
    "ContractService",
    "DeadlineService",
    "NotificationService",
    "PatentService",
    "ReminderService",
    "ReportService",
    "Scheduler",
    "TaxService",
]
