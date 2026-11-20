"""Справочники: регион, вид деятельности, территориальный орган МВД (DESIGN.md, раздел 5)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.entity.ids import new_id


@dataclass(kw_only=True)
class Region:
    """Субъект РФ (``Регион``: код, наименование)."""

    code: str
    name: str
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {"code": self.code, "name": self.name}


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
    """Территориальный орган МВД — адресат уведомления (``ТерриториальныйОрганМВД``)."""

    code: str
    name: str
    address: str
    region_code: str
    id: str = field(default_factory=new_id)

    def requisites(self) -> dict:
        return {"code": self.code, "name": self.name, "address": self.address}

    def to_dict(self) -> dict:
        return {**self.requisites(), "region_code": self.region_code}
