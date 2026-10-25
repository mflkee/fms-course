"""Экран патента (boundary): операции 1, 2, 3, 9, 13."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import (
    NonpaymentTerminationRequest,
    PatentArchiveRequest,
    PatentCreateRequest,
    RecalculateRequest,
)
from app.container import Container
from app.entity.enums import Role
from app.entity.user import User

router = APIRouter(prefix="/patents", tags=["patents"])


def _require_read_access(container: Container, actor: User, patent) -> None:
    container.access.require_role(actor, Role.CITIZEN, Role.EMPLOYER_REP, Role.ADMIN)
    if actor.role is Role.CITIZEN:
        container.access.ensure_citizen_owns(actor, patent.citizen_id)


def _require_owner_access(container: Container, actor: User, patent) -> None:
    container.access.require_role(actor, Role.CITIZEN, Role.ADMIN)
    if actor.role is Role.CITIZEN:
        container.access.ensure_citizen_owns(actor, patent.citizen_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def register_patent(
    payload: PatentCreateRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 1. ``зарегистрироватьПатент``."""
    result = container.patent_service.register(
        citizen_id=payload.citizen_id,
        series=payload.series,
        number=payload.number,
        issue_date=payload.issue_date,
        region_code=payload.region_code,
        activity_codes=payload.activity_codes,
        issuing_authority=payload.issuing_authority,
        valid_until=payload.valid_until,
        scan=payload.scan.model_dump() if payload.scan else None,
        previous_patent_id=payload.previous_patent_id,
        actor=actor,
    )
    return result.to_dict()


@router.get("/by-requisites")
def get_patent_by_requisites(
    series: str = Query(min_length=1),
    number: str = Query(min_length=1),
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 3 (вариант поиска): сведения о патенте по серии и номеру."""
    return container.patent_service.find_by_requisites(series, number, actor=actor)


@router.get("/{patent_id}")
def get_patent(
    patent_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 3. ``получитьСведенияОпатенте``."""
    return container.patent_service.get_details(patent_id, actor=actor)


@router.post("/{patent_id}/archive")
def archive_patent(
    patent_id: str,
    payload: PatentArchiveRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 2. ``пометитьПатентАрхивным``."""
    return container.patent_service.archive(
        patent_id=patent_id,
        basis=payload.basis,
        reason=payload.reason,
        actor=actor,
    )


@router.get("/{patent_id}/deadline-points")
def list_deadline_points(
    patent_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Контрольные точки патента (чтение для экранов П04)."""
    patent = container.patents.require(patent_id)
    _require_read_access(container, actor, patent)
    points = container.deadline_service.points_for_patent(patent)
    return {
        "patent_id": patent.id,
        "employment_deadline": patent.employment_deadline.isoformat(),
        "points": [point.to_dict() for point in points],
        "summary": container.deadline_service.summary(patent).to_dict(),
    }


@router.post("/{patent_id}/recalculate")
def recalculate_deadlines(
    patent_id: str,
    payload: RecalculateRequest | None = None,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 9. ``пересчитатьСрокиПатента``."""
    patent = container.patents.require(patent_id)
    _require_owner_access(container, actor, patent)
    reason = payload.reason if payload and payload.reason else "пересчёт по запросу"
    summary = container.deadline_service.recalculate(
        patent, reason=reason, actor=actor.login
    )
    return {"summary": summary.to_dict(), "reason": reason}


@router.post("/{patent_id}/terminate-nonpayment")
def terminate_nonpayment(
    patent_id: str,
    payload: NonpaymentTerminationRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 13. ``зафиксироватьПрекращениеПатентаНеуплата``."""
    return container.tax_service.terminate_nonpayment(
        patent_id=patent_id, detected_at=payload.detected_at, actor=actor
    )
