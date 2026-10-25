"""Операции 15–16: реестр, срез данных и выгрузка с обезличиванием."""

from __future__ import annotations

import hashlib

from app.container import Container


def test_build_report_records_snapshot(api, patent, contract):
    body = api.build_report()
    assert body["row_count"] == 1
    assert body["critical_count"] == 0
    row = body["rows"][0]
    assert row["patent"] == "72 26 000001"
    assert row["citizen_name"] == "Петров Иван Сергеевич"
    assert row["employer"] == "ООО «Ромашка»"
    assert row["contract_date"] == "2026-10-05"
    assert row["payment_status"] == "нет подтверждённых платежей"

    fetched = api.expect(
        api.client.get(f"/reports/{body['id']}", headers={"X-User-Login": "admin"}), 200
    )
    assert fetched["snapshot_at"] == body["snapshot_at"]
    assert fetched["parameters"] == body["parameters"]


def test_build_report_empty_selection(api, patent):
    response = api.client.get(
        "/reports", params={"region": "77"}, headers={"X-User-Login": "admin"}
    )
    body = api.expect(response, 404)
    assert body["code"] == "EMPTY_SELECTION"


def test_build_report_requires_admin(api, patent):
    response = api.client.get("/reports", headers={"X-User-Login": "hr-romashka"})
    body = api.expect(response, 403)
    assert body["code"] == "FORBIDDEN"


def test_export_csv_with_hash(api, patent, container: Container):
    report = api.build_report()
    response = api.client.get(
        f"/reports/{report['id']}/export",
        params={"format": "csv"},
        headers={"X-User-Login": "admin"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    digest = hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-export-hash"] == digest
    assert response.headers["x-export-anonymized"] == "false"
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("ФИО;Патент;Регион")
    assert "Петров Иван Сергеевич" in text

    stored = container.reports.require(report["id"])
    assert len(stored.exports) == 1
    assert stored.exports[0].sha256 == digest
    assert stored.exports[0].anonymized is False


def test_export_pdf(api, patent):
    report = api.build_report()
    response = api.client.get(
        f"/reports/{report['id']}/export",
        params={"format": "pdf"},
        headers={"X-User-Login": "admin"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4")
    assert response.content.rstrip().endswith(b"%%EOF")
    assert response.headers["content-disposition"].endswith('.pdf"')


def test_auditor_gets_anonymized_export(api, patent):
    report = api.expect(
        api.client.get("/reports", headers={"X-User-Login": "auditor"}), 200
    )
    assert report["rows"][0]["citizen_name"].startswith("ИГ-")

    response = api.client.get(
        f"/reports/{report['id']}/export",
        params={"format": "csv"},
        headers={"X-User-Login": "auditor"},
    )
    assert response.status_code == 200
    assert response.headers["x-export-anonymized"] == "true"
    text = response.content.decode("utf-8-sig")
    assert "Петров Иван Сергеевич" not in text
    assert "ИГ-" in text


def test_auditor_cannot_export_full_report(api, patent, container: Container):
    report = api.build_report()
    response = api.client.get(
        f"/reports/{report['id']}/export",
        params={"format": "csv", "anonymize": "false"},
        headers={"X-User-Login": "auditor"},
    )
    body = api.expect(response, 403)
    assert body["code"] == "PERSONAL_DATA_FORBIDDEN"
    denied = [
        event
        for event in container.audit.all()
        if event.action == "export_report_denied"
    ]
    assert denied, "отказ должен попадать в журнал аудита"


def test_report_with_critical_rows(api):
    created = api.register_patent(series="72 26", number="940001", issue_date="2026-07-01")
    report = api.build_report()
    assert report["critical_count"] == 1
    assert report["rows"][0]["patent"] == "72 26 940001"
    assert report["rows"][0]["critical"] is True
    assert created["patent"]["employment_deadline"] == "2026-09-01"

    only_critical = api.build_report(has_overdue="true")
    assert only_critical["row_count"] == 1


def test_export_unknown_report(api):
    response = api.client.get(
        "/reports/unknown/export", headers={"X-User-Login": "admin"}
    )
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"
