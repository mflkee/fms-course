"""Участники: иностранный гражданин, работодатель (лаб. 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.entity.ids import new_id


@dataclass(kw_only=True)
class ForeignCitizen:
    """Владелец патента, сторона трудовых отношений."""

    full_name: str
    birth_date: date
    citizenship: str
    identity_document: str
    inn: str
    address: str
    phone: str
    email: str
    status: str = "registered"
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "birth_date": self.birth_date.isoformat(),
            "citizenship": self.citizenship,
            "inn": self.inn,
            "status": self.status,
        }

    def to_public_dict(self) -> dict:
        """Данные в объёме, допустимом работодателю (операция 3)."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "citizenship": self.citizenship,
            "status": self.status,
        }


@dataclass(kw_only=True)
class Employer:
    """Организация, ИП или заказчик по ГПХ."""

    name: str
    inn: str
    ogrn: str
    address: str
    org_type: str
    contact_person: str
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "inn": self.inn,
            "ogrn": self.ogrn,
            "address": self.address,
            "type": self.org_type,
            "contact_person": self.contact_person,
        }
