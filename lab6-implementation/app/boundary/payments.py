"""Экран платежа НДФЛ (boundary): операции 11 и 12."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import PaymentConfirmRequest, PaymentCreateRequest
from app.container import Container
from app.entity.user import User

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def register_payment(
    payload: PaymentCreateRequest,
    response: Response,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 11. ``зарегистрироватьПлатёжНДФЛ``.

    Если ФНС не находит поступление, платёж сохраняется со статусом
    ``not_found`` и ``confirmed=false`` — период не считается оплаченным.
    Повторный вызов за уже оплаченный период идемпотентен и отвечает 200.
    """
    result = container.tax_service.register_payment(
        patent_id=payload.patent_id,
        period=payload.period,
        amount=payload.amount,
        payment_date=payload.payment_date,
        document_number=payload.document_number,
        document=payload.document.model_dump(),
        fns_status=payload.fns_status,
        simulate_failure=payload.simulate_failure,
        actor=actor,
    )
    if result.idempotent:
        response.status_code = status.HTTP_200_OK
    return result.to_dict()


@router.get("/{payment_id}")
def get_payment(
    payment_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Карточка платежа с документом-основанием."""
    return container.tax_service.get(payment_id, actor=actor)


@router.post("/{payment_id}/confirm")
def confirm_payment(
    payment_id: str,
    payload: PaymentConfirmRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 12. ``подтвердитьПлатёж`` (ручной ввод по документу)."""
    result = container.tax_service.confirm_payment(
        payment_id=payment_id,
        source=payload.source,
        document=payload.document.model_dump(),
        actor=actor,
    )
    return result.to_dict()
