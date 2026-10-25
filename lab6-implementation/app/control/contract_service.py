"""Сервис договоров (лаб. 5, ``СервисДоговоров``), операции 4, 5, 14.

ИНВ-1, ИНВ-3 и ИНВ-4 проверяются до создания договора. Просрочка срока
трудоустройства не блокирует регистрацию (решение лаб. 3, п. 6.1.4): договор
создаётся с признаком ``overdue``, а точка закрывается с отметкой ``late``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.control.access_service import AccessService
from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    contract_is_late,
    ensure_activity_allowed,
    ensure_contract_allows_termination,
    ensure_contract_is_draft,
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
    Role,
    WorkMode,
)
from app.entity.patent import Patent
from app.entity.user import User
from app.errors import ConflictError, ForbiddenError, ValidationFailure
from app.repository.audit import AuditRepository
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


@dataclass(kw_only=True)
class TerminationResult:
    contract: Contract
    reopened_point: DeadlinePoint | None
    notification_task: dict | None
    history_notifications: int
    corrected: bool

    def to_dict(self) -> dict:
        return {
            "contract": self.contract.to_dict(),
            "reopened_point": (
                self.reopened_point.to_dict() if self.reopened_point else None
            ),
            "notification_task": self.notification_task,
            "history_notifications": self.history_notifications,
            "corrected": self.corrected,
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
        access: AccessService,
        clock: Clock,
        audit: AuditRepository,
    ) -> None:
        self._contracts = contracts
        self._patents = patents
        self._employers = employers
        self._activities = activities
        self._documents = documents
        self._notifications = notifications
        self._deadlines = deadlines
        self._reminders = reminders
        self._access = access
        self._clock = clock
        self._audit = audit

    # --- операция 4: заключить договор ------------------------------------
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
        actor: User | None,
    ) -> ContractResult:
        self._access.require_employer_rep(actor)
        assert actor is not None
        if actor.role is Role.EMPLOYER_REP and actor.employer_id != employer_id:  # type: ignore[attr-defined]
            raise ForbiddenError(
                "представитель работодателя может заключать договоры только от своего работодателя",
                code="FORBIDDEN",
                details={"employer_id": employer_id},
            )

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
            self._audit.record(
                at=self._clock.now(),
                actor=actor.login,
                action="draft_contract_created",
                entity_type="contract",
                entity_id=contract.id,
                details={"reason": "согласие сторон не подтверждено"},
            )
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
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="conclude_contract",
            entity_type="contract",
            entity_id=contract.id,
            details={
                "patent_id": patent.id,
                "employer_id": employer.id,
                "overdue": overdue,
            },
        )
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

    # --- операция 5: отменить договор -------------------------------------
    def cancel(self, *, contract_id: str, reason: str, actor: User | None) -> dict:
        self._access.require_employer_or_admin(actor)
        assert actor is not None
        contract = self._contracts.require(contract_id)
        self._ensure_side(contract, actor)
        ensure_contract_is_draft(contract)
        if not reason or not reason.strip():
            raise ValidationFailure(
                "укажите причину отмены договора", code="CANCEL_REASON_REQUIRED"
            )
        contract.cancel(reason.strip(), self._clock.today())
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="cancel_contract",
            entity_type="contract",
            entity_id=contract.id,
            details={"reason": reason},
        )
        return {
            "contract": contract.to_dict(),
            "active_contract_created": False,
            "history_preserved": True,
            "deadline_point_state": "open",
            "notes": [
                "Неуспешная попытка сохранена в истории.",
                "Контрольная точка «заключить договор» остаётся открытой: срок продолжает идти.",
            ],
        }

    # --- операция 14: прекратить договор ----------------------------------
    def terminate(
        self,
        *,
        contract_id: str,
        termination_date: date,
        reason: str,
        document: dict | None = None,
        confirm_contradiction: bool = False,
        actor: User | None,
    ) -> TerminationResult:
        self._access.require_employer_or_admin(actor)
        assert actor is not None
        contract = self._contracts.require(contract_id)
        self._ensure_side(contract, actor)
        ensure_contract_allows_termination(contract)
        if not reason or not reason.strip():
            raise ValidationFailure(
                "укажите основание прекращения договора", code="TERMINATION_REASON_REQUIRED"
            )
        if termination_date < contract.conclusion_date:
            raise ValidationFailure(
                "дата прекращения не может быть раньше даты заключения договора",
                code="TERMINATION_DATE_INVALID",
                details={"conclusion_date": contract.conclusion_date.isoformat()},
            )

        history = self._notifications.history_by_contract(contract.id)
        last_notification = self._notifications.by_contract(contract.id)
        corrected = False
        if (
            last_notification is not None
            and last_notification.send_date is not None
            and termination_date < last_notification.send_date
        ):
            if not confirm_contradiction:
                raise ConflictError(
                    "дата прекращения раньше уже направленного уведомления МВД: "
                    "требуется подтверждение (confirm_contradiction=true)",
                    code="TERMINATION_CONTRADICTS_NOTIFICATION",
                    details={
                        "notification_id": last_notification.id,
                        "notification_date": last_notification.send_date.isoformat(),
                    },
                )
            corrected = True

        contract.terminate(
            termination_date, reason.strip(), corrected=corrected
        )
        if document is not None and document.get("filename"):
            saved = Document.create(
                doc_type=DocumentType.AGREEMENT,
                filename=document["filename"],
                owner_type="contract",
                owner_id=contract.id,
                content_hash=document.get("hash"),
                source=document.get("source", "manual_upload"),
            )
            self._documents.add(saved)
            contract.document_ids.append(saved.id)

        patent = self._patents.require(contract.patent_id)
        reopened: DeadlinePoint | None = None
        if patent.is_current() and self._contracts.active_by_patent(patent.id) is None:
            point = self._deadlines.ensure_point(patent, PointKind.CONCLUDE_CONTRACT)
            point.reopen(patent.employment_deadline)
            self._deadlines.recalculate(
                patent, reason="прекращение договора: открыта задача трудоустройства",
                actor=actor.login,
            )
            reopened = point
        self._audit.record(
            at=self._clock.now(),
            actor=actor.login,
            action="terminate_contract",
            entity_type="contract",
            entity_id=contract.id,
            details={
                "reason": reason,
                "termination_date": termination_date.isoformat(),
                "corrected": corrected,
            },
        )
        return TerminationResult(
            contract=contract,
            reopened_point=reopened,
            notification_task={
                "contract_id": contract.id,
                "action": "send_termination_notification",
                "reason": reason,
                "allowed_channels": ["epgu", "post"],
            },
            history_notifications=len(history),
            corrected=corrected,
        )

    def _ensure_side(self, contract: Contract, actor: User) -> None:
        if actor.role is Role.EMPLOYER_REP and getattr(actor, "employer_id", None) != contract.employer_id:
            raise ForbiddenError(
                "договор заключён с другим работодателем", code="FORBIDDEN"
            )
        if actor.role is Role.CITIZEN:
            patent = self._patents.require(contract.patent_id)
            self._access.ensure_citizen_owns(actor, patent.citizen_id)

    # --- чтение -----------------------------------------------------------
    def get(self, contract_id: str, *, actor: User | None) -> dict:
        self._access.require_role(actor, Role.CITIZEN, Role.EMPLOYER_REP, Role.ADMIN)
        assert actor is not None
        contract = self._contracts.require(contract_id)
        self._ensure_side(contract, actor)
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
