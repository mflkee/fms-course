"""Отдельные тесты на каждый инвариант ИНВ-1…ИНВ-7 (DESIGN.md, раздел 5).

Проверяется не только текст ошибки, но и то, что состояние не изменилось
после отказа (для блокирующих инвариантов) либо что нарушение зафиксировано
(для «регистрирующих» инвариантов ИНВ-2 в части просрочки и ИНВ-3).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.container import Container
from app.entity.deadline import DeadlinePoint, Reminder
from app.entity.enums import NotificationChannel, PointKind
from app.errors import ConflictError


def test_inv1_only_one_active_contract_per_patent(api, patent, contract):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-06",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "second.pdf"},
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-1"
    assert body["details"]["active_contract_id"] == contract["contract"]["id"]


def test_inv2_notification_not_before_contract(api, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {
                "signature": "SIG",
                "signed_at": "2026-10-04",
                "receipt_number": "EPGU-1",
            },
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-2"


def test_inv2_late_notification_is_registered_with_flag(api):
    """Просрочка срока уведомления не блокирует отправку, а фиксируется."""
    created = api.register_patent(series="72 26", number="950003", issue_date="2026-07-01")
    contract = api.conclude(created["patent"]["id"], conclusion_date="2026-10-05")
    result = api.notify(contract["contract"]["id"])
    assert result["late"] is True
    assert result["notification"]["status"] == "overdue"
    assert result["deadline_point"]["late"] is True


def test_inv3_late_contract_is_registered_with_flag(api):
    created = api.register_patent(series="72 26", number="950002", issue_date="2026-07-01")
    result = api.conclude(created["patent"]["id"], conclusion_date="2026-10-05")
    assert result["overdue"] is True
    assert result["deadline_point"]["late"] is True
    assert result["contract"]["status"] == "concluded"


def test_inv4_contract_activity_must_be_in_patent(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "builder",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Строитель",
            "document": {"filename": "dogovor.pdf"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"
    assert body["details"]["activity_code"] == "builder"


def test_inv5_one_current_patent_and_archive_unblocks(api, container: Container):
    first = api.register_patent(series="72 26", number="950004")
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": container.citizens.all()[0].id,
            "series": "72 26",
            "number": "950005",
            "issue_date": "2026-10-02",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-5"
    assert body["details"]["existing_patent_id"] == first["patent"]["id"]

    api.archive(first["patent"]["id"])
    second = api.register_patent(series="72 26", number="950005")
    assert second["patent"]["status"] == "active"


def test_inv6_points_and_reminders_require_parent(container: Container):
    point = DeadlinePoint(
        patent_id="missing-patent",
        kind=PointKind.CONCLUDE_CONTRACT,
        planned_date=date(2026, 12, 1),
    )
    with pytest.raises(ConflictError) as point_error:
        container.points.add(point)
    assert point_error.value.code == "INV-6"

    reminder = Reminder(
        point_id="missing-point",
        channel=NotificationChannel.EMAIL,
        days_before=7,
        planned_at=date(2026, 11, 24),
        text="напоминание",
    )
    with pytest.raises(ConflictError) as reminder_error:
        container.reminders.add(reminder)
    assert reminder_error.value.code == "INV-6"


def test_inv6_archive_cancels_points_and_reminders(api, patent, container: Container):
    api.remind(days=[30, 7])
    api.archive(patent["patent"]["id"], basis="annulled", reason="аннулирован")
    assert all(point.is_closed() for point in container.points.by_patent(patent["patent"]["id"]))
    assert all(
        reminder.status.value == "skipped" for reminder in container.reminders.all()
    )


def test_inv7_duplicate_notification_for_contract_blocked(api, notified, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "post",
            "confirmation": {"inventory": "опись"},
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-7"
    assert body["details"]["notification_id"] == notified["notification"]["id"]


def test_inv7_notification_requires_active_contract(api, patent):
    draft = api.conclude(
        patent["patent"]["id"], consent_confirmed=False, document=None
    )
    contract_id = draft["contract"]["id"]

    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract_id,
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "receipt_number": "EPGU-1"},
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-7"
    assert body["details"]["status"] == "draft"

    api.client.post(f"/contracts/{contract_id}/cancel", json={"reason": "отказ"})
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract_id,
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "receipt_number": "EPGU-2"},
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-7"
    assert body["details"]["status"] == "cancelled"


def test_inv7_notification_is_bound_to_its_contract(api, notified, contract, container):
    """Уведомление принадлежит договору: другой договор его «не наследует»."""
    contract_id = contract["contract"]["id"]
    stored = container.notifications.by_contract(contract_id)
    assert stored is not None
    assert stored.contract_id == contract_id
    assert container.notifications.by_contract("another-contract") is None
    assert len(container.notifications.history_by_contract(contract_id)) == 1
