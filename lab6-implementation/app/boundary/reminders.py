"""Экран напоминаний (boundary): операция 8."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import ReminderSettingsRequest
from app.container import Container
from app.entity.enums import Role
from app.entity.user import CitizenUser, User
from app.errors import ForbiddenError, ValidationFailure

router = APIRouter(tags=["reminders"])


@router.put("/reminder-settings")
def configure_reminders(
    payload: ReminderSettingsRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 8. ``настроитьНапоминания``."""
    container.access.require_citizen(actor)
    profile = (
        container.users.require(payload.profile_id)
        if payload.profile_id
        else actor
    )
    if not isinstance(profile, CitizenUser):
        raise ValidationFailure(
            "настройки напоминаний принадлежат профилю иностранного гражданина",
            code="PROFILE_INVALID",
            details={"profile_id": profile.id},
        )
    if actor.role is Role.CITIZEN and profile.id != actor.id:
        raise ForbiddenError(
            "настройка напоминаний доступна только для своего профиля",
            code="FORBIDDEN",
        )
    if not profile.active:
        raise ValidationFailure(
            "профиль заблокирован: настройка напоминаний недоступна",
            code="PROFILE_BLOCKED",
        )

    plan = container.reminder_service.configure(
        profile=profile,
        channels=payload.channels,
        days=payload.days,
        consent=payload.consent,
    )
    return {
        "profile_id": profile.id,
        "settings": plan.settings.to_dict(),
        "reminders_created": [reminder.to_dict() for reminder in plan.created],
        "reminders_count": len(plan.created),
        "skipped_closed_points": plan.skipped_closed,
        "notes": [
            "Напоминания созданы только по открытым контрольным точкам (ИНВ-9).",
        ],
    }
