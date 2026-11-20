"""Слой хранилищ (repository).

Все реализации — in-memory, но за интерфейсами: замена на БД затрагивает
только этот пакет и сборку зависимостей в ``app/container.py``.
"""

from app.repository.base import InMemoryRepository
from app.repository.catalogs import (
    ActivityTypeRepository,
    MvdOfficeRepository,
    RegionRepository,
)
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository, ReminderRepository
from app.repository.documents import DocumentRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository
from app.repository.people import CitizenRepository, EmployerRepository

__all__ = [
    "ActivityTypeRepository",
    "CitizenRepository",
    "ContractRepository",
    "DeadlinePointRepository",
    "DocumentRepository",
    "EmployerRepository",
    "InMemoryRepository",
    "MvdOfficeRepository",
    "NotificationRepository",
    "PatentRepository",
    "RegionRepository",
    "ReminderRepository",
]
