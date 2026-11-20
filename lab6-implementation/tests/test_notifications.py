"""Операции 6 и 7: регистрация отправки уведомления МВД и фиксация возврата.

Система не отправляет уведомление: квитанция ЕПГУ и трек-номер Почты вводятся
исполнителем и регистрируются здесь.
"""

from __future__ import annotations

from app.container import Container


def test_send_notification_registers_entered_receipt(api, contract, container: Container):
    result = api.notify(
        contract["contract"]["id"],
        confirmation={"signature": "SIG-1", "receipt_number": "EPGU-REAL-42"},
    )
    notification = result["notification"]

    assert notification["status"] == "sent"
    assert notification["channel"] == "epgu"
    assert notification["receipt_number"] == "EPGU-REAL-42"
    assert notification["mvd_office_code"] == "72-001"
    assert notification["contract_copy_document_id"] == contract["contract"]["document_ids"][0]
    assert notification["evidence_document_ids"]
    assert result["contract"]["status"] == "notification_sent"
    assert result["deadline_point"]["status"] == "done"
    assert result["late"] is False

    assert result["package"]["channel"] == "epgu"
    assert result["package"]["addressee"] == container.offices.for_region("72").name
    assert "копия договора" in result["package"]["enclosures"]
    assert result["notes"][0].startswith("Система не отправляет уведомление")

    stored = container.notifications.history_by_contract(contract["contract"]["id"])
    assert len(stored) == 1
    assert stored[0].receipt_number == "EPGU-REAL-42"


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
    assert notification["receipt_number"] is None
    assert notification["inventory"] == "опись вложения на 2 листах"
    assert notification["send_date"] == "2026-10-25"
    assert result["package"]["channel"] == "post"
    assert "опись вложения: опись вложения на 2 листах" in " ".join(
        result["package"]["enclosures"]
    )


def test_notification_before_contract_rejected(api, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {
                "signature": "SIG",
                "signed_at": "2026-10-01",
                "receipt_number": "EPGU-1",
            },
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-2"
    assert body["details"]["contract_conclusion_date"] == "2026-10-05"


def test_late_notification_is_registered_and_flagged(api):
    created = api.register_patent(series="72 26", number="920001", issue_date="2026-07-01")
    contract = api.conclude(created["patent"]["id"], conclusion_date="2026-10-05")

    result = api.notify(contract["contract"]["id"])
    assert result["late"] is True
    assert result["notification"]["status"] == "overdue"
    assert result["deadline_point"]["late"] is True
    assert any("нарушением срока" in note for note in result["notes"])


def test_gateway_failure_is_saved_then_return_is_registered(api, contract, container):
    failed = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "receipt_number": "EPGU-FAIL"},
            "simulate_failure": True,
        },
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
    )
    result = api.expect(returned, 200)
    assert result["notification"]["status"] == "error"
    assert result["notification"]["attempts"] == 2
    assert result["notification"]["return_reason"] == "ошибка СМЭВ"
    assert result["task_state"] == "open"

    retried = api.notify(contract["contract"]["id"])
    assert retried["notification"]["status"] == "sent"
    history = container.notifications.history_by_contract(contract["contract"]["id"])
    assert len(history) == 2  # неудачная попытка сохранена как доказательство


def test_duplicate_notification_rejected(api, notified, contract):
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


def test_return_of_delivered_notification_rejected(api, notified, contract, container):
    notification = container.notifications.by_contract(contract["contract"]["id"])
    notification.mark_delivered()

    response = api.client.post(
        f"/notifications/{notification.id}/return",
        json={"reason": "отказ адресата"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "NOTIFICATION_NOT_RETURNABLE"
    assert body["details"]["status"] == "delivered"


def test_return_unknown_notification(api):
    response = api.client.post(
        "/notifications/unknown/return",
        json={"reason": "нет такого"},
    )
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"


def test_notification_channel_must_be_epgu_or_post(api, contract):
    response = api.client.post(
        "/notifications",
        json={"contract_id": contract["contract"]["id"], "channel": "email"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "NOTIFICATION_CHANNEL_INVALID"


def test_epgu_requires_signature(api, contract):
    response = api.client.post(
        "/notifications",
        json={"contract_id": contract["contract"]["id"], "channel": "epgu"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "EPGU_SIGNATURE_REQUIRED"


def test_epgu_requires_receipt_number_from_executor(api, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "EPGU_RECEIPT_REQUIRED"


def test_post_requires_track_number_from_executor(api, contract):
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "post",
            "confirmation": {"inventory": "опись"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "POST_TRACK_REQUIRED"


def test_allow_overdue_flag_is_gone(api, contract):
    """Просрочка не блокирует регистрацию, поэтому флага подтверждения больше нет."""
    response = api.client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "receipt_number": "EPGU-1"},
            "allow_overdue": True,
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "REQUEST_VALIDATION_ERROR"


def test_notification_card_shows_evidence(api, notified):
    body = api.expect(
        api.client.get(f"/notifications/{notified['notification']['id']}"), 200
    )
    assert body["notification"]["status"] == "sent"
    assert body["evidence"]["receipt_number"] == "EPGU-TEST-0001"
    assert [document["type"] for document in body["documents"]] == ["receipt"]
