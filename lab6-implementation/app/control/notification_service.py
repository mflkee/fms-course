"""Сервис уведомлений МВД (``СервисУведомлений``), операции 6 и 7.

Система не отправляет уведомление и не интегрируется с ЕПГУ или Почтой России
(DESIGN.md, раздел 1). Операция 6 формирует комплект, а затем регистрирует факт
отправки: квитанцию ЕПГУ или трек-номер и опись, которые ввёл исполнитель.
Доказательства сохраняются навсегда (DESIGN.md, раздел 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    ensure_notification_for_active_contract,
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
)
from app.entity.notification import Notification
from app.errors import ConflictError, GatewayError, ValidationFailure
from app.gateway.base import Package
from app.gateway.epgu import EpguGateway
from app.gateway.post import PostGateway
from app.repository.catalogs import MvdOfficeRepository
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository
from app.repository.documents import DocumentRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository

MVD_CHANNELS = {NotificationChannel.EPGU, NotificationChannel.POST}


@dataclass(kw_only=True)
class _Confirmation:
    """Сведения об отправке, введённые исполнителем (ПодтверждениеОтправки)."""

    send_date: date
    signature: str | None = None
    receipt_number: str | None = None
    track_number: str | None = None
    inventory: str | None = None


@dataclass(kw_only=True)
class NotificationSendResult:
    notification: Notification
    contract: Contract
    point: DeadlinePoint | None
    package: Package
    evidence: dict
    late: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "notification": self.notification.to_dict(),
            "contract": self.contract.to_dict(),
            "deadline_point": self.point.to_dict() if self.point else None,
            "package": self.package.to_dict(),
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
        clock: Clock,
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
        self._clock = clock

    # --- операция 6: направитьУведомлениеМВД ------------------------------
    def send(
        self,
        *,
        contract_id: str,
        channel: NotificationChannel,
        confirmation: dict | None = None,
        simulate_failure: bool | None = None,
    ) -> NotificationSendResult:
        contract = self._contracts.require(contract_id)
        if channel not in MVD_CHANNELS:
            raise ValidationFailure(
                "уведомление МВД направляется через ЕПГУ или Почту России",
                code="NOTIFICATION_CHANNEL_INVALID",
                details={"allowed": sorted(item.value for item in MVD_CHANNELS)},
            )
        ensure_notification_for_active_contract(
            contract, self._notifications.history_by_contract(contract.id)
        )

        patent = self._patents.require(contract.patent_id)
        ensure_patent_is_current(patent, "направить уведомление МВД")
        proof = self._parse_confirmation(channel, confirmation)
        ensure_notification_not_before_contract(proof.send_date, contract)

        late = notification_is_late(patent, proof.send_date)
        office = self._offices.for_region(patent.region_code)
        contract_documents = self._documents.by_owner("contract", contract.id)
        notification = Notification(
            contract_id=contract.id,
            channel=channel,
            created_at=self._clock.now(),
        )
        self._notifications.add(notification)
        if contract_documents:
            notification.contract_copy_document_id = contract_documents[0].id

        if channel is NotificationChannel.EPGU:
            package = self._epgu.build_package(
                addressee=office,
                signed_at=proof.send_date,
                contract_copy_attached=bool(contract_documents),
            )
        else:
            package = self._post.build_package(
                addressee=office,
                inventory=proof.inventory or "",
                sent_at=proof.send_date,
                contract_copy_attached=bool(contract_documents),
            )

        try:
            if channel is NotificationChannel.EPGU:
                receipt = self._epgu.register_receipt(
                    notification,
                    receipt_number=proof.receipt_number or "",
                    simulate_failure=simulate_failure,
                )
            else:
                receipt = self._post.register_track(
                    notification,
                    track_number=proof.track_number or "",
                    simulate_failure=simulate_failure,
                )
        except GatewayError as exc:
            notification.mark_error(exc.message)
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
            send_date=proof.send_date,
            receipt_number=receipt.number if channel is NotificationChannel.EPGU else None,
            track_number=receipt.number if channel is NotificationChannel.POST else None,
            inventory=proof.inventory if channel is NotificationChannel.POST else None,
            mvd_office_code=office.code,
            late=late,
        )

        evidence_doc = Document.create(
            doc_type=(
                DocumentType.RECEIPT
                if channel is NotificationChannel.EPGU
                else DocumentType.INVENTORY
            ),
            filename=f"{channel.value}-{receipt.number}.pdf",
            owner_type="notification",
            owner_id=notification.id,
            source="executor_input",
            uploaded_at=self._clock.now(),
        )
        self._documents.add(evidence_doc)
        notification.evidence_document_ids.append(evidence_doc.id)

        contract.mark_notification_sent()
        point = self._deadlines.close_point(
            patent, PointKind.SEND_NOTIFICATION, proof.send_date, late=late
        )
        self._reminders.schedule_for_patent(patent)
        notes = [
            "Система не отправляет уведомление: комплект сформирован, квитанция или трек-номер зарегистрированы по данным исполнителя.",
            "Копия договора и доказательство отправки сохранены; хранятся бессрочно.",
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
            package=package,
            evidence=notification.evidence(),
            late=late,
            notes=notes,
        )

    def _parse_confirmation(
        self, channel: NotificationChannel, confirmation: dict | None
    ) -> _Confirmation:
        today = self._clock.today()
        payload = confirmation or {}
        if channel is NotificationChannel.EPGU:
            signature = payload.get("signature")
            if not signature:
                raise ValidationFailure(
                    "для регистрации отправки через ЕПГУ нужна электронная подпись (signature)",
                    code="EPGU_SIGNATURE_REQUIRED",
                )
            receipt_number = payload.get("receipt_number")
            if not receipt_number:
                raise ValidationFailure(
                    "укажите номер квитанции ЕПГУ (receipt_number): его выдаёт ЕПГУ "
                    "после подачи уведомления",
                    code="EPGU_RECEIPT_REQUIRED",
                )
            signed_at = payload.get("signed_at") or today
            if signed_at > today:
                raise ValidationFailure(
                    "дата подписи не может быть в будущем", code="DATE_IN_FUTURE"
                )
            return _Confirmation(
                send_date=signed_at, signature=signature, receipt_number=receipt_number
            )

        sent_at = payload.get("sent_at") or today
        if sent_at > today:
            raise ValidationFailure(
                "дата отправки не может быть в будущем", code="DATE_IN_FUTURE"
            )
        track_number = payload.get("track_number")
        if not track_number:
            raise ValidationFailure(
                "укажите трек-номер почтового отправления (track_number)",
                code="POST_TRACK_REQUIRED",
            )
        inventory = payload.get("inventory")
        if not inventory:
            raise ValidationFailure(
                "для почтового отправления нужна опись вложения (inventory)",
                code="POST_INVENTORY_REQUIRED",
            )
        return _Confirmation(send_date=sent_at, track_number=track_number, inventory=inventory)

    # --- операция 7: зафиксироватьВозвратУведомления ----------------------
    def register_return(
        self,
        *,
        notification_id: str,
        reason: str,
        document: dict | None = None,
    ) -> dict:
        notification = self._notifications.require(notification_id)
        contract = self._contracts.require(notification.contract_id)
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
        point = self._points.latest_by_kind(patent.id, PointKind.SEND_NOTIFICATION)
        if point is not None:
            # отправление вернулось: задача уведомления снова открыта
            point.reopen(patent.employment_deadline)
        self._deadlines.recalculate(patent, reason="возврат уведомления МВД")
        point = self._points.latest_by_kind(patent.id, PointKind.SEND_NOTIFICATION)
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
    def get(self, notification_id: str) -> dict:
        notification = self._notifications.require(notification_id)
        contract = self._contracts.require(notification.contract_id)
        return {
            "notification": notification.to_dict(),
            "contract": contract.to_dict(),
            "evidence": notification.evidence(),
            "documents": [
                document.to_dict()
                for document in self._documents.by_owner("notification", notification.id)
            ],
        }
