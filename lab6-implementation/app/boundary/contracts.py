"""Экран договора (boundary): операции 4, 5, 14."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import (
    ContractCancelRequest,
    ContractCreateRequest,
    ContractTerminateRequest,
)
from app.container import Container
from app.entity.user import User

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", status_code=status.HTTP_201_CREATED)
def conclude_contract(
    payload: ContractCreateRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 4. ``заключитьДоговор``."""
    result = container.contract_service.conclude(
        patent_id=payload.patent_id,
        employer_id=payload.employer_id,
        activity_code=payload.activity_code,
        conclusion_date=payload.conclusion_date,
        kind=payload.kind,
        document=payload.document.model_dump() if payload.document else None,
        consent_confirmed=payload.consent_confirmed,
        number=payload.number,
        end_date=payload.end_date,
        position=payload.position,
        work_mode=payload.work_mode,
        subject=payload.subject,
        work_deadline=payload.work_deadline,
        actor=actor,
    )
    return result.to_dict()


@router.get("/{contract_id}")
def get_contract(
    contract_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Карточка договора с историей уведомлений (для экрана П06)."""
    return container.contract_service.get(contract_id, actor=actor)


@router.post("/{contract_id}/cancel")
def cancel_contract(
    contract_id: str,
    payload: ContractCancelRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 5. ``отменитьДоговор``."""
    return container.contract_service.cancel(
        contract_id=contract_id, reason=payload.reason, actor=actor
    )


@router.post("/{contract_id}/terminate")
def terminate_contract(
    contract_id: str,
    payload: ContractTerminateRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 14. ``прекратитьДоговор``."""
    result = container.contract_service.terminate(
        contract_id=contract_id,
        termination_date=payload.termination_date,
        reason=payload.reason,
        document=payload.document.model_dump() if payload.document else None,
        confirm_contradiction=payload.confirm_contradiction,
        actor=actor,
    )
    return result.to_dict()
