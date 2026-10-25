"""Сервис уведомлений МВД (лаб. 5, ``СервисУведомлений``), операции 6 и 7.

Канал — параметр, а не отдельный класс: проект уведомления формируется один
раз, различается только шлюз доставки. Доказательства (квитанция ЕПГУ,
трек-номер и опись почты) сохраняются навсегда (ИНВ-8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.control.access_service import AccessService
from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    ensure_notification_not_before_contract,
    ensure_patent_is_current,
    notification_is_late,
)
from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.contract import Contract
from app.entity.deadline import DeadlinePoint
from app.entity.documents import Document
from app.entity.enums import (
    DocumentType,
    NotificationChannel,
    PointKind,
    Role,
)
from app.entity.notification import Notification
from app.entity.user import User
from app.errors import ConflictError, ForbiddenError, GatewayError, ValidationFailure
from app.gateway.base import FailurePolicy
from app.gateway.epgu import EpguGateway
from app.gateway.post import PostGateway
from app.repository.audit import AuditRepository
from app.repository.catalogs import MvdOfficeRepository
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository
from app.repository.documents import DocumentRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository

MVD_CHANNELS = {NotificationChannel.EPGU, NotificationChannel.POST}


@dataclass(kw_only=True)
class NotificationSendResult:
    notification: Notification
    contract: Contract
    point: DeadlinePoint | None
    evidence: dict
    late: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "notification": self.notification.to_dict(),
            "contract": self.contract.to_dict(),
            "deadline_point": self.point.to_dict() if self.point else None,
            "evidence": self.evidence,
            "late": self.late,
            "notes": self.notes,
        }


class NotificationService:
    def __init__(
        self,
        notifications: NotificationRepository,
        contracts: ContractRepository,
        patents: PatentRepository,
        points: DeadlinePointRepository,
        offices: MvdOfficeRepository,
        documents: DocumentRepository,
        deadlines: DeadlineService,
        reminders: ReminderService,
        epgu: EpguGateway,
        post: PostGateway,
        policy: FailurePolicy,
        access: AccessService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._notifications = notifications
        self._contracts = contracts
        self._patents = patents
        self._points = points
        self._offices = offices
        self._documents = documents
        self._deadlines = deadlines
        self._reminders = reminders
        self._epgu = epgu
        self._post = post
        self._policy = policy
        self._access = access
        self._clock = clock
        self._audit = audit

    # --- операция 6: направить уведомление МВД ----------------------------
    def send(
        self,
        *,
        contract_id: str,
        channel: NotificationChannel,
        confirmation: dict | None = None,
        allow_overdue: bool = False,
        simulate_failure: bool | None = None,
        actor: User | None,
    ) -> NotificationSendResult:
        self._access.require_employer_rep(actor)
        assert actor is not None
        contract = self._contracts.require(contract_id)
        self._ensure_side(contract, actor)
        if channel not in MVD_CHANNELS:
            raise ValidationFailure(
                "уведомление МВД направляется через ЕПГУ или Почту России",
                code="NOTIFICATION_CHANNEL_INVALID",
                details={"allowed": sorted(item.value for item in MVD_CHANNELS)},
            )
        if contract.is_draft():
            raise ConflictError(
                "по черновику договора уведомление не направляется: сначала заключите договор",
                code="CONTRACT_DRAFT",
                details={"contract_id": contract.id},
            )
        if not contract.is_active():
            raise ConflictError(
                f"договор в статусе «{contract.status.value}», уведомление не направляется",
                code="CONTRACT_NOT_ACTIVE",
                details={"contract_id": contract.id, "status": contract.status.value},
            )

        history = self._notifications.history_by_contract(contract.id)
        successful = [
            item
            for item in history
            if item.status.value in {"sent", "overdue", "delivered"}
        ]
        if successful:
            raise ConflictError(
                "по договору уже направлено уведомление МВД: повторная отправка невозможна",
                code="NOTIFICATION_ALREADY_SENT",
                details={"notification_id": successful[-1].id},
            )

        patent = self._patents.require(contract.patent_id)
        ensure_patent_is_current(patent, "направить уведомление МВД")
        send_date, signature, track_number, inventory = self._parse_confirmation(
            channel, confirmation
        )
        ensure_notification_not_before_contract(send_date, contract)

        late = notification_is_late(patent, send_date)
        if late and not allow_overdue:
            raise ValidationFailure(
                "срок направления уведомления МВД истёк: уведомление не может быть "
                "направлено без подтверждения просрочки",
                code="INV-2",
                details={
                    "deadline": patent.employment_deadline.isoformat(),
                    "send_date": send_date.isoformat(),
                    "hint": "повторите запрос с allow_overdue=true, чтобы "
                    "зафиксировать просрочку и отправить уведомление",
                },
            )

        office = self._offices.for_region(patent.region_code)
        notification = Notification(
            contract_id=contract.id,
            channel=channel,
            created_at=self._clock.now(),
        )
        self._notifications.add(notification)

        try:
            receipt = (
                self._epgu.send(
                    notification,
                    signature=signature,
                    signed_at=send_date,
                    simulate_failure=simulate_failure,
                )
                if channel is NotificationChannel.EPGU
                else self._post.send(
                    notification,
                    addressee=office,
                    inventory=inventory,
                    sent_at=send_date,
                    simulate_failure=simulate_failure,
                )
            )
        except GatewayError as exc:
            notification.mark_error(exc.message)
            self._audit.record(
                at=self._clock.now(),
                actor=actor.login,
                action="send_notification_failed",
                outcome="failure",
                entity_type="notification",
                entity_id=notification.id,
                details={"gateway": channel.value, "error": exc.message},
            )
            raise GatewayError(
                exc.message,
                code=exc.code,
                details={
                    **exc.details,
                    "notification_id": notification.id,
                    "notification_status": notification.status.value,
                    "next_operation": "POST /notifications/{id}/return",
                },
            ) from exc

        notification.mark_sent(
            send_date=send_date,
            receipt_number=receipt.number if channel is NotificationChannel.EPGU else None,
            track_number=(track_number or receipt.number) if channel is NotificationChannel.POST else None,
            inventory=inventory if channel is NotificationChannel.POST else None,
            mvd_office_code=office.code,
            late=late,
        )

        contract_documents = self._documents.by_owner("contract", contract.id)
        if contract_documents:
            notification.contract_copy_document_id = contract_documents[0].id
        evidence_doc = Document.create(
            doc_type=(
                DocumentType.RECEIPT
                if channel is NotificationChannel.EPGU
                else DocumentType.INVENTORY
            ),
            filename=f"{channel.value}-{receipt.number}.pdf",
            owner_type="notification",
            owner_id=notification.id,
            source=f"{channel.value}_gateway",
            uploaded_at=self._clock.now(),
        )
        self._documents.add(evidence_doc)
        notification.evidence_document_ids.append(evidence_doc.id)

        contract.mark_notification_sent()
        point = self._deadlines.close_point(
            patent, PointKind.SEND_NOTIFICATION, send_date, late=late
        )
        self._reminders.schedule_for_patent(patent)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="send_mvd_notification",
            entity_type="notification",
            entity_id=notification.id,
            details={
                "contract_id": contract.id,
                "channel": channel.value,
                "late": late,
                "mvd_office": office.code,
            },
        )
        notes = [
            "Копия договора и доказательство отправки сохранены (ИНВ-8).",
            "Уведомление и доказательства хранятся бессрочно.",
        ]
        if late:
            notes.append(
                "Уведомление направлено с нарушением срока: точка отмечена как "
                "просроченная, требуется фиксация нарушения (операция 10)."
            )
        return NotificationSendResult(
            notification=notification,
            contract=contract,
            point=point,
            evidence=notification.evidence(),
            late=late,
            notes=notes,
        )

    def _parse_confirmation(
        self, channel: NotificationChannel, confirmation: dict | None
    ) -> tuple[date, str | None, str | None, str | None]:
        today = self._clock.today()
        payload = confirmation or {}
        if channel is NotificationChannel.EPGU:
            signature = payload.get("signature")
            if not signature:
                raise ValidationFailure(
                    "для отправки через ЕПГУ нужна электронная подпись (signature)",
                    code="EPGU_SIGNATURE_REQUIRED",
                )
            signed_at = payload.get("signed_at") or today
            if signed_at > today:
                raise ValidationFailure(
                    "дата подписи не может быть в будущем", code="DATE_IN_FUTURE"
                )
            return signed_at, signature, None, None

        sent_at = payload.get("sent_at") or today
        if sent_at > today:
            raise ValidationFailure(
                "дата отправки не может быть в будущем", code="DATE_IN_FUTURE"
            )
        inventory = payload.get("inventory")
        if not inventory:
            raise ValidationFailure(
                "для почтового отправления нужна опись вложения (inventory)",
                code="POST_INVENTORY_REQUIRED",
            )
        return sent_at, None, payload.get("track_number"), inventory

    def _ensure_side(self, contract: Contract, actor: User) -> None:
        if actor.role is Role.EMPLOYER_REP and getattr(actor, "employer_id", None) != contract.employer_id:
            raise ForbiddenError(
                "договор заключён с другим работодателем", code="FORBIDDEN"
            )
        if actor.role is Role.CITIZEN:
            patent = self._patents.require(contract.patent_id)
            self._access.ensure_citizen_owns(actor, patent.citizen_id)

    # --- операция 7: зафиксировать возврат уведомления --------------------
    def register_return(
        self,
        *,
        notification_id: str,
        reason: str,
        document: dict | None = None,
        actor: User | None,
    ) -> dict:
        self._access.require_employer_or_admin(actor)
        assert actor is not None
        notification = self._notifications.require(notification_id)
        contract = self._contracts.require(notification.contract_id)
        self._ensure_side(contract, actor)
        if not reason or not reason.strip():
            raise ValidationFailure(
                "укажите причину возврата уведомления", code="RETURN_REASON_REQUIRED"
            )
        if not notification.may_be_returned():
            raise ConflictError(
                "нельзя зафиксировать возврат уведомления в текущем статусе",
                code="NOTIFICATION_NOT_RETURNABLE",
                details={"status": notification.status.value},
            )

        notification.mark_error(reason.strip())
        if document is not None and document.get("filename"):
            saved = Document.create(
                doc_type=DocumentType.RECEIPT,
                filename=document["filename"],
                owner_type="notification",
                owner_id=notification.id,
                content_hash=document.get("hash"),
                source=document.get("source", "manual_upload"),
            )
            self._documents.add(saved)
            notification.evidence_document_ids.append(saved.id)

        patent = self._patents.require(contract.patent_id)
        self._deadlines.recalculate(
            patent, reason="возврат уведомления МВД", actor=actor.login
        )
        point = self._points.latest_by_kind(patent.id, PointKind.SEND_NOTIFICATION)
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="register_notification_return",
            outcome="failure",
            entity_type="notification",
            entity_id=notification.id,
            details={"reason": reason, "attempt": notification.attempts},
        )
        return {
            "notification": notification.to_dict(),
            "deadline_point": point.to_dict() if point else None,
            "task_state": "open",
            "notes": [
                "Задача уведомления остаётся открытой; доказательство попытки сохранено.",
                "При истечении срока точка станет «просроченной» (операция 10).",
            ],
        }

    # --- чтение -----------------------------------------------------------
    def get(self, notification_id: str, *, actor: User | None) -> dict:
        self._access.require_role(actor, Role.CITIZEN, Role.EMPLOYER_REP, Role.ADMIN)
        assert actor is not None
        notification = self._notifications.require(notification_id)
        contract = self._contracts.require(notification.contract_id)
        self._ensure_side(contract, actor)
        return {
            "notification": notification.to_dict(),
            "contract": contract.to_dict(),
            "evidence": notification.evidence(),
            "documents": [
                document.to_dict()
                for document in self._documents.by_owner("notification", notification.id)
            ],
        }

    def failure_policy(self) -> FailurePolicy:
        return self._policy
