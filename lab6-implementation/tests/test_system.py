"""Служебные эндпоинты, права доступа и планировщик."""

from __future__ import annotations

from app.container import Container


def test_health_reports_zero_state(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["today"] == "2026-10-25"
    assert body["counts"]["patents"] == 0
    assert body["gateways_failing"] == []


def test_catalogs_are_available(client):
    regions = client.get("/catalog/regions").json()
    activities = client.get("/catalog/activities").json()
    assert {region["code"] for region in regions} == {"72", "77", "66"}
    assert regions[0]["patent_cost"] == "6000.00"
    assert {activity["code"] for activity in activities} >= {"driver", "cook", "teacher"}


def test_users_are_visible_only_to_admin(client):
    as_admin = client.get("/users", headers={"X-User-Login": "admin"})
    assert as_admin.status_code == 200
    logins = {user["login"] for user in as_admin.json()}
    assert logins == {"admin", "auditor", "hr-romashka", "ig-petrov"}

    as_employer = client.get("/users", headers={"X-User-Login": "hr-romashka"})
    assert as_employer.status_code == 403


def test_unknown_login_is_rejected(client):
    response = client.get("/patents/whatever", headers={"X-User-Login": "nobody"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_audit_log_contains_operations(client, container: Container):
    client.post(
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
        headers={"X-User-Login": "admin"},
    )
    events = client.get("/audit-events", headers={"X-User-Login": "admin"}).json()
    assert events
    assert any(event["action"] == "register_patent" for event in events)


def test_scheduler_runs_daily_control(client, container: Container):
    created = client.post(
        "/patents",
        json={
            "citizen_id": container.citizens.all()[0].id,
            "series": "72 26",
            "number": "960002",
            "issue_date": "2026-07-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
        headers={"X-User-Login": "admin"},
    ).json()
    patent_id = created["patent"]["id"]

    response = client.post("/scheduler/daily-run", headers={"X-User-Login": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["processed_patents"] == 1
    assert body["recalculated"] == [patent_id]
    assert body["patents_with_unpaid_period"]


def test_default_user_is_admin(client, container: Container):
    response = client.post(
        "/patents",
        json={
            "citizen_id": container.citizens.all()[0].id,
            "series": "72 26",
            "number": "960003",
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ",
        },
    )
    assert response.status_code == 201


def test_openapi_lists_all_sixteen_operations(client):
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
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
        ("post", "/payments"),
        ("post", "/payments/{payment_id}/confirm"),
        ("post", "/patents/{patent_id}/terminate-nonpayment"),
        ("post", "/contracts/{contract_id}/terminate"),
        ("get", "/reports"),
        ("get", "/reports/{report_id}/export"),
    }
    available = {
        (method, path)
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert expected <= available
    assert len(expected) == 16
