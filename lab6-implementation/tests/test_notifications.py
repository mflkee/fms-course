"""Операции 6 и 7: направление уведомления МВД и фиксация возврата."""

from __future__ import annotations

from app.container import Container


def test_send_notification_via_epgu(api, contract, container: Container):
    result = api.notify(contract["contract"]["id"])
    notification = result["notification"]

    assert notification["status"] == "sent"
    assert notification["channel"] == "epgu"
    assert notification["receipt_number"].startswith("EPGU-")
    assert notification["mvd_office_code"] == "72-001"
    assert notification["contract_copy_document_id"] == contract["contract"]["document_ids"][0]
    assert notification["evidence_document_ids"]
    assert result["contract"]["status"] == "notification_sent"
    assert result["deadline_point"]["status"] == "done"
    assert result["late"] is False

    stored = container.notifications.history_by_contract(contract["contract"]["id"])
    assert len(stored) == 1
    assert stored[0].receipt_number == notification["receipt_number"]


def test_send_notification_via_post(api, contract):
    result = api.notify(
        contract["contract"]["id"],
        channel="post",
        confirmation={
            "sent_at": "2026-10-25",
            "track_number": "RU123456789",
            "inventory": "опись вложения на 2 листах",
        },
    )
    notification = result["notification"]
    assert notification["status"] == "sent"
    assert notification["track_number"] == "RU123456789"
    assert notification["inventory"] == "опись вложения на 2 листах"
    assert notification["send_date"] == "2026-10-25"


def test_notification_before_contract_rejected(api, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "signed_at": "2026-10-01"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-2"
    assert body["details"]["contract_conclusion_date"] == "2026-10-05"


def test_late_notification_requires_allow_overdue(api):
    created = api.register_patent(series="72 26", number="920001", issue_date="2026-07-01")
    patent_id = created["patent"]["id"]
    contract = api.conclude(patent_id, conclusion_date="2026-10-05")
    contract_id = contract["contract"]["id"]

    payload = {
        "contract_id": contract_id,
        "channel": "epgu",
        "confirmation": {"signature": "SIG"},
    }
    blocked = api.client.post(
        "/notifications", json=payload, headers={"X-User-Login": "admin"}
    )
    body = api.expect(blocked, 422)
    assert body["code"] == "INV-2"
    assert "allow_overdue" in body["details"]["hint"]

    allowed = api.client.post(
        "/notifications",
        json={**payload, "allow_overdue": True},
        headers={"X-User-Login": "admin"},
    )
    result = api.expect(allowed, 201)
    assert result["late"] is True
    assert result["notification"]["status"] == "overdue"


def test_gateway_failure_is_saved_then_return_is_registered(api, contract, container):
    failed = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG"},
            "simulate_failure": True,
        },
        headers={"X-User-Login": "admin"},
    )
    error = api.expect(failed, 502)
    assert error["code"] == "GATEWAY_ERROR"
    notification_id = error["details"]["notification_id"]
    stored = container.notifications.require(notification_id)
    assert stored.status.value == "error"
    assert stored.attempts == 1

    returned = api.client.post(
        f"/notifications/{notification_id}/return",
        json={"reason": "ошибка СМЭВ", "document": {"filename": "vozvrat.pdf"}},
        headers={"X-User-Login": "admin"},
    )
    result = api.expect(returned, 200)
    assert result["notification"]["status"] == "error"
    assert result["notification"]["attempts"] == 2
    assert result["notification"]["return_reason"] == "ошибка СМЭВ"
    assert result["task_state"] == "open"

    retried = api.notify(contract["contract"]["id"])
    assert retried["notification"]["status"] == "sent"
    history = container.notifications.history_by_contract(contract["contract"]["id"])
    assert len(history) == 2  # неудачная попытка сохранена (ИНВ-8)


def test_duplicate_notification_rejected(api, notified, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "post",
            "confirmation": {"inventory": "опись"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "NOTIFICATION_ALREADY_SENT"


def test_return_of_delivered_notification_rejected(api, notified, contract, container):
    notification = container.notifications.by_contract(contract["contract"]["id"])
    notification.mark_delivered()

    response = api.client.post(
        f"/notifications/{notification.id}/return",
        json={"reason": "отказ адресата"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "NOTIFICATION_NOT_RETURNABLE"
    assert body["details"]["status"] == "delivered"


def test_return_unknown_notification(api):
    response = api.client.post(
        "/notifications/unknown/return",
        json={"reason": "нет такого"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"


def test_employer_can_send_notification(api, contract):
    allowed = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG"},
        },
        headers={"X-User-Login": "hr-romashka"},
    )
    body = api.expect(allowed, 201)
    assert body["notification"]["status"] == "sent"
