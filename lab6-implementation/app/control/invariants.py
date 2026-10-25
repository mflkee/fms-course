"""Инварианты предметной области ИНВ-1…ИНВ-9 — в одном месте.

Правило живёт здесь, а не в HTTP-обработчике: его нельзя обойти, вызвав
сервис напрямую (тесты так и делают). Каждая проверка либо блокирует
операцию (409/422), либо возвращает признак нарушения, которое операция
обязана зафиксировать — это осознанное различие, см. README.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.entity.contract import Contract
from app.entity.enums import ContractStatus
from app.entity.money import money, money_str, shortfall
from app.entity.patent import Patent
from app.errors import ConflictError, ValidationFailure


# --- ИНВ-1: не более одного действующего договора на патент -------------
def ensure_no_active_contract(active: Contract | None, patent: Patent) -> None:
    if active is not None:
        raise ConflictError(
            "по патенту уже есть действующий договор: сначала прекратите его "
            "(операция 14), затем заключайте новый",
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


# --- ИНВ-5: непрерывность уплаты НДФЛ -----------------------------------
@dataclass(kw_only=True)
class ContinuityCheck:
    outcome: str  # "next" | "already_paid"
    expected_period: str


def ensure_payment_continuity(patent: Patent, period: str) -> ContinuityCheck:
    expected = patent.next_uncovered_period()
    if period == expected:
        return ContinuityCheck(outcome="next", expected_period=expected)
    if period < expected:
        return ContinuityCheck(outcome="already_paid", expected_period=expected)
    raise ConflictError(
        "нарушена непрерывность уплаты НДФЛ: пропущен период "
        f"{expected}; перерыв не восстанавливается задним числом",
        code="INV-5",
        details={"expected_period": expected, "requested_period": period},
    )


# --- ИНВ-6: не более одного действующего патента у ИГ --------------------
def ensure_single_current_patent(existing: Patent | None) -> None:
    if existing is not None:
        raise ConflictError(
            "у иностранного гражданина уже есть действующий патент: "
            "сначала пометьте его архивным (операция 2)",
            code="INV-6",
            details={
                "existing_patent_id": existing.id,
                "existing_series": existing.series,
                "existing_number": existing.number,
            },
        )


def ensure_patent_is_current(patent: Patent, operation: str) -> None:
    if not patent.is_current():
        raise ConflictError(
            f"патент не действует (статус «{patent.status.value}»), операция «{operation}» невозможна",
            code="PATENT_NOT_CURRENT",
            details={"patent_id": patent.id, "status": patent.status.value},
        )


# --- ИНВ-7: сумма платежа равна стоимости патента в регионе --------------
def ensure_payment_amount(expected: Decimal, received: Decimal) -> None:
    expected = money(expected)
    received = money(received)
    if received != expected:
        missing = shortfall(expected, received)
        raise ValidationFailure(
            "сумма платежа не соответствует стоимости патента в регионе на дату платежа",
            code="INV-7",
            details={
                "expected": money_str(expected),
                "received": money_str(received),
                "shortfall": money_str(missing),
                "excess": money_str(received - expected) if received > expected else None,
            },
        )


# --- ИНВ-8: доказательства не удаляются ---------------------------------
def ensure_contract_allows_termination(contract: Contract) -> None:
    if not contract.is_active():
        raise ConflictError(
            f"договор в статусе «{contract.status.value}» нельзя прекратить",
            code="CONTRACT_NOT_ACTIVE",
            details={"contract_id": contract.id, "status": contract.status.value},
        )


def ensure_contract_is_draft(contract: Contract) -> None:
    if contract.status is not ContractStatus.DRAFT:
        raise ConflictError(
            "отменить можно только черновик договора; для действующего "
            "договора применяется операция 14 «прекратить договор»",
            code="CONTRACT_NOT_DRAFT",
            details={"contract_id": contract.id, "status": contract.status.value},
        )
