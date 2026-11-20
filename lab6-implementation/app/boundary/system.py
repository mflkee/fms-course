"""Служебные экраны: здоровье приложения и справочники."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.boundary.deps import get_container
from app.container import Container

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
            "deadline_points": container.points.count(),
            "reminders": container.reminders.count(),
        },
        "gateways_failing": sorted(container.policy.failing),
    }


@router.get("/catalog/regions")
def list_regions(container: Container = Depends(get_container)) -> list[dict]:
    return [region.to_dict() for region in container.regions.all()]


@router.get("/catalog/activities")
def list_activities(container: Container = Depends(get_container)) -> list[dict]:
    return [activity.to_dict() for activity in container.activities.all()]


@router.get("/catalog/offices")
def list_offices(container: Container = Depends(get_container)) -> list[dict]:
    return [office.to_dict() for office in container.offices.all()]


@router.get("/catalog/citizens")
def list_citizens(container: Container = Depends(get_container)) -> list[dict]:
    """Служебное чтение для демо-сценария: кто есть в учёте."""
    return [citizen.to_public_dict() for citizen in container.citizens.all()]


@router.get("/catalog/employers")
def list_employers(container: Container = Depends(get_container)) -> list[dict]:
    """Служебное чтение для демо-сценария: кто есть в учёте."""
    return [employer.to_dict() for employer in container.employers.all()]
