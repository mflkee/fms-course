"""Операции 4, 5, 14: заключение, отмена и прекращение договора."""

from __future__ import annotations

from app.container import Container
from app.entity.enums import PointKind


def test_conclude_employment_contract(api, patent, container: Container):
    result = api.conclude(patent["patent"]["id"])
    contract = result["contract"]

    assert contract["status"] == "concluded"
    assert contract["kind"] == "employment"
    assert contract["position"] == "Водитель автомобиля"
    assert contract["document_ids"]
    assert result["overdue"] is False
    assert result["deadline_point"]["status"] == "done"
    assert result["notification_task"]["due_date"] == "2026-12-01"

    conclude_point = container.points.latest_by_kind(
        patent["patent"]["id"], PointKind.CONCLUDE_CONTRACT
    )
    assert conclude_point.status.value == "done"


def test_conclude_civil_contract(api, patent):
    result = api.conclude(
        patent["patent"]["id"],
        kind="civil",
        subject="Перевозка грузов",
        work_deadline="2026-12-20",
        position=None,
    )
    contract = result["contract"]
    assert contract["kind"] == "civil"
    assert contract["subject"] == "Перевозка грузов"
    assert contract["work_deadline"] == "2026-12-20"
    assert "position" not in contract


def test_conclude_contract_without_document_rejected(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.container.employers.all()[0].id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Водитель",
            "document": None,
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "CONTRACT_DOCUMENT_REQUIRED"


def test_conclude_contract_rejects_foreign_activity(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.container.employers.all()[0].id,
            "activity_code": "cook",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Повар",
            "document": {"filename": "dogovor.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"
    assert body["details"]["patent_activities"] == ["driver"]


def test_second_active_contract_blocked(api, patent, contract):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.container.employers.all()[0].id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-10",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "second.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-1"
    assert body["details"]["active_contract_id"] == contract["contract"]["id"]


def test_late_contract_is_recorded_not_blocked(api):
    created = api.register_patent(series="72 26", number="910001", issue_date="2026-07-01")
    patent_id = created["patent"]["id"]
    assert created["patent"]["employment_deadline"] == "2026-09-01"

    result = api.conclude(patent_id, conclusion_date="2026-10-05")
    assert result["overdue"] is True
    assert result["deadline_point"]["late"] is True
    assert any("Срок трудоустройства нарушен" in note for note in result["notes"])


def test_draft_contract_can_be_cancelled(api, patent, container: Container):
    draft = api.conclude(
        patent["patent"]["id"],
        consent_confirmed=False,
        document=None,
    )
    contract = draft["contract"]
    assert contract["status"] == "draft"
    assert draft["notification_task"] is None

    response = api.client.post(
        f"/contracts/{contract['id']}/cancel",
        json={"reason": "кандидат отказался от трудоустройства"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 200)
    assert body["contract"]["status"] == "cancelled"
    assert body["contract"]["cancel_reason"] == "кандидат отказался от трудоустройства"
    assert body["history_preserved"] is True
    assert body["deadline_point_state"] == "open"

    assert container.contracts.active_by_patent(patent["patent"]["id"]) is None


def test_cancel_concluded_contract_rejected(api, contract):
    response = api.client.post(
        f"/contracts/{contract['contract']['id']}/cancel",
        json={"reason": "передумали"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "CONTRACT_NOT_DRAFT"


def test_terminate_contract_reopens_employment_point(api, patent, contract, container):
    response = api.client.post(
        f"/contracts/{contract['contract']['id']}/terminate",
        json={
            "termination_date": "2026-10-20",
            "reason": "расторжение по соглашению сторон",
            "document": {"filename": "soglashenie.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 200)
    assert body["contract"]["status"] == "terminated"
    assert body["contract"]["termination_date"] == "2026-10-20"
    assert body["reopened_point"] is not None
    assert body["reopened_point"]["kind"] == "conclude_contract"
    assert body["notification_task"]["action"] == "send_termination_notification"
    assert container.contracts.active_by_patent(patent["patent"]["id"]) is None


def test_terminate_before_conclusion_rejected(api, contract):
    response = api.client.post(
        f"/contracts/{contract['contract']['id']}/terminate",
        json={"termination_date": "2026-09-01", "reason": "ошибка даты"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "TERMINATION_DATE_INVALID"


def test_termination_contradicting_notification_requires_confirmation(api, notified):
    contract_id = notified["contract"]["id"]
    payload = {
        "termination_date": "2026-10-10",
        "reason": "расторжение по соглашению сторон",
    }
    response = api.client.post(
        f"/contracts/{contract_id}/terminate",
        json=payload,
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "TERMINATION_CONTRADICTS_NOTIFICATION"

    confirmed = api.client.post(
        f"/contracts/{contract_id}/terminate",
        json={**payload, "confirm_contradiction": True},
        headers={"X-User-Login": "admin"},
    )
    result = api.expect(confirmed, 200)
    assert result["corrected"] is True
    assert result["history_notifications"] == 1
