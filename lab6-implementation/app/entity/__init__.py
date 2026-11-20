"""Сущности предметной области (DESIGN.md, раздел 5) в терминах Python.

Модули повторяют классы модели, но с английскими именами; соответствие
русским названиям — в таблице README лаб. 6.
"""

from app.entity.catalogs import ActivityType, MvdOffice, Region
from app.entity.clock import Clock, FixedClock, SystemClock
from app.entity.contract import CivilContract, Contract, EmploymentContract
from app.entity.deadline import DeadlinePoint, Reminder, ReminderSettings
from app.entity.documents import Document
from app.entity.notification import Notification
from app.entity.patent import Patent, default_valid_until
from app.entity.people import Employer, ForeignCitizen

__all__ = [
    "ActivityType",
    "CivilContract",
    "Clock",
    "Contract",
    "DeadlinePoint",
    "Document",
    "Employer",
    "EmploymentContract",
    "FixedClock",
    "ForeignCitizen",
    "MvdOffice",
    "Notification",
    "Patent",
    "Region",
    "Reminder",
    "ReminderSettings",
    "SystemClock",
    "default_valid_until",
]
