"""Экран сроков (``ЭкранСроков``): операция 10 ``зафиксироватьНарушениеСрока``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.boundary.deps import get_container
from app.boundary.schemas import ViolationRequest
from app.container import Container

router = APIRouter(prefix="/deadline-points", tags=["deadlines"])


@router.post("/{point_id}/violation")
def register_violation(
    point_id: str,
    payload: ViolationRequest,
    container: Container = Depends(get_container),
) -> dict:
    """Операция 10. ``зафиксироватьНарушениеСрока``."""
    point, reminder = container.deadline_service.register_violation(
        point_id, payload.detected_at
    )
    return {
        "deadline_point": point.to_dict(),
        "escalation_reminder": reminder.to_dict(),
        "notes": [
            "Нарушение срока зафиксировано как юридически значимое событие.",
            "Запись критическая и видна без дополнительной фильтрации.",
        ],
    }
