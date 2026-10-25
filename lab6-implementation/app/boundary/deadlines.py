"""Экран контроля сроков (boundary): операция 10."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import ViolationRequest
from app.container import Container
from app.entity.enums import Role
from app.entity.user import User

router = APIRouter(prefix="/deadline-points", tags=["deadlines"])


@router.post("/{point_id}/violation")
def register_violation(
    point_id: str,
    payload: ViolationRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 10. ``зафиксироватьНарушениеСрока``."""
    container.access.require_role(actor, Role.ADMIN, Role.CITIZEN)
    point = container.points.require(point_id)
    patent = container.patents.require(point.patent_id)
    if actor.role is Role.CITIZEN:
        container.access.ensure_citizen_owns(actor, patent.citizen_id)
    point, reminder = container.deadline_service.register_violation(
        point_id, payload.detected_at, actor=actor.login
    )
    return {
        "deadline_point": point.to_dict(),
        "escalation_reminder": reminder.to_dict(),
        "notes": [
            "Нарушение срока зафиксировано как юридически значимое событие.",
            "Запись критическая и видна в реестре без дополнительной фильтрации.",
        ],
    }
