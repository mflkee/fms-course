"""Репозитории справочников: регионы, виды деятельности, органы МВД."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.entity.catalogs import ActivityType, MvdOffice, Region
from app.errors import NotFoundError, ValidationFailure
from app.repository.base import InMemoryRepository


class RegionRepository(InMemoryRepository[Region]):
    entity_name = "регион"

    def __init__(self) -> None:
        super().__init__()
        self._by_code: dict[str, Region] = {}

    def add(self, item: Region) -> Region:
        self._by_code[item.code] = item
        return super().add(item)

    def by_code(self, code: str) -> Region | None:
        return self._by_code.get(code)

    def require_code(self, code: str) -> Region:
        region = self.by_code(code)
        if region is None:
            raise ValidationFailure(
                f"регион не найден в справочнике: {code}", code="INV-4"
            )
        return region

    def cost_on(self, code: str, on_date: date) -> Decimal:
        region = self.require_code(code)
        try:
            return region.cost_on(on_date)
        except ValueError as exc:
            raise ValidationFailure(str(exc), code="STALE_CATALOG") from exc


class ActivityTypeRepository(InMemoryRepository[ActivityType]):
    entity_name = "вид деятельности"

    def __init__(self) -> None:
        super().__init__()
        self._by_code: dict[str, ActivityType] = {}

    def add(self, item: ActivityType) -> ActivityType:
        self._by_code[item.code] = item
        return super().add(item)

    def by_code(self, code: str) -> ActivityType | None:
        return self._by_code.get(code)

    def require_allowed(self, codes: list[str]) -> list[ActivityType]:
        """Все коды должны существовать и быть допустимыми для патента (ИНВ-4)."""
        resolved: list[ActivityType] = []
        for code in codes:
            activity = self.by_code(code)
            if activity is None:
                raise ValidationFailure(
                    f"вид деятельности не найден в справочнике: {code}", code="INV-4"
                )
            if not activity.is_allowed():
                raise ValidationFailure(
                    f"вид деятельности недопустим для патента: {code}", code="INV-4"
                )
            resolved.append(activity)
        return resolved

    def allowed(self) -> list[ActivityType]:
        return [activity for activity in self.all() if activity.is_allowed()]


class MvdOfficeRepository(InMemoryRepository[MvdOffice]):
    entity_name = "территориальный орган МВД"

    def __init__(self) -> None:
        super().__init__()
        self._by_code: dict[str, MvdOffice] = {}

    def add(self, item: MvdOffice) -> MvdOffice:
        self._by_code[item.code] = item
        return super().add(item)

    def for_region(self, region_code: str) -> MvdOffice:
        for office in self.all():
            if office.region_code == region_code:
                return office
        raise NotFoundError(
            f"территориальный орган МВД для региона {region_code} не найден",
            code="MVD_OFFICE_NOT_FOUND",
        )
