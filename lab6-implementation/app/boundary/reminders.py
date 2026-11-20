"""Экран сроков (``ЭкранСроков``): операция 8 ``настроитьНапоминания``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.boundary.deps import get_container
from app.boundary.schemas import ReminderSettingsRequest
from app.container import Container

router = APIRouter(tags=["reminders"])


@router.put("/reminder-settings")
def configure_reminders(
    payload: ReminderSettingsRequest,
    container: Container = Depends(get_container),
) -> dict:
    """Операция 8. ``настроитьНапоминания``."""
    citizen = container.citizens.require(payload.citizen_id)
    plan = container.reminder_service.configure(
        citizen=citizen,
        channels=payload.channels,
        days=payload.days,
        consent=payload.consent,
    )
    return {
        "citizen_id": citizen.id,
        "settings": plan.settings.to_dict(),
        "reminders_created": [reminder.to_dict() for reminder in plan.created],
        "reminders_count": len(plan.created),
        "skipped_closed_points": plan.skipped_closed,
        "notes": [
            "Напоминания созданы только по открытым контрольным точкам (ИНВ-6).",
        ],
    }
