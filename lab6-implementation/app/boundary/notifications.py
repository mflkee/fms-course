"""Экран уведомления МВД (boundary): операции 6 и 7."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.boundary.deps import get_actor, get_container
from app.boundary.schemas import NotificationCreateRequest, NotificationReturnRequest
from app.container import Container
from app.entity.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", status_code=status.HTTP_201_CREATED)
def send_notification(
    payload: NotificationCreateRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 6. ``направитьУведомлениеМВД``.

    При отказе источника (ЕПГУ/Почта) возвращается 502, уведомление сохраняется
    в статусе ``error`` — задачу закрывает операция 7.
    """
    result = container.notification_service.send(
        contract_id=payload.contract_id,
        channel=payload.channel,
        confirmation=(
            payload.confirmation.model_dump() if payload.confirmation else None
        ),
        allow_overdue=payload.allow_overdue,
        simulate_failure=payload.simulate_failure,
        actor=actor,
    )
    return result.to_dict()


@router.get("/{notification_id}")
def get_notification(
    notification_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Карточка уведомления и его доказательств (ИНВ-8)."""
    return container.notification_service.get(notification_id, actor=actor)


@router.post("/{notification_id}/return")
def register_return(
    notification_id: str,
    payload: NotificationReturnRequest,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 7. ``зафиксироватьВозвратУведомления``."""
    return container.notification_service.register_return(
        notification_id=notification_id,
        reason=payload.reason,
        document=payload.document.model_dump() if payload.document else None,
        actor=actor,
    )
