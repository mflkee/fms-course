"""Журнал аудита: единственная «запись», которую делает операция-запрос."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.entity.ids import new_id


@dataclass(kw_only=True)
class AuditEvent:
    at: datetime
    actor: str
    action: str
    outcome: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "at": self.at.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "outcome": self.outcome,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
        }
