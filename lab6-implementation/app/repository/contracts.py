"""Репозиторий договоров (лаб. 5, ``РеестрДоговоров``)."""

from __future__ import annotations

from app.entity.contract import Contract
from app.repository.base import InMemoryRepository


class ContractRepository(InMemoryRepository[Contract]):
    entity_name = "договор"

    def by_patent(self, patent_id: str) -> list[Contract]:
        return self.filter(lambda contract: contract.patent_id == patent_id)

    def active_by_patent(self, patent_id: str) -> Contract | None:
        """Действующий договор патента — проверка ИНВ-1."""
        for contract in self.by_patent(patent_id):
            if contract.is_active():
                return contract
        return None

    def has_active(self, patent_id: str) -> bool:
        return self.active_by_patent(patent_id) is not None

    def by_employer(self, employer_id: str) -> list[Contract]:
        return self.filter(lambda contract: contract.employer_id == employer_id)

    def active_by_employer(self, employer_id: str) -> list[Contract]:
        return [contract for contract in self.by_employer(employer_id) if contract.is_active()]
