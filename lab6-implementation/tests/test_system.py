"""Служебные эндпоинты, справочники и полнота набора операций."""

from __future__ import annotations

from app.container import Container

TEN_OPERATIONS = {
    ("post", "/patents"),
    ("post", "/patents/{patent_id}/archive"),
    ("get", "/patents/{patent_id}"),
    ("post", "/contracts"),
    ("post", "/contracts/{contract_id}/cancel"),
    ("post", "/notifications"),
    ("post", "/notifications/{notification_id}/return"),
    ("put", "/reminder-settings"),
    ("post", "/patents/{patent_id}/recalculate"),
    ("post", "/deadline-points/{point_id}/violation"),
}

AUXILIARY_ROUTES = {
    ("get", "/health"),
    ("get", "/catalog/regions"),
    ("get", "/catalog/activities"),
    ("get", "/catalog/offices"),
    ("get", "/catalog/citizens"),
    ("get", "/catalog/employers"),
    ("get", "/patents/by-requisites"),
    ("get", "/patents/{patent_id}/deadline-points"),
    ("get", "/contracts/{contract_id}"),
    ("get", "/notifications/{notification_id}"),
    ("get", "/reminders/due"),
}


def test_health_starts_empty(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["today"] == "2026-10-25"
    assert body["counts"] == {
        "patents": 0,
        "contracts": 0,
        "notifications": 0,
        "deadline_points": 0,
        "reminders": 0,
    }
    assert body["gateways_failing"] == []


def test_catalogs_are_available(client):
    regions = client.get("/catalog/regions").json()
    activities = client.get("/catalog/activities").json()
    offices = client.get("/catalog/offices").json()
    assert {region["code"] for region in regions} == {"72", "77", "66"}
    assert {activity["code"] for activity in activities} >= {"driver", "cook", "teacher"}
    assert {office["code"] for office in offices} == {"72-001", "77-001", "66-001"}


def test_demo_participants_are_available(client):
    citizens = client.get("/catalog/citizens").json()
    employers = client.get("/catalog/employers").json()
    assert "Петров Иван Сергеевич" in [citizen["full_name"] for citizen in citizens]
    assert all("inn" not in citizen for citizen in citizens)
    assert [employer["name"] for employer in employers] == ["ООО «Ромашка»"]


def test_openapi_lists_exactly_ten_operations(client):
    paths = client.get("/openapi.json").json()["paths"]
    available = {
        (method, path)
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert TEN_OPERATIONS <= available

    # кроме десяти операций — только служебные чтения
    assert available - TEN_OPERATIONS == AUXILIARY_ROUTES


def test_failed_gateway_returns_502_and_keeps_task(client, container: Container):
    patent = client.post(
        "/patents",
        json={
            "citizen_id": container.citizens.all()[0].id,
            "series": "72 26",
            "number": "960001",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    ).json()
    contract = client.post(
        "/contracts",
        json={
            "patent_id": patent["patent"]["id"],
            "employer_id": container.employers.all()[0].id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Водитель",
            "document": {"filename": "dogovor.pdf"},
        },
    ).json()

    response = client.post(
        "/notifications",
        json={
            "contract_id": contract["contract"]["id"],
            "channel": "epgu",
            "confirmation": {"signature": "SIG", "receipt_number": "EPGU-FAIL"},
            "simulate_failure": True,
        },
    )
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "GATEWAY_ERROR"
    assert body["details"]["gateway"] == "epgu"
    assert body["details"]["notification_status"] == "error"
    assert body["details"]["next_operation"] == "POST /notifications/{id}/return"
