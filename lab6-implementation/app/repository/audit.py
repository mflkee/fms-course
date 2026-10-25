"""Репозиторий журнала аудита: только добавление, без изменения и удаления."""

from __future__ import annotations

from datetime import datetime

from app.entity.audit import AuditEvent
from app.repository.base import InMemoryRepository


class AuditRepository(InMemoryRepository[AuditEvent]):
    entity_name = "событие аудита"

    def record(
        self,
        *,
        at: datetime,
        actor: str,
        action: str,
        outcome: str = "success",
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            at=at,
            actor=actor,
            action=action,
            outcome=outcome,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        return self.add(event)

    def latest(self, limit: int = 50) -> list[AuditEvent]:
        events = sorted(self.all(), key=lambda event: event.at)
        return events[-limit:][::-1]
