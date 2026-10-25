"""Репозиторий патентов (лаб. 5, ``РеестрПатентов``)."""

from __future__ import annotations

from app.entity.enums import CURRENT_PATENT_STATUSES
from app.entity.patent import Patent
from app.repository.base import InMemoryRepository


class PatentRepository(InMemoryRepository[Patent]):
    entity_name = "патент"

    def active_by_citizen(self, citizen_id: str) -> Patent | None:
        for patent in self.all():
            if patent.citizen_id == citizen_id and patent.status in CURRENT_PATENT_STATUSES:
                return patent
        return None

    def all_by_citizen(self, citizen_id: str) -> list[Patent]:
        return self.filter(lambda patent: patent.citizen_id == citizen_id)

    def by_requisites(self, series: str, number: str) -> Patent | None:
        series = series.strip()
        number = number.strip()
        for patent in self.all():
            if patent.series.strip() == series and patent.number.strip() == number:
                return patent
        return None

    def current(self) -> list[Patent]:
        return self.filter(lambda patent: patent.is_current())

    def by_region(self, region_code: str) -> list[Patent]:
        return self.filter(lambda patent: patent.region_code == region_code)
