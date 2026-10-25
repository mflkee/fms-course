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
    assert kinds == {"conclude_contract", "send_notification", "pay_ndfl", "extend_patent"}
    assert {step["code"] for step in result["next_steps"]} == {
        "conclude_contract",
        "send_notification",
        "pay_ndfl",
    }
    documents = container.documents.by_owner("patent", patent["id"])
    assert [document.filename for document in documents] == ["patent-scan.pdf"]


def test_register_patent_rejects_duplicate_requisites(api):
    first = api.register_patent(series="72 26", number="900002")
    assert first["patent"]["number"] == "900002"

    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.container.citizens.all()[0].id,
            "series": "72 26",
            "number": "900002",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "DUPLICATE_PATENT"


def test_register_patent_rejects_future_issue_date(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.container.citizens.all()[0].id,
            "series": "72 26",
            "number": "900003",
            "issue_date": "2026-11-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "DATE_IN_FUTURE"


def test_register_patent_rejects_not_allowed_activity(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.container.citizens.all()[0].id,
            "series": "72 26",
            "number": "900004",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["teacher"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-4"


def test_archive_patent_closes_points_and_reminders(api, container: Container):
    patent = api.register_patent(series="72 26", number="900005")
    patent_id = patent["patent"]["id"]
    api.remind()  # включить напоминания, чтобы проверить их снятие
    assert container.reminders.count() > 0

    response = api.client.post(
        f"/patents/{patent_id}/archive",
        json={"basis": "new_patent", "reason": "выдан новый патент"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 200)
    assert body["patent"]["status"] == "archived"
    assert body["patent"]["archive_basis"] == "new_patent"
    assert body["cancelled_deadline_points"] == 4
    assert all(point.is_closed() for point in container.points.by_patent(patent_id))
    assert all(
        reminder.status.value == "cancelled"
        for reminder in container.reminders.all()
    )


def test_archive_patent_rejects_active_contract(api, patent, contract):
    response = api.client.post(
        f"/patents/{patent['patent']['id']}/archive",
        json={"basis": "annulled", "reason": "решение МВД"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "ACTIVE_CONTRACT"
    assert body["details"]["contract_id"] == contract["contract"]["id"]


def test_patent_details_for_employer_hide_personal_data(api, patent):
    response = api.client.get(
        f"/patents/{patent['patent']['id']}",
        headers={"X-User-Login": "hr-romashka"},
    )
    body = api.expect(response, 200)
    assert body["patent"]["id"] == patent["patent"]["id"]
    assert body["citizen"] is None
    assert body["restrictions"]["personal_data_hidden"] is True
    assert body["restrictions"]["payment_amounts_hidden"] is True
    assert body["days_left_for_employment"] == 37
    assert body["employment_overdue"] is False


def test_patent_details_for_citizen_include_public_profile(api, patent):
    response = api.client.get(
        f"/patents/{patent['patent']['id']}",
        headers={"X-User-Login": "ig-petrov"},
    )
    body = api.expect(response, 200)
    assert body["citizen"]["full_name"] == "Петров Иван Сергеевич"
    assert "inn" not in body["citizen"]


def test_patent_details_by_requisites(api):
    created = api.register_patent(series="72 26", number="900006")
    response = api.client.get(
        "/patents/by-requisites",
        params={"series": "72 26", "number": "900006"},
        headers={"X-User-Login": "hr-romashka"},
    )
    body = api.expect(response, 200)
    assert body["patent"]["id"] == created["patent"]["id"]


def test_patent_details_unknown_id(api):
    response = api.client.get("/patents/does-not-exist", headers={"X-User-Login": "admin"})
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"


def test_register_patent_requires_citizen_role(api):
    response = api.client.post(
        "/patents",
        json={
            "citizen_id": api.container.citizens.all()[0].id,
            "series": "72 26",
            "number": "900007",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "hr-romashka"},
    )
    body = api.expect(response, 403)
    assert body["code"] == "FORBIDDEN"
