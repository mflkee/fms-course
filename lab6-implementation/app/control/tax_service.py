"""Сервис НДФЛ (лаб. 5, ``СервисНДФЛ``), операции 11–13.

ИНВ-7 — сумма сверяется со стоимостью патента в регионе на дату платежа;
ИНВ-5 — периоды идут подряд, перерыв не восстанавливается задним числом.
Подтверждение из ФНС автоматическое, подтверждение по документу — всегда
помечается как ручной ввод.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.control.access_service import AccessService
from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    ensure_patent_is_current,
    ensure_payment_amount,
    ensure_payment_continuity,
)
from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.contract import Contract
from app.entity.deadline import DeadlinePoint
from app.entity.documents import Document
from app.entity.enums import (
    DocumentType,
    PaymentInputSource,
    PaymentStatus,
    PointKind,
    Role,
)
from app.entity.patent import Patent
from app.entity.payment import TaxPayment
from app.entity.periods import parse_period, period_end, period_of
from app.entity.user import User
from app.errors import ConflictError, GatewayError, ValidationFailure
from app.gateway.base import FailurePolicy
from app.gateway.fns import FnsGateway
from app.repository.audit import AuditRepository
from app.repository.catalogs import RegionRepository
from app.repository.contracts import ContractRepository
from app.repository.documents import DocumentRepository
from app.repository.patents import PatentRepository
from app.repository.payments import PaymentRepository
from app.repository.people import CitizenRepository


@dataclass(kw_only=True)
class PaymentResult:
    payment: TaxPayment
    patent: Patent
    confirmed: bool
    deadline_point: DeadlinePoint | None
    idempotent: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "payment": self.payment.to_dict(),
            "patent": self.patent.to_dict(),
            "confirmed": self.confirmed,
            "deadline_point": self.deadline_point.to_dict() if self.deadline_point else None,
            "idempotent": self.idempotent,
            "notes": self.notes,
        }


class TaxService:
    def __init__(
        self,
        payments: PaymentRepository,
        patents: PatentRepository,
        contracts: ContractRepository,
        regions: RegionRepository,
        documents: DocumentRepository,
        deadlines: DeadlineService,
        reminders: ReminderService,
        citizens: CitizenRepository,
        fns: FnsGateway,
        policy: FailurePolicy,
        access: AccessService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._payments = payments
        self._patents = patents
        self._contracts = contracts
        self._regions = regions
        self._documents = documents
        self._deadlines = deadlines
        self._reminders = reminders
        self._citizens = citizens
        self._fns = fns
        self._policy = policy
        self._access = access
        self._clock = clock
        self._audit = audit

    # --- операция 11: зарегистрировать платёж НДФЛ ------------------------
    def register_payment(
        self,
        *,
        patent_id: str,
        period: str,
        amount: Decimal,
        payment_date: date,
        document_number: str,
        document: dict | None,
        fns_status: str | None = None,
        simulate_failure: bool | None = None,
        actor: User | None,
    ) -> PaymentResult:
        self._access.require_citizen(actor)
        assert actor is not None
        patent = self._patents.require(patent_id)
        if actor.role is Role.CITIZEN:
            self._access.ensure_citizen_owns(actor, patent.citizen_id)
        ensure_patent_is_current(patent, "зарегистрировать платёж НДФЛ")

        self._validate_period(patent, period)
        today = self._clock.today()
        if payment_date > today:
            raise ValidationFailure(
                "дата платежа не может быть в будущем", code="DATE_IN_FUTURE"
            )
        if payment_date < patent.issue_date:
            raise ValidationFailure(
                "дата платежа не может быть раньше даты выдачи патента",
                code="PAYMENT_BEFORE_PATENT",
            )
        expected = self._regions.cost_on(patent.region_code, payment_date)

        existing = self._payments.confirmed_by_period(patent.id, period)
        if existing is not None:
            # идемпотентность: повторный вызов возвращает тот же результат
            return PaymentResult(
                payment=existing,
                patent=patent,
                confirmed=True,
                deadline_point=self._deadlines.latest_point(
                    patent.id, PointKind.PAY_NDFL
                ),
                idempotent=True,
                notes=["Период уже оплачен: возвращён ранее подтверждённый платёж."],
            )
        pending = self._payments.by_period(patent.id, period)
        if pending is not None:
            raise ConflictError(
                "платёж за этот период уже зарегистрирован, но не подтверждён: "
                "воспользуйтесь операцией 12",
                code="PAYMENT_ALREADY_REGISTERED",
                details={"payment_id": pending.id, "status": pending.status.value},
            )

        continuity = ensure_payment_continuity(patent, period)
        if continuity.outcome == "already_paid":
            raise ConflictError(
                "период уже покрыт подтверждённым платежом",
                code="INV-5",
                details={"period": period, "expected_period": continuity.expected_period},
            )
        if document is None or not document.get("filename"):
            raise ValidationFailure(
                "приложите чек или платёжное поручение", code="PAYMENT_DOCUMENT_REQUIRED"
            )
        ensure_payment_amount(expected, amount)

        payment = TaxPayment(
            patent_id=patent.id,
            period=period,
            amount=amount,
            payment_date=payment_date,
            document_number=document_number,
            expected_amount=expected,
            created_at=self._clock.now(),
        )
        self._payments.add(payment)
        saved_document = self._attach_document(payment, document)

        try:
            check = self._fns.check_payment(
                inn=self._inn_of(patent),
                period=period,
                amount=amount,
                on_date=payment_date,
                simulate_status=fns_status,
                simulate_failure=simulate_failure,
            )
        except GatewayError as exc:
            payment.mark_not_found(f"ФНС недоступна: {exc.message}")
            payment.document_id = saved_document.id
            self._audit.record(
                at=self._clock.now(),
                actor=actor.login,
                action="register_payment_failed",
                outcome="failure",
                entity_type="payment",
                entity_id=payment.id,
                details={"gateway": "fns", "error": exc.message},
            )
            raise GatewayError(
                exc.message,
                code=exc.code,
                details={
                    **exc.details,
                    "payment_id": payment.id,
                    "payment_status": payment.status.value,
                    "next_operation": "POST /payments/{id}/confirm",
                },
            ) from exc

        if not check.found:
            if fns_status == "returned":
                payment.mark_returned(check.detail)
            else:
                payment.mark_not_found(check.detail)
            self._audit.record(
                at=self._clock.now(),
                actor=actor.login,
                action="register_payment_not_found",
                outcome="failure",
                entity_type="payment",
                entity_id=payment.id,
                details={"period": period, "detail": check.detail},
            )
            return PaymentResult(
                payment=payment,
                patent=patent,
                confirmed=False,
                deadline_point=None,
                notes=[
                    "Платёж не найден в ФНС: период не признаётся оплаченным.",
                    "Подтвердите платёж по документу (операция 12).",
                ],
            )

        payment.confirm(
            source=PaymentInputSource.FNS.value,
            document_id=saved_document.id,
            confirmed_at=self._clock.now(),
            manual=False,
        )
        point = self._apply_confirmation(payment, patent, actor.login)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="register_payment",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "period": period,
                "amount": str(payment.amount),
                "source": payment.input_source,
            },
        )
        return PaymentResult(
            payment=payment,
            patent=patent,
            confirmed=True,
            deadline_point=point,
            notes=[
                "Платёж подтверждён по данным ФНС; оплаченный период обновлён.",
                "Работодателю сообщается только факт «оплачен до», без суммы.",
            ],
        )

    # --- операция 12: подтвердить платёж ----------------------------------
    def confirm_payment(
        self,
        *,
        payment_id: str,
        source: PaymentInputSource,
        document: dict | None,
        actor: User | None,
    ) -> PaymentResult:
        self._access.require_citizen(actor)
        assert actor is not None
        payment = self._payments.require(payment_id)
        patent = self._patents.require(payment.patent_id)
        if actor.role is Role.CITIZEN:
            self._access.ensure_citizen_owns(actor, patent.citizen_id)
        if payment.status is PaymentStatus.CONFIRMED:
            raise ConflictError(
                "платёж уже подтверждён",
                code="PAYMENT_ALREADY_CONFIRMED",
                details={"payment_id": payment.id},
            )
        if document is None or not document.get("filename"):
            raise ValidationFailure(
                "приложите документ, подтверждающий платёж",
                code="PAYMENT_DOCUMENT_REQUIRED",
            )

        expected = self._regions.cost_on(patent.region_code, payment.payment_date)
        if payment.amount != expected:
            payment.mark_insufficient(expected)
            raise ValidationFailure(
                "сумма платежа меньше стоимости патента: требуется доплата",
                code="INV-7",
                details={
                    "expected": str(expected),
                    "received": str(payment.amount),
                    "shortfall": str(payment.shortfall_amount),
                },
            )
        continuity = ensure_payment_continuity(patent, payment.period)
        if continuity.outcome == "already_paid":
            raise ConflictError(
                "период уже покрыт другим подтверждённым платежом",
                code="INV-5",
                details={"expected_period": continuity.expected_period},
            )

        saved_document = self._attach_document(payment, document)
        payment.confirm(
            source=source.value,
            document_id=saved_document.id,
            confirmed_at=self._clock.now(),
            manual=True,
        )
        point = self._apply_confirmation(payment, patent, actor.login)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="confirm_payment_manually",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "period": payment.period,
                "source": source.value,
                "manual": True,
                "document_id": saved_document.id,
            },
        )
        return PaymentResult(
            payment=payment,
            patent=patent,
            confirmed=True,
            deadline_point=point,
            notes=[
                "Платёж подтверждён вручную по документу; признак ручного ввода сохранён.",
                "Непрерывность оплаты восстановлена (ИНВ-5).",
            ],
        )

    # --- операция 13: прекращение патента из-за неуплаты -------------------
    def terminate_nonpayment(
        self,
        *,
        patent_id: str,
        detected_at: date,
        actor: User | None,
    ) -> dict:
        self._access.require_admin(actor)
        assert actor is not None
        if detected_at > self._clock.today():
            raise ValidationFailure(
                "дата фиксации прекращения не может быть в будущем",
                code="DATE_IN_FUTURE",
                details={"detected_at": detected_at.isoformat()},
            )
        patent = self._patents.require(patent_id)
        ensure_patent_is_current(patent, "зафиксировать прекращение патента из-за неуплаты")
        if not patent.has_paid_period():
            raise ConflictError(
                "патент не был оплачен ни за один период: прекращение из-за неуплаты неприменимо",
                code="NO_PAID_PERIOD",
                details={"patent_id": patent.id},
            )
        if patent.paid_until is not None and patent.paid_until >= patent.valid_until:
            raise ConflictError(
                "патент оплачен до конца срока действия: прекращать из-за неуплаты нечего",
                code="PATENT_FULLY_PAID",
            )
        next_period = patent.next_uncovered_period()
        if self._payments.confirmed_by_period(patent.id, next_period) is not None:
            raise ConflictError(
                "платёж за очередной период найден: патент не прекращается, "
                "примените операцию 12",
                code="PAYMENT_FOUND",
                details={"period": next_period},
            )
        if patent.paid_until is not None and detected_at <= patent.paid_until:
            raise ValidationFailure(
                "оплаченный период ещё не истёк: прекращение преждевременно",
                code="PAYMENT_PERIOD_NOT_EXPIRED",
                details={"paid_until": patent.paid_until.isoformat()},
            )

        check = self._fns.confirm_absence(
            inn=self._inn_of(patent), period=next_period, on_date=detected_at
        )
        if check.found:
            raise ConflictError(
                "ФНС подтвердила наличие платежа: патент не прекращается",
                code="PAYMENT_FOUND",
                details={"period": next_period},
            )

        patent.terminate_nonpayment(detected_at)
        cancelled_points = self._deadlines.cancel_all(
            patent, "прекращение патента (неуплата)"
        )
        cancelled_reminders = self._reminders.cancel_for_patent(patent.id)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="terminate_patent_nonpayment",
            entity_type="patent",
            entity_id=patent.id,
            details={
                "detected_at": detected_at.isoformat(),
                "paid_until": patent.paid_until.isoformat() if patent.paid_until else None,
                "fns": check.detail,
            },
        )
        return {
            "patent": patent.to_dict(),
            "cancelled_deadline_points": cancelled_points,
            "cancelled_reminders": cancelled_reminders,
            "fns_confirmation": check.to_dict(),
            "notices": [
                {
                    "recipient": "citizen",
                    "text": "Патент прекращён из-за неуплаты НДФЛ: необходимо покинуть РФ "
                    "или оформить иной статус.",
                },
                {
                    "recipient": "employer",
                    "text": "Использование патента невозможно: действие прекращено из-за неуплаты.",
                },
            ],
        }

    # --- вспомогательное --------------------------------------------------
    def _validate_period(self, patent: Patent, period: str) -> None:
        try:
            parse_period(period)
        except ValueError as exc:
            raise ValidationFailure(str(exc), code="PERIOD_INVALID") from exc
        if not patent.period_is_within_term(period):
            raise ValidationFailure(
                "период платежа выходит за срок действия патента",
                code="PERIOD_OUT_OF_TERM",
                details={
                    "period": period,
                    "issue_period": period_of(patent.issue_date),
                    "valid_until": patent.valid_until.isoformat(),
                },
            )

    def _apply_confirmation(
        self, payment: TaxPayment, patent: Patent, actor_login: str
    ) -> DeadlinePoint | None:
        patent.mark_paid_until(period_end(payment.period))
        point = self._deadlines.close_point(
            patent, PointKind.PAY_NDFL, payment.payment_date
        )
        if (
            patent.paid_until is not None
            and patent.paid_until < patent.valid_until
            and period_of(patent.paid_until) < period_of(patent.valid_until)
        ):
            self._deadlines.open_point(patent, PointKind.PAY_NDFL)
        self._reminders.schedule_for_patent(patent)
        try:
            self._fns.transfer_payment(payment)
        except GatewayError as exc:  # передача сведений не отменяет подтверждение
            self._audit.record(
                at=self._clock.now(),
                actor=actor_login,
                action="fns_transfer_failed",
                outcome="failure",
                entity_type="payment",
                entity_id=payment.id,
                details={"error": exc.message},
            )
        return point

    def _attach_document(self, payment: TaxPayment, payload: dict) -> Document:
        document = Document.create(
            doc_type=DocumentType.PAYMENT_RECEIPT,
            filename=payload["filename"],
            owner_type="payment",
            owner_id=payment.id,
            content_hash=payload.get("hash"),
            source=payload.get("source", "manual_upload"),
            uploaded_at=self._clock.now(),
        )
        return self._documents.add(document)

    def _inn_of(self, patent: Patent) -> str:
        citizen = self._citizens.find(patent.citizen_id)
        return citizen.inn if citizen else ""

    def get(self, payment_id: str, *, actor: User | None) -> dict:
        self._access.require_role(actor, Role.CITIZEN, Role.ADMIN)
        assert actor is not None
        payment = self._payments.require(payment_id)
        patent = self._patents.require(payment.patent_id)
        if actor.role is Role.CITIZEN:
            self._access.ensure_citizen_owns(actor, patent.citizen_id)
        return {
            "payment": payment.to_dict(),
            "patent": patent.to_dict(),
            "documents": [
                document.to_dict()
                for document in self._documents.by_owner("payment", payment.id)
            ],
        }

    def failure_policy(self) -> FailurePolicy:
        return self._policy

    def active_contract(self, patent: Patent) -> Contract | None:
        return self._contracts.active_by_patent(patent.id)
