"""Справочники: регион и вид деятельности (лаб. 2, классы ``Регион``, ``ВидДеятельности``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.entity.ids import new_id
from app.entity.money import money


@dataclass(kw_only=True)
class Region:
    """Субъект РФ: определяет стоимость патента и актуальность справочника."""

    code: str
    name: str
    patent_cost: Decimal
    actual_date: date
    id: str = field(default_factory=new_id)

    def cost_on(self, on_date: date) -> Decimal:
        """Стоимость патента на дату (ИНВ-7: сверяется с датой платежа)."""
        if on_date < self.actual_date:
            raise ValueError(
                f"справочник региона {self.code} неактуален на {on_date.isoformat()}"
            )
        return money(self.patent_cost)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "patent_cost": str(money(self.patent_cost)),
            "actual_date": self.actual_date.isoformat(),
        }


@dataclass(kw_only=True)
class ActivityType:
    """Профессия / вид работ, допустимый для патента."""

    code: str
    name: str
    allowed_for_patent: bool = True
    id: str = field(default_factory=new_id)

    def is_allowed(self) -> bool:
        return self.allowed_for_patent

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "allowed_for_patent": self.allowed_for_patent,
        }


@dataclass(kw_only=True)
class MvdOffice:
    """Территориальный орган МВД — адресат уведомления (лаб. 2)."""

    code: str
    name: str
    address: str
    region_code: str
    id: str = field(default_factory=new_id)

    def requisites(self) -> dict:
        return {"code": self.code, "name": self.name, "address": self.address}

    def to_dict(self) -> dict:
        return {**self.requisites(), "region_code": self.region_code}
