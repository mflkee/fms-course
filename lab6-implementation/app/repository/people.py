"""Репозитории участников: иностранный гражданин и работодатель."""

from __future__ import annotations

from app.entity.people import Employer, ForeignCitizen
from app.repository.base import InMemoryRepository


class CitizenRepository(InMemoryRepository[ForeignCitizen]):
    entity_name = "иностранный гражданин"


class EmployerRepository(InMemoryRepository[Employer]):
    entity_name = "работодатель"
