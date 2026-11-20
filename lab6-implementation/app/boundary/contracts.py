"""Экран договора (``ЭкранДоговора``): операции 4 и 5."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.boundary.deps import get_container
from app.boundary.schemas import ContractCancelRequest, ContractCreateRequest
from app.container import Container

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", status_code=status.HTTP_201_CREATED)
def conclude_contract(
    payload: ContractCreateRequest,
    container: Container = Depends(get_container),
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
    )
    return result.to_dict()


@router.get("/{contract_id}")
def get_contract(
    contract_id: str,
    container: Container = Depends(get_container),
) -> dict:
    """Карточка договора с историей уведомлений."""
    return container.contract_service.get(contract_id)


@router.post("/{contract_id}/cancel")
def cancel_contract(
    contract_id: str,
    payload: ContractCancelRequest,
    container: Container = Depends(get_container),
) -> dict:
    """Операция 5. ``отменитьДоговор``."""
    return container.contract_service.cancel(
        contract_id=contract_id, reason=payload.reason
    )
