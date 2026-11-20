"""Операции 1–3: регистрация, архивация и выдача сведений о патенте."""

from __future__ import annotations

from app.container import Container


def test_register_patent_creates_card_and_control_points(api, container: Container):
    result = api.register_patent(
        series="72 26",
        number="900001",
        issue_date="2026-10-01",
        activity_codes=["driver", "loader"],
        scan={"filename": "patent-scan.pdf", "hash": "abc123"},
    )
    patent = result["patent"]

    assert patent["status"] == "active"
    assert patent["employment_deadline"] == "2026-12-01"
    assert patent["valid_until"] == "2027-09-30"
    assert patent["activity_codes"] == ["driver", "loader"]
    assert result["reminders_created"] == 0  # согласие на напоминания ещё не дано

    kinds = {point["kind"] for point in result["deadline_points"]}
    assert kinds == {"conclude_contract", "send_notification", "extend_patent"}
    assert {step["code"] for step in result["next_steps"]} == {
        "conclude_contract",
        "send_notification",
    }
    documents = container.documents.by_owner("patent", patent["id"])
    assert [document.filename for document in documents] == ["patent-scan.pdf"]


def test_register_patent_rejects_duplicate_requisites(api):
    first = api.register_patent(series="72 26", number="900002")
    assert first["patent"]["number"] == "900002"

    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.citizen_id,
            "series": "72 26",
            "number": "900002",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    )
    body = api.expect(response, 409)
    assert body["code"] == "DUPLICATE_PATENT"


def test_register_patent_rejects_future_issue_date(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.citizen_id,
            "series": "72 26",
            "number": "900003",
            "issue_date": "2026-11-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "DATE_IN_FUTURE"


def test_register_patent_rejects_not_allowed_activity(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.citizen_id,
            "series": "72 26",
            "number": "900004",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["teacher"],
            "issuing_authority": "УВМ",
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"


def test_register_patent_rejects_term_longer_than_year(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.citizen_id,
            "series": "72 26",
            "number": "900008",
            "issue_date": "2026-10-01",
            "valid_until": "2027-12-31",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    )
    body = api.expect(response, 422)
    assert body["code"] == "PATENT_TERM_TOO_LONG"


def test_archive_patent_closes_points_and_reminders(api, container: Container):
    patent = api.register_patent(series="72 26", number="900005")
    patent_id = patent["patent"]["id"]
    api.remind()  # включить напоминания, чтобы проверить их снятие
    assert container.reminders.count() > 0

    body = api.archive(patent_id, basis="new_patent", reason="выдан новый патент")
    assert body["patent"]["status"] == "archived"
    assert body["patent"]["archive_basis"] == "new_patent"
    assert body["cancelled_deadline_points"] == 3
    assert body["skipped_reminders"] > 0
    assert all(point.is_closed() for point in container.points.by_patent(patent_id))
    assert all(
        reminder.status.value == "skipped"
        for reminder in container.reminders.all()
    )


def test_archive_patent_rejects_active_contract(api, patent, contract):
    response = api.client.post(
        f"/patents/{patent['patent']['id']}/archive",
        json={"basis": "annulled", "reason": "решение МВД"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "ACTIVE_CONTRACT"
    assert body["details"]["contract_id"] == contract["contract"]["id"]


def test_archive_already_archived_patent_rejected(api, patent):
    api.archive(patent["patent"]["id"], basis="annulled", reason="аннулирован")
    response = api.client.post(
        f"/patents/{patent['patent']['id']}/archive",
        json={"basis": "mvd_decision", "reason": "повторно"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "PATENT_NOT_CURRENT"


def test_patent_details_include_citizen_and_deadlines(api, patent):
    body = api.expect(
        api.client.get(f"/patents/{patent['patent']['id']}"), 200
    )
    assert body["patent"]["id"] == patent["patent"]["id"]
    assert body["citizen"]["full_name"] == "Петров Иван Сергеевич"
    assert "inn" not in body["citizen"]  # в сведениях о патенте — только публичные данные
    assert body["region"]["code"] == "72"
    assert [activity["code"] for activity in body["activities"]] == ["driver"]
    assert body["days_left_for_employment"] == 37
    assert body["employment_overdue"] is False
    assert body["has_active_contract"] is False
    assert body["deadline_summary"]["counts"]["open"] == 3


def test_patent_details_by_requisites(api):
    created = api.register_patent(series="72 26", number="900006")
    body = api.expect(
        api.client.get(
            "/patents/by-requisites", params={"series": "72 26", "number": "900006"}
        ),
        200,
    )
    assert body["patent"]["id"] == created["patent"]["id"]


def test_patent_details_by_unknown_requisites(api):
    body = api.expect(
        api.client.get(
            "/patents/by-requisites", params={"series": "00 00", "number": "000000"}
        ),
        404,
    )
    assert body["code"] == "PATENT_NOT_FOUND"


def test_patent_details_unknown_id(api):
    response = api.client.get("/patents/does-not-exist")
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"
