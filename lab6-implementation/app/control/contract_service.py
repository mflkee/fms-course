"""Сервис договоров (``СервисДоговоров``), операции 4 и 5.

ИНВ-1, ИНВ-3 и ИНВ-4 проверяются до создания договора. Просрочка срока
трудоустройства не блокирует регистрацию (решение лаб. 3): договор
создаётся с признаком ``overdue``, а точка закрывается с отметкой ``late``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    contract_is_late,
    ensure_activity_allowed,
    ensure_no_active_contract,
    ensure_patent_is_current,
)
from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.contract import CivilContract, Contract, EmploymentContract
from app.entity.deadline import DeadlinePoint
from app.entity.documents import Document
from app.entity.enums import (
    ContractKind,
    ContractStatus,
    DocumentType,
    PointKind,
    WorkMode,
)
from app.entity.patent import Patent
from app.errors import ConflictError, ValidationFailure
from app.repository.catalogs import ActivityTypeRepository
from app.repository.contracts import ContractRepository
from app.repository.documents import DocumentRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository
from app.repository.people import EmployerRepository


@dataclass(kw_only=True)
class ContractResult:
    contract: Contract
    overdue: bool = False
    deadline_point: DeadlinePoint | None = None
    notification_task: dict | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "contract": self.contract.to_dict(),
            "overdue": self.overdue,
            "deadline_point": self.deadline_point.to_dict() if self.deadline_point else None,
            "notification_task": self.notification_task,
            "notes": self.notes,
        }


class ContractService:
    def __init__(
        self,
        contracts: ContractRepository,
        patents: PatentRepository,
        employers: EmployerRepository,
        activities: ActivityTypeRepository,
        documents: DocumentRepository,
        notifications: NotificationRepository,
        deadlines: DeadlineService,
        reminders: ReminderService,
        clock: Clock,
    ) -> None:
        self._contracts = contracts
        self._patents = patents
        self._employers = employers
        self._activities = activities
        self._documents = documents
        self._notifications = notifications
        self._deadlines = deadlines
        self._reminders = reminders
        self._clock = clock

    # --- операция 4: заключитьДоговор -------------------------------------
    def conclude(
        self,
        *,
        patent_id: str,
        employer_id: str,
        activity_code: str,
        conclusion_date: date,
        kind: ContractKind,
        document: dict | None,
        consent_confirmed: bool = True,
        number: str | None = None,
        end_date: date | None = None,
        position: str | None = None,
        work_mode: WorkMode = WorkMode.FULL_DAY,
        subject: str | None = None,
        work_deadline: date | None = None,
    ) -> ContractResult:
        patent = self._patents.require(patent_id)
        ensure_patent_is_current(patent, "заключить договор")
        employer = self._employers.require(employer_id)
        self._activities.require_allowed([activity_code])
        ensure_activity_allowed(patent, activity_code)
        ensure_no_active_contract(self._contracts.active_by_patent(patent.id), patent)

        today = self._clock.today()
        if conclusion_date > today:
            raise ValidationFailure(
                "дата заключения договора не может быть в будущем", code="DATE_IN_FUTURE"
            )
        if conclusion_date < patent.issue_date:
            raise ValidationFailure(
                "договор не может быть заключён раньше даты выдачи патента",
                code="CONTRACT_BEFORE_PATENT",
                details={"issue_date": patent.issue_date.isoformat()},
            )

        if kind is ContractKind.EMPLOYMENT:
            if not position or not position.strip():
                raise ValidationFailure(
                    "для трудового договора укажите должность", code="POSITION_REQUIRED"
                )
        else:
            if not subject or not subject.strip():
                raise ValidationFailure(
                    "для договора ГПХ укажите предмет работ", code="SUBJECT_REQUIRED"
                )
            if work_deadline is None:
                raise ValidationFailure(
                    "для договора ГПХ укажите срок работ", code="WORK_DEADLINE_REQUIRED"
                )
            if work_deadline < conclusion_date:
                raise ValidationFailure(
                    "срок работ по ГПХ не может быть раньше даты заключения",
                    code="WORK_DEADLINE_INVALID",
                )

        if consent_confirmed and (document is None or not document.get("filename")):
            raise ValidationFailure(
                "приложите подписанный файл договора", code="CONTRACT_DOCUMENT_REQUIRED"
            )

        contract_stub = f"{kind.value}-{self._contracts.count() + 1}"
        contract: Contract
        common = {
            "number": number or f"{contract_stub}/{today.year}",
            "patent_id": patent.id,
            "employer_id": employer.id,
            "activity_code": activity_code,
            "conclusion_date": conclusion_date,
            "end_date": end_date,
            "created_at": today,
            "status": ContractStatus.CONCLUDED if consent_confirmed else ContractStatus.DRAFT,
        }
        if kind is ContractKind.EMPLOYMENT:
            contract = EmploymentContract(
                **common,
                position=position.strip() if position else "",
                work_mode=work_mode,
            )
        else:
            contract = CivilContract(
                **common,
                subject=subject.strip() if subject else "",
                work_deadline=work_deadline,  # type: ignore[arg-type]
            )
        self._contracts.add(contract)

        if document is not None and document.get("filename"):
            saved = Document.create(
                doc_type=DocumentType.CONTRACT,
                filename=document["filename"],
                owner_type="contract",
                owner_id=contract.id,
                content_hash=document.get("hash"),
                source=document.get("source", "manual_upload"),
            )
            self._documents.add(saved)
            contract.document_ids.append(saved.id)

        if not consent_confirmed:
            return ContractResult(
                contract=contract,
                notes=[
                    "Согласие сторон не подтверждено — создан черновик договора.",
                    "Черновик можно отменить операцией 5; действующий договор не создан.",
                ],
            )

        overdue = contract_is_late(patent, conclusion_date)
        point = self._deadlines.close_point(
            patent, PointKind.CONCLUDE_CONTRACT, conclusion_date, late=overdue
        )
        self._deadlines.ensure_point(patent, PointKind.SEND_NOTIFICATION)
        self._reminders.schedule_for_patent(patent)
        due = patent.employment_deadline.isoformat()
        notes = [f"Уведомление МВД должно быть направлено не позднее {due}."]
        if overdue:
            notes.append(
                "Срок трудоустройства нарушен: договор заключён позже "
                f"{due}. Нарушение зафиксировано в контрольной точке; "
                "патент при этом не блокируется."
            )
        return ContractResult(
            contract=contract,
            overdue=overdue,
            deadline_point=point,
            notification_task=self._notification_task(contract, patent),
            notes=notes,
        )

    def _notification_task(self, contract: Contract, patent: Patent) -> dict:
        today = self._clock.today()
        due = patent.employment_deadline
        return {
            "contract_id": contract.id,
            "action": "send_mvd_notification",
            "due_date": due.isoformat(),
            "days_left": (due - today).days,
            "overdue": today > due,
            "allowed_channels": ["epgu", "post"],
        }

    # --- операция 5: отменитьДоговор --------------------------------------
    def cancel(self, *, contract_id: str, reason: str) -> dict:
        """Отмена черновика договора (лаб. 3, операция 5).

        Действующий договор операцией не отменяется (409): ни договор со
        статусом «заключён», ни договор с направленным уведомлением. Точка
        «заключить договор» при отмене черновика не закрывалась, поэтому
        остаётся открытой и не переоткрывается.
        """
        contract = self._contracts.require(contract_id)
        if contract.status is ContractStatus.CANCELLED:
            raise ConflictError(
                "договор уже отменён",
                code="CONTRACT_ALREADY_CANCELLED",
                details={"contract_id": contract.id},
            )
        if contract.status is ContractStatus.NOTIFICATION_SENT:
            raise ConflictError(
                "по договору уже направлено уведомление МВД: отмена невозможна, "
                "доказательства отправки сохраняются",
                code="CONTRACT_NOTIFICATION_SENT",
                details={"contract_id": contract.id},
            )
        if not contract.is_draft():
            raise ConflictError(
                "действующий договор операцией «отменитьДоговор» не отменяется: "
                "операция применяется только к черновику (согласие сторон не подтверждено)",
                code="CONTRACT_ACTIVE",
                details={"contract_id": contract.id, "status": contract.status.value},
            )
        if not reason or not reason.strip():
            raise ValidationFailure(
                "укажите причину отмены договора", code="CANCEL_REASON_REQUIRED"
            )

        contract.cancel(reason.strip(), self._clock.today())
        point = self._deadlines.latest_point(contract.patent_id, PointKind.CONCLUDE_CONTRACT)
        return {
            "contract": contract.to_dict(),
            "history_preserved": True,
            "deadline_point": point.to_dict() if point else None,
            "notes": [
                "Черновик отклонён; действующий договор не создан (ИНВ-1 не нарушен).",
                "Контрольная точка «заключить договор» остаётся открытой: срок продолжает идти.",
            ],
        }

    # --- чтение -----------------------------------------------------------
    def get(self, contract_id: str) -> dict:
        contract = self._contracts.require(contract_id)
        notifications = self._notifications.history_by_contract(contract.id)
        return {
            "contract": contract.to_dict(),
            "notifications": [notification.to_dict() for notification in notifications],
            "documents": [
                document.to_dict()
                for document in self._documents.by_owner("contract", contract.id)
            ],
        }

    def active_for_patent(self, patent_id: str) -> Contract | None:
        return self._contracts.active_by_patent(patent_id)
