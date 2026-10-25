"""Сущности предметной области (лаб. 2) в терминах Python.

Модули повторяют классы модели, но с английскими именами; соответствие
русским названиям — в таблице README лаб. 6.
"""

from app.entity.audit import AuditEvent
from app.entity.catalogs import ActivityType, MvdOffice, Region
from app.entity.clock import Clock, FixedClock, SystemClock
from app.entity.contract import CivilContract, Contract, EmploymentContract
from app.entity.deadline import DeadlinePoint, Reminder
from app.entity.documents import Document
from app.entity.notification import Notification
from app.entity.patent import Patent, default_valid_until
from app.entity.payment import TaxPayment
from app.entity.people import Employer, ForeignCitizen
from app.entity.report import ExportRecord, Report, ReportRow
from app.entity.user import (
    CitizenUser,
    EmployerRepresentative,
    ReminderSettings,
    SystemAdministrator,
    User,
)

__all__ = [
    "ActivityType",
    "AuditEvent",
    "CitizenUser",
    "CivilContract",
    "Clock",
    "Contract",
    "DeadlinePoint",
    "Document",
    "Employer",
    "EmployerRepresentative",
    "EmploymentContract",
    "ExportRecord",
    "FixedClock",
    "ForeignCitizen",
    "MvdOffice",
    "Notification",
    "Patent",
    "Region",
    "Reminder",
    "ReminderSettings",
    "Report",
    "ReportRow",
    "SystemAdministrator",
    "SystemClock",
    "TaxPayment",
    "User",
    "default_valid_until",
]
