"""Экран сроков (``ЭкранСроков``): операция 8 и чтение напоминаний кабинета."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.boundary.deps import get_container
from app.boundary.schemas import ReminderSettingsRequest
from app.container import Container

router = APIRouter(tags=["reminders"])


@router.get("/reminders/due")
def list_due_reminders(
    citizen_id: str = Query(min_length=1),
    container: Container = Depends(get_container),
) -> dict:
    """Актуальные напоминания для личного кабинета.

    Напоминания не рассылаются. Запланированные напоминания, момент которых
    наступил, помечаются «показано»; уже показанные возвращаются повторно, пока
    точка открыта. Запрос меняет статус, но повторный вызов безопасен.
    """
    citizen = container.citizens.require(citizen_id)
    reminders = container.reminder_service.show_due(citizen)
    return {
        "citizen_id": citizen.id,
        "today": container.clock.today().isoformat(),
        "count": len(reminders),
        "reminders": [reminder.to_dict() for reminder in reminders],
        "notes": [
            "Напоминание показано в личном кабинете; рассылки по email, SMS или ЕПГУ нет.",
        ],
    }


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
