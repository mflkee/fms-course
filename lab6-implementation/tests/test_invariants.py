"""Отдельные тесты на каждый инвариант ИНВ-1…ИНВ-9.

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
            "employer_id": api.container.employers.all()[0].id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-06",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "second.pdf"},
        },
        headers={"X-User-Login": "admin"},
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
            "confirmation": {"signature": "SIG", "signed_at": "2026-10-04"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-2"


def test_inv2_late_notification_blocked_without_override(api):
    created = api.register_patent(series="72 26", number="950001", issue_date="2026-07-01")
    contract = api.conclude(created["patent"]["id"], conclusion_date="2026-10-05")
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-2"
    assert body["details"]["deadline"] == "2026-09-01"


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
            "employer_id": api.container.employers.all()[0].id,
            "activity_code": "builder",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Строитель",
            "document": {"filename": "dogovor.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"
    assert body["details"]["activity_code"] == "builder"


def test_inv5_payment_gap_and_restore(api, patent):
    api.pay(patent["patent"]["id"], period="2026-10")

    # ноябрь зарегистрирован, но не подтверждён: декабрь создать нельзя
    api.pay(patent["patent"]["id"], period="2026-11", fns_status="not_found")
    gap = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-12",
            "amount": "6000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-gap",
            "document": {"filename": "cheque.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(gap, 409)
    assert body["code"] == "INV-5"

    # подтверждение ноябрьского платежа восстанавливает непрерывность
    pending = api.container.payments.by_period(patent["patent"]["id"], "2026-11")
    confirmed = api.client.post(
        f"/payments/{pending.id}/confirm",
        json={"source": "manual", "document": {"filename": "november.pdf"}},
        headers={"X-User-Login": "admin"},
    )
    result = api.expect(confirmed, 200)
    assert result["patent"]["paid_until"] == "2026-11-30"


def test_inv6_one_current_patent_and_archive_unblocks(api, container: Container):
    first = api.register_patent(series="72 26", number="950003")
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": container.citizens.all()[0].id,
            "series": "72 26",
            "number": "950004",
            "issue_date": "2026-10-02",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-6"
    assert body["details"]["existing_patent_id"] == first["patent"]["id"]

    api.expect(
        api.client.post(
            f"/patents/{first['patent']['id']}/archive",
            json={"basis": "new_patent", "reason": "выдан новый патент"},
            headers={"X-User-Login": "admin"},
        ),
        200,
    )
    second = api.register_patent(series="72 26", number="950004")
    assert second["patent"]["status"] == "active"


def test_inv7_payment_amount_matches_region_cost(api, patent):
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-10",
            "amount": "7000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-7",
            "document": {"filename": "cheque.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-7"
    assert body["details"]["expected"] == "6000.00"
    assert body["details"]["excess"] == "1000.00"


def test_inv8_evidence_survives_contract_termination(api, notified, contract, container):
    notification_id = notified["notification"]["id"]
    contract_id = contract["contract"]["id"]

    api.expect(
        api.client.post(
            f"/contracts/{contract_id}/terminate",
            json={"termination_date": "2026-10-25", "reason": "увольнение"},
            headers={"X-User-Login": "admin"},
        ),
        200,
    )

    stored = api.expect(
        api.client.get(f"/notifications/{notification_id}", headers={"X-User-Login": "admin"}),
        200,
    )
    assert stored["notification"]["status"] == "sent"
    assert stored["notification"]["evidence_document_ids"]
    history = container.notifications.history_by_contract(contract_id)
    assert len(history) == 1
    assert not hasattr(container.notifications, "delete")


def test_inv9_points_and_reminders_require_parent(container: Container):
    point = DeadlinePoint(
        patent_id="missing-patent",
        kind=PointKind.CONCLUDE_CONTRACT,
        planned_date=date(2026, 12, 1),
    )
    with pytest.raises(ConflictError) as point_error:
        container.points.add(point)
    assert point_error.value.code == "INV-9"

    reminder = Reminder(
        point_id="missing-point",
        channel=NotificationChannel.EMAIL,
        days_before=7,
        planned_at=date(2026, 11, 24),
        text="напоминание",
    )
    with pytest.raises(ConflictError) as reminder_error:
        container.reminders.add(reminder)
    assert reminder_error.value.code == "INV-9"


def test_inv9_archive_cancels_points_and_reminders(api, patent, container: Container):
    api.remind(days=[30, 7])
    api.expect(
        api.client.post(
            f"/patents/{patent['patent']['id']}/archive",
            json={"basis": "annulled", "reason": "аннулирован"},
            headers={"X-User-Login": "admin"},
        ),
        200,
    )
    assert all(point.is_closed() for point in container.points.by_patent(patent["patent"]["id"]))
    assert all(
        reminder.status.value == "cancelled" for reminder in container.reminders.all()
    )
