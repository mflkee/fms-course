"""Операции 4 и 5: заключение и отмена договора."""

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
            "employer_id": api.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Водитель",
            "document": None,
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "CONTRACT_DOCUMENT_REQUIRED"


def test_conclude_contract_rejects_foreign_activity(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "cook",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Повар",
            "document": {"filename": "dogovor.pdf"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"
    assert body["details"]["patent_activities"] == ["driver"]


def test_second_active_contract_blocked(api, patent, contract):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-10",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "second.pdf"},
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-1"
    assert body["details"]["active_contract_id"] == contract["contract"]["id"]


def test_contract_before_patent_issue_rejected(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-09-01",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "dogovor.pdf"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "CONTRACT_BEFORE_PATENT"


def test_civil_contract_requires_scope(api, patent):
    response = api.client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": api.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-05",
            "kind": "civil",
            "subject": "Перевозка",
            "document": {"filename": "gpkh.pdf"},
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "WORK_DEADLINE_REQUIRED"


def test_late_contract_is_recorded_not_blocked(api):
    created = api.register_patent(series="72 26", number="910001", issue_date="2026-07-01")
    patent_id = created["patent"]["id"]
    assert created["patent"]["employment_deadline"] == "2026-09-01"

    result = api.conclude(patent_id, conclusion_date="2026-10-05")
    assert result["overdue"] is True
    assert result["deadline_point"]["late"] is True
    assert any("Срок трудоустройства нарушен" in note for note in result["notes"])


def test_contract_card_shows_documents(api, contract):
    body = api.expect(api.client.get(f"/contracts/{contract['contract']['id']}"), 200)
    assert body["contract"]["id"] == contract["contract"]["id"]
    assert [document["filename"] for document in body["documents"]] == ["dogovor.pdf"]
    assert body["notifications"] == []


def test_draft_contract_can_be_cancelled(api, patent, container: Container):
    draft = api.conclude(
        patent["patent"]["id"],
        consent_confirmed=False,
        document=None,
    )
    contract = draft["contract"]
    assert contract["status"] == "draft"
    assert draft["notification_task"] is None

    body = api.expect(
        api.client.post(
            f"/contracts/{contract['id']}/cancel",
            json={"reason": "кандидат отказался от трудоустройства"},
        ),
        200,
    )
    assert body["contract"]["status"] == "cancelled"
    assert body["contract"]["cancel_reason"] == "кандидат отказался от трудоустройства"
    assert body["history_preserved"] is True
    assert body["deadline_point"]["status"] == "open"

    assert container.contracts.active_by_patent(patent["patent"]["id"]) is None


def test_cancelled_draft_frees_patent_for_new_contract(api, patent, container: Container):
    draft = api.conclude(
        patent["patent"]["id"], consent_confirmed=False, document=None
    )
    api.client.post(
        f"/contracts/{draft['contract']['id']}/cancel",
        json={"reason": "отказ от сделки"},
    )

    second = api.conclude(patent["patent"]["id"], number="2-2026")
    assert second["contract"]["status"] == "concluded"
    assert container.contracts.active_by_patent(patent["patent"]["id"]) is not None


def test_concluded_contract_cannot_be_cancelled(api, patent, container: Container):
    """Операция 5 применяется только к черновику: действующий договор — отказ."""
    created = api.conclude(patent["patent"]["id"])
    contract_id = created["contract"]["id"]

    body = api.expect(
        api.client.post(
            f"/contracts/{contract_id}/cancel",
            json={"reason": "работодатель отказал в трудоустройстве"},
        ),
        409,
    )
    assert body["code"] == "CONTRACT_ACTIVE"
    assert body["details"]["status"] == "concluded"

    stored = container.contracts.require(contract_id)
    assert stored.is_active()
    conclude_point = container.points.latest_by_kind(
        patent["patent"]["id"], PointKind.CONCLUDE_CONTRACT
    )
    assert conclude_point.status.value == "done"


def test_cancel_after_notification_rejected(api, notified, contract):
    response = api.client.post(
        f"/contracts/{contract['contract']['id']}/cancel",
        json={"reason": "передумали"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "CONTRACT_NOTIFICATION_SENT"


def test_cancel_twice_rejected(api, patent):
    draft = api.conclude(
        patent["patent"]["id"], consent_confirmed=False, document=None
    )
    contract_id = draft["contract"]["id"]
    api.client.post(f"/contracts/{contract_id}/cancel", json={"reason": "отказ"})
    response = api.client.post(
        f"/contracts/{contract_id}/cancel", json={"reason": "ещё раз"}
    )
    body = api.expect(response, 409)
    assert body["code"] == "CONTRACT_ALREADY_CANCELLED"


def test_cancel_requires_reason(api, patent):
    draft = api.conclude(
        patent["patent"]["id"], consent_confirmed=False, document=None
    )
    response = api.client.post(
        f"/contracts/{draft['contract']['id']}/cancel",
        json={"reason": ""},
    )
    body = api.expect(response, 422)
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
