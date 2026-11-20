"""Сервис патентов (``СервисПатентов``), операции 1–3.

Проверки ИНВ-4 и ИНВ-5 живут внутри сервиса, а не в экране: правило должно
действовать при любом способе вызова. Расчёт сроков делегируется
``DeadlineService`` — единственному месту, где известно про «2 месяца».
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.control.deadline_service import DeadlineService
from app.control.invariants import (
    ensure_patent_is_current,
    ensure_single_current_patent,
)
from app.control.reminder_service import ReminderService
from app.entity.clock import Clock
from app.entity.contract import Contract
from app.entity.deadline import DeadlinePoint
from app.entity.documents import Document
from app.entity.enums import ArchiveBasis, DocumentType
from app.entity.patent import Patent, default_valid_until
from app.errors import ConflictError, NotFoundError, ValidationFailure
from app.repository.catalogs import ActivityTypeRepository, RegionRepository
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository
from app.repository.documents import DocumentRepository
from app.repository.patents import PatentRepository
from app.repository.people import CitizenRepository


@dataclass(kw_only=True)
class PatentRegistrationResult:
    patent: Patent
    points: list[DeadlinePoint]
    reminders_created: int
    next_steps: list[dict]

    def to_dict(self) -> dict:
        return {
            "patent": self.patent.to_dict(),
            "deadline_points": [point.to_dict() for point in self.points],
            "reminders_created": self.reminders_created,
            "next_steps": self.next_steps,
        }


class PatentService:
    def __init__(
        self,
        patents: PatentRepository,
        contracts: ContractRepository,
        points: DeadlinePointRepository,
        citizens: CitizenRepository,
        regions: RegionRepository,
        activities: ActivityTypeRepository,
        documents: DocumentRepository,
        deadlines: DeadlineService,
        reminders: ReminderService,
        clock: Clock,
    ) -> None:
        self._patents = patents
        self._contracts = contracts
        self._points = points
        self._citizens = citizens
        self._regions = regions
        self._activities = activities
        self._documents = documents
        self._deadlines = deadlines
        self._reminders = reminders
        self._clock = clock

    # --- операция 1: зарегистрироватьПатент -------------------------------
    def register(
        self,
        *,
        citizen_id: str,
        series: str,
        number: str,
        issue_date: date,
        region_code: str,
        activity_codes: Iterable[str],
        issuing_authority: str,
        valid_until: date | None = None,
        scan: dict | None = None,
        previous_patent_id: str | None = None,
    ) -> PatentRegistrationResult:
        citizen = self._citizens.require(citizen_id)
        if not series.strip() or not number.strip():
            raise ValidationFailure(
                "серия и номер патента обязательны", code="PATENT_REQUISITES_REQUIRED"
            )
        today = self._clock.today()
        if issue_date > today:
            raise ValidationFailure(
                "дата выдачи патента не может быть в будущем", code="DATE_IN_FUTURE"
            )

        existing_by_number = self._patents.by_requisites(series, number)
        if existing_by_number is not None:
            raise ConflictError(
                "патент с такими серией и номером уже учтён",
                code="DUPLICATE_PATENT",
                details={"patent_id": existing_by_number.id},
            )

        ensure_single_current_patent(self._patents.active_by_citizen(citizen_id))

        region = self._regions.require_code(region_code)
        codes = [code.strip() for code in activity_codes if code and code.strip()]
        if not codes:
            raise ValidationFailure(
                "в патенте должен быть указан хотя бы один вид деятельности",
                code="PATENT_ACTIVITIES_REQUIRED",
            )
        self._activities.require_allowed(codes)

        term_end = valid_until or default_valid_until(issue_date)
        if term_end <= issue_date:
            raise ValidationFailure(
                "срок действия патента должен быть позже даты выдачи",
                code="PATENT_TERM_INVALID",
            )
        if term_end > default_valid_until(issue_date):
            raise ValidationFailure(
                "срок действия патента не может превышать 12 месяцев с даты выдачи "
                "(продление оформляется новой карточкой)",
                code="PATENT_TERM_TOO_LONG",
                details={"max_valid_until": default_valid_until(issue_date).isoformat()},
            )

        if previous_patent_id is not None:
            previous = self._patents.require(previous_patent_id)
            if previous.citizen_id != citizen_id:
                raise ValidationFailure(
                    "предыдущий патент принадлежит другому гражданину",
                    code="PREVIOUS_PATENT_OWNER_MISMATCH",
                )

        patent = Patent(
            citizen_id=citizen.id,
            series=series.strip(),
            number=number.strip(),
            issue_date=issue_date,
            valid_until=term_end,
            region_code=region.code,
            activity_codes=codes,
            issuing_authority=issuing_authority.strip(),
            previous_patent_id=previous_patent_id,
            created_at=today,
        )
        self._patents.add(patent)

        if scan is not None:
            self._attach_document(
                doc_type=DocumentType.PATENT,
                owner_type="patent",
                owner_id=patent.id,
                payload=scan,
            )

        points = self._deadlines.create_patent_points(patent)
        reminders = self._reminders.schedule_for_patent(patent)
        return PatentRegistrationResult(
            patent=patent,
            points=points,
            reminders_created=len(reminders),
            next_steps=self._next_steps(patent),
        )

    def _next_steps(self, patent: Patent) -> list[dict]:
        return [
            {
                "code": "conclude_contract",
                "title": "Заключить трудовой договор или договор ГПХ",
                "due": patent.employment_deadline.isoformat(),
            },
            {
                "code": "send_notification",
                "title": "Направить уведомление МВД об осуществлении трудовой деятельности",
                "due": patent.employment_deadline.isoformat(),
            },
        ]

    # --- операция 2: пометитьПатентАрхивным -------------------------------
    def archive(
        self,
        *,
        patent_id: str,
        basis: ArchiveBasis,
        reason: str,
    ) -> dict:
        patent = self._patents.require(patent_id)
        ensure_patent_is_current(patent, "пометить патент архивным")
        if not reason or not reason.strip():
            raise ValidationFailure(
                "укажите основание утраты силы патента", code="ARCHIVE_REASON_REQUIRED"
            )

        active = self._contracts.active_by_patent(patent.id)
        if active is not None:
            raise ConflictError(
                "по патенту есть действующий договор: сначала отмените его "
                "(операция 5), затем архивируйте патент",
                code="ACTIVE_CONTRACT",
                details={"contract_id": active.id},
            )

        patent.archive(basis, self._clock.today())
        cancelled_points = self._deadlines.cancel_all(patent, f"патент архивный: {basis.value}")
        cancelled_reminders = self._reminders.cancel_for_patent(patent.id)
        return {
            "patent": patent.to_dict(),
            "cancelled_deadline_points": cancelled_points,
            "cancelled_reminders": cancelled_reminders,
            "reason": reason,
        }

    # --- операция 3: получитьСведенияОпатенте ------------------------------
    def get_details(self, patent_id: str) -> dict:
        patent = self._patents.require(patent_id)
        return self._details(patent)

    def find_by_requisites(self, series: str, number: str) -> dict:
        patent = self._patents.by_requisites(series, number)
        if patent is None:
            raise NotFoundError(
                "патент с указанными серией и номером не найден",
                code="PATENT_NOT_FOUND",
                details={"series": series, "number": number},
            )
        return self._details(patent)

    def _details(self, patent: Patent) -> dict:
        region = self._regions.by_code(patent.region_code)
        activities = [
            self._activities.by_code(code) for code in patent.activity_codes
        ]
        contract = self._contracts.active_by_patent(patent.id)
        today = self._clock.today()
        citizen = self._citizens.find(patent.citizen_id)
        return {
            "patent": patent.to_dict(),
            "region": region.to_dict() if region else None,
            "activities": [
                activity.to_dict() for activity in activities if activity is not None
            ],
            "citizen": citizen.to_public_dict() if citizen else None,
            "employment_deadline": patent.employment_deadline.isoformat(),
            "days_left_for_employment": patent.days_left_for_employment(today),
            "employment_overdue": today > patent.employment_deadline,
            "has_active_contract": contract is not None,
            "active_contract_id": contract.id if contract else None,
            "days_left": patent.days_left(today),
            "deadline_summary": self._deadlines.summary(patent).to_dict(),
        }

    # --- общее ------------------------------------------------------------
    def require(self, patent_id: str) -> Patent:
        return self._patents.require(patent_id)

    def current_contract(self, patent: Patent) -> Contract | None:
        return self._contracts.active_by_patent(patent.id)

    def _attach_document(
        self, *, doc_type: DocumentType, owner_type: str, owner_id: str, payload: dict
    ) -> Document:
        try:
            document = Document.create(
                doc_type=doc_type,
                filename=payload["filename"],
                owner_type=owner_type,
                owner_id=owner_id,
                content_hash=payload.get("hash"),
                source=payload.get("source", "manual_upload"),
            )
        except (KeyError, ValueError) as exc:
            raise ValidationFailure(
                "вложение должно содержать имя файла", code="DOCUMENT_INVALID"
            ) from exc
        return self._documents.add(document)
