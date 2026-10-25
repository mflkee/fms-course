"""Pydantic-схемы запросов (boundary-слой).

Схемы проверяют только форму данных: синтаксис, обязательность, перечисления.
Предметные правила (ИНВ-1…9) остаются в control-слое, чтобы их нельзя было
обойти, вызвав сервис напрямую.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.entity.enums import (
    ArchiveBasis,
    ContractKind,
    NotificationChannel,
    PaymentInputSource,
    WorkMode,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DocumentPayload(StrictModel):
    filename: str = Field(min_length=1, max_length=255)
    hash: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=64)


# --- патенты -------------------------------------------------------------
class PatentCreateRequest(StrictModel):
    citizen_id: str
    series: str = Field(min_length=1, max_length=32)
    number: str = Field(min_length=1, max_length=32)
    issue_date: date
    region_code: str = Field(min_length=1, max_length=8)
    activity_codes: list[str] = Field(min_length=1)
    issuing_authority: str = Field(min_length=1, max_length=255)
    valid_until: date | None = None
    scan: DocumentPayload | None = None
    previous_patent_id: str | None = None


class PatentArchiveRequest(StrictModel):
    basis: ArchiveBasis
    reason: str = Field(min_length=1, max_length=255)


class RecalculateRequest(StrictModel):
    reason: str | None = Field(default=None, max_length=255)


class NonpaymentTerminationRequest(StrictModel):
    detected_at: date


# --- договоры ------------------------------------------------------------
class ContractCreateRequest(StrictModel):
    patent_id: str
    employer_id: str
    activity_code: str
    conclusion_date: date
    kind: ContractKind
    document: DocumentPayload | None = None
    consent_confirmed: bool = True
    number: str | None = Field(default=None, max_length=64)
    end_date: date | None = None
    position: str | None = Field(default=None, max_length=255)
    work_mode: WorkMode = WorkMode.FULL_DAY
    subject: str | None = Field(default=None, max_length=500)
    work_deadline: date | None = None


class ContractCancelRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=255)


class ContractTerminateRequest(StrictModel):
    termination_date: date
    reason: str = Field(min_length=1, max_length=255)
    document: DocumentPayload | None = None
    confirm_contradiction: bool = False


# --- уведомления ---------------------------------------------------------
class ConfirmationPayload(StrictModel):
    signature: str | None = Field(default=None, max_length=255)
    signed_at: date | None = None
    sent_at: date | None = None
    track_number: str | None = Field(default=None, max_length=64)
    inventory: str | None = Field(default=None, max_length=255)


class NotificationCreateRequest(StrictModel):
    contract_id: str
    channel: NotificationChannel
    confirmation: ConfirmationPayload | None = None
    allow_overdue: bool = False
    simulate_failure: bool | None = None


class NotificationReturnRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=255)
    document: DocumentPayload | None = None


# --- напоминания и сроки -------------------------------------------------
class ReminderSettingsRequest(StrictModel):
    profile_id: str | None = None
    channels: list[NotificationChannel] = Field(min_length=1)
    days: list[int] = Field(default_factory=lambda: [30, 14, 7, 3, 1], min_length=1)
    consent: bool = True


class ViolationRequest(StrictModel):
    detected_at: date


# --- платежи -------------------------------------------------------------
class PaymentCreateRequest(StrictModel):
    patent_id: str
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_date: date
    document_number: str = Field(min_length=1, max_length=64)
    document: DocumentPayload
    fns_status: Literal["found", "not_found", "returned"] | None = None
    simulate_failure: bool | None = None


class PaymentConfirmRequest(StrictModel):
    source: PaymentInputSource
    document: DocumentPayload


__all__ = [
    "ConfirmationPayload",
    "ContractCancelRequest",
    "ContractCreateRequest",
    "ContractTerminateRequest",
    "DocumentPayload",
    "NonpaymentTerminationRequest",
    "NotificationCreateRequest",
    "NotificationReturnRequest",
    "PatentArchiveRequest",
    "PatentCreateRequest",
    "PaymentConfirmRequest",
    "PaymentCreateRequest",
    "RecalculateRequest",
    "ReminderSettingsRequest",
    "ViolationRequest",
]
