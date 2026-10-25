"""Пользователь (абстрактный) и три роли учётной записи (лаб. 2, лаб. 5)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.entity.enums import NotificationChannel, Role
from app.entity.ids import new_id


@dataclass(kw_only=True)
class ReminderSettings:
    channels: list[NotificationChannel]
    days: list[int]
    consent: bool
    updated_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "channels": [channel.value for channel in self.channels],
            "days": list(self.days),
            "consent": self.consent,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass(kw_only=True)
class User(ABC):
    login: str
    contact: str
    id: str = field(default_factory=new_id)
    active: bool = True

    @property
    @abstractmethod
    def role(self) -> Role:
        """Роль учётной записи."""

    def has_role(self, role: Role) -> bool:
        return self.role is role

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "login": self.login,
            "role": self.role.value,
            "contact": self.contact,
            "active": self.active,
        }


@dataclass(kw_only=True)
class CitizenUser(User):
    citizen_id: str
    preferred_channel: NotificationChannel = NotificationChannel.EMAIL
    reminder_settings: ReminderSettings | None = None

    @property
    def role(self) -> Role:
        return Role.CITIZEN

    def has_reminder_consent(self) -> bool:
        return bool(
            self.reminder_settings
            and self.reminder_settings.consent
            and self.reminder_settings.channels
        )

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update(
            {
                "citizen_id": self.citizen_id,
                "preferred_channel": self.preferred_channel.value,
                "reminder_settings": (
                    self.reminder_settings.to_dict() if self.reminder_settings else None
                ),
            }
        )
        return payload


@dataclass(kw_only=True)
class EmployerRepresentative(User):
    employer_id: str
    position: str

    @property
    def role(self) -> Role:
        return Role.EMPLOYER_REP

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update({"employer_id": self.employer_id, "position": self.position})
        return payload


@dataclass(kw_only=True)
class SystemAdministrator(User):
    export_right: bool = True
    personal_data_right: bool = False

    @property
    def role(self) -> Role:
        return Role.ADMIN

    def may_export(self) -> bool:
        return self.export_right

    def may_see_personal_data(self) -> bool:
        return self.personal_data_right

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update(
            {
                "export_right": self.export_right,
                "personal_data_right": self.personal_data_right,
            }
        )
        return payload
