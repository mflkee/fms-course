"""Служебные экраны: здоровье, справочники, пользователи, аудит, планировщик."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.boundary.deps import get_actor, get_container
from app.container import Container
from app.entity.enums import Role
from app.entity.user import User

router = APIRouter(tags=["system"])


@router.get("/health")
def health(container: Container = Depends(get_container)) -> dict:
    return {
        "status": "ok",
        "today": container.clock.today().isoformat(),
        "counts": {
            "patents": container.patents.count(),
            "contracts": container.contracts.count(),
            "notifications": container.notifications.count(),
            "payments": container.payments.count(),
            "deadline_points": container.points.count(),
            "reminders": container.reminders.count(),
            "reports": container.reports.count(),
        },
        "gateways_failing": sorted(container.policy.failing),
    }


@router.get("/catalog/regions")
def list_regions(container: Container = Depends(get_container)) -> list[dict]:
    return [region.to_dict() for region in container.regions.all()]


@router.get("/catalog/activities")
def list_activities(container: Container = Depends(get_container)) -> list[dict]:
    return [activity.to_dict() for activity in container.activities.all()]


@router.get("/users")
def list_users(
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> list[dict]:
    container.access.require_admin(actor)
    return [user.to_dict() for user in container.users.all()]


@router.get("/audit-events")
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=500),
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> list[dict]:
    container.access.require_admin(actor)
    return [event.to_dict() for event in container.audit.latest(limit)]


@router.post("/scheduler/daily-run")
def run_daily_control(
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    container.access.require_role(actor, Role.ADMIN)
    result = container.scheduler.run_daily_control(actor=actor.login)
    payload = result.to_dict()
    payload["suggested_nonpayment_patents"] = [
        patent.to_dict() for patent in container.scheduler.candidate_patents_for_nonpayment()
    ]
    return payload
