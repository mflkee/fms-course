"""Инварианты предметной области ИНВ-1…ИНВ-7 — в одном месте.

Нумерация совпадает с DESIGN.md (раздел 5). Правило живёт здесь, а не в
HTTP-обработчике: его нельзя обойти, вызвав сервис напрямую (тесты так и
делают). Каждая проверка либо блокирует операцию (409/422), либо возвращает
признак нарушения, которое операция обязана зафиксировать, — это осознанное
различие, см. README.
"""

from __future__ import annotations

from datetime import date

from app.entity.contract import Contract
from app.entity.notification import Notification
from app.entity.patent import Patent
from app.errors import ConflictError, ValidationFailure

SENT_NOTIFICATION_STATUSES = {"sent", "overdue", "delivered"}


# --- ИНВ-1: не более одного действующего договора на патент -------------
def ensure_no_active_contract(active: Contract | None, patent: Patent) -> None:
    if active is not None:
        raise ConflictError(
            "по патенту уже есть действующий договор: сначала отмените его "
            "(операция 5), затем заключайте новый",
            code="INV-1",
            details={
                "patent_id": patent.id,
                "active_contract_id": active.id,
                "active_contract_number": active.number,
            },
        )


# --- ИНВ-2: уведомление не ранее договора -------------------------------
def ensure_notification_not_before_contract(
    notification_date: date, contract: Contract
) -> None:
    if notification_date < contract.conclusion_date:
        raise ValidationFailure(
            "уведомление МВД не может быть направлено раньше даты заключения договора",
            code="INV-2",
            details={
                "notification_date": notification_date.isoformat(),
                "contract_conclusion_date": contract.conclusion_date.isoformat(),
            },
        )


def notification_is_late(patent: Patent, notification_date: date) -> bool:
    """Нарушение срока «не позднее 2 месяцев с даты выдачи» (фиксируется, не блокирует)."""
    return notification_date > patent.employment_deadline


# --- ИНВ-3: договор не позднее 2 месяцев с даты выдачи -------------------
def contract_is_late(patent: Patent, conclusion_date: date) -> bool:
    return conclusion_date > patent.employment_deadline


# --- ИНВ-4: профессия входит в перечень патента -------------------------
def ensure_activity_allowed(patent: Patent, activity_code: str) -> None:
    if not patent.allows_activity(activity_code):
        raise ValidationFailure(
            "вид деятельности по договору не входит в перечень, указанный в патенте",
            code="INV-4",
            details={
                "activity_code": activity_code,
                "patent_activities": list(patent.activity_codes),
            },
        )


# --- ИНВ-5: не более одного действующего патента у ИГ --------------------
def ensure_single_current_patent(existing: Patent | None) -> None:
    if existing is not None:
        raise ConflictError(
            "у иностранного гражданина уже есть действующий патент: "
            "сначала пометьте его архивным (операция 2)",
            code="INV-5",
            details={
                "existing_patent_id": existing.id,
                "existing_series": existing.series,
                "existing_number": existing.number,
            },
        )


# --- ИНВ-7: смена работодателя требует нового уведомления ----------------
def ensure_notification_not_repeated(history: list[Notification]) -> None:
    """По одному договору уведомление направляется один раз.

    Новый работодатель — это новый договор и, следовательно, новое
    уведомление; повтор по тому же договору запрещён.
    """
    successful = [
        item for item in history if item.status.value in SENT_NOTIFICATION_STATUSES
    ]
    if successful:
        raise ConflictError(
            "по договору уже направлено уведомление МВД: повторная отправка "
            "невозможна; при смене работодателя заключается новый договор и "
            "направляется новое уведомление",
            code="INV-7",
            details={
                "notification_id": successful[-1].id,
                "contract_id": successful[-1].contract_id,
            },
        )


# --- проверки состояния (не входят в список инвариантов модели) ----------
def ensure_patent_is_current(patent: Patent, operation: str) -> None:
    if not patent.is_current():
        raise ConflictError(
            f"патент не действует (статус «{patent.status.value}»), операция «{operation}» невозможна",
            code="PATENT_NOT_CURRENT",
            details={"patent_id": patent.id, "status": patent.status.value},
        )

