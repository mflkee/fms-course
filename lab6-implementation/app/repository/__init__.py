"""Слой хранилищ (repository).

Все реализации — in-memory, но за интерфейсами: замена на БД затрагивает
только этот пакет и сборку зависимостей в ``app/container.py``.
"""

from app.repository.audit import AuditRepository
from app.repository.base import InMemoryRepository
from app.repository.catalogs import (
    ActivityTypeRepository,
    MvdOfficeRepository,
    RegionRepository,
)
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository, ReminderRepository
from app.repository.documents import DocumentRepository, ReportRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository
from app.repository.payments import PaymentRepository
from app.repository.people import CitizenRepository, EmployerRepository, UserRepository

__all__ = [
    "ActivityTypeRepository",
    "AuditRepository",
    "CitizenRepository",
    "ContractRepository",
    "DeadlinePointRepository",
    "DocumentRepository",
    "EmployerRepository",
    "InMemoryRepository",
    "MvdOfficeRepository",
    "NotificationRepository",
    "PatentRepository",
    "PaymentRepository",
    "RegionRepository",
    "ReminderRepository",
    "ReportRepository",
    "UserRepository",
]
