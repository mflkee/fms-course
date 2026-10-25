"""Операции 11–13: учёт НДФЛ, ручное подтверждение и прекращение из-за неуплаты."""

from __future__ import annotations

from datetime import date

from app.container import Container
from app.entity.enums import PointKind


def test_register_payment_confirms_and_updates_patent(api, patent, container: Container):
    result = api.pay(patent["patent"]["id"], period="2026-10")
    payment = result["payment"]

    assert payment["status"] == "confirmed"
    assert payment["amount"] == "6000.00"
    assert payment["input_source"] == "fns"
    assert payment["manual"] is False
    assert result["confirmed"] is True
    assert result["patent"]["paid_until"] == "2026-10-31"
    assert result["patent"]["status"] == "paid_until"
    assert result["deadline_point"]["status"] == "done"

    open_ndfl = [
        point
        for point in container.points.open_by_patent(patent["patent"]["id"])
        if point.kind is PointKind.PAY_NDFL
    ]
    assert len(open_ndfl) == 1
    assert open_ndfl[0].planned_date.isoformat() == "2026-11-30"


def test_payment_amount_must_match_region_cost(api, patent):
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-10",
            "amount": "5000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-1",
            "document": {"filename": "cheque.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "INV-7"
    assert body["details"]["expected"] == "6000.00"
    assert body["details"]["shortfall"] == "1000.00"


def test_payment_continuity_gap_rejected(api, patent):
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-12",
            "amount": "6000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-12",
            "document": {"filename": "cheque.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "INV-5"
    assert body["details"]["expected_period"] == "2026-10"


def test_payment_is_idempotent(api, patent, container: Container):
    first = api.pay(patent["patent"]["id"], period="2026-10")
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-10",
            "amount": "6000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-repeat",
            "document": {"filename": "cheque-repeat.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    second = api.expect(response, 200)
    assert second["idempotent"] is True
    assert second["payment"]["id"] == first["payment"]["id"]
    assert len(container.payments.by_patent(patent["patent"]["id"])) == 1


def test_payment_not_found_then_confirmed_manually(api, patent):
    registered = api.pay(patent["patent"]["id"], fns_status="not_found")
    assert registered["confirmed"] is False
    assert registered["payment"]["status"] == "not_found"
    assert registered["patent"]["paid_until"] is None

    response = api.client.post(
        f"/payments/{registered['payment']['id']}/confirm",
        json={
            "source": "bank",
            "document": {"filename": "bank-confirmation.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    confirmed = api.expect(response, 200)
    assert confirmed["payment"]["status"] == "confirmed"
    assert confirmed["payment"]["manual"] is True
    assert confirmed["payment"]["input_source"] == "bank"
    assert confirmed["patent"]["paid_until"] == "2026-10-31"


def test_returned_payment_is_not_counted(api, patent):
    registered = api.pay(patent["patent"]["id"], fns_status="returned")
    assert registered["confirmed"] is False
    assert registered["payment"]["status"] == "returned"
    assert registered["patent"]["paid_until"] is None


def test_payment_gateway_failure_is_visible(api, patent, container: Container):
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2026-10",
            "amount": "6000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-fail",
            "document": {"filename": "cheque.pdf"},
            "simulate_failure": True,
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 502)
    assert body["code"] == "GATEWAY_ERROR"
    payment = container.payments.require(body["details"]["payment_id"])
    assert payment.status.value == "not_found"
    assert "ФНС недоступна" in payment.fns_detail


def test_confirm_already_confirmed_payment(api, patent):
    paid = api.pay(patent["patent"]["id"], period="2026-10")
    response = api.client.post(
        f"/payments/{paid['payment']['id']}/confirm",
        json={"source": "manual", "document": {"filename": "doc.pdf"}},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "PAYMENT_ALREADY_CONFIRMED"


def test_payment_period_outside_patent_term(api, patent):
    response = api.client.post(
        "/payments",
        json={
            "patent_id": patent["patent"]["id"],
            "period": "2028-01",
            "amount": "6000.00",
            "payment_date": "2026-10-25",
            "document_number": "PP-out",
            "document": {"filename": "cheque.pdf"},
        },
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "PERIOD_OUT_OF_TERM"


def test_terminate_nonpayment_closes_points(api, patent, clock, container: Container):
    api.pay(patent["patent"]["id"], period="2026-10")
    clock.set_today(date(2026, 11, 15))

    response = api.client.post(
        f"/patents/{patent['patent']['id']}/terminate-nonpayment",
        json={"detected_at": "2026-11-15"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 200)
    assert body["patent"]["status"] == "terminated_nonpayment"
    assert body["patent"]["termination_date"] == "2026-11-15"
    assert body["patent"]["paid_until"] == "2026-10-31"
    assert body["cancelled_deadline_points"] >= 1
    assert body["fns_confirmation"]["found"] is False
    assert all(point.is_closed() for point in container.points.by_patent(patent["patent"]["id"]))


def test_terminate_nonpayment_requires_paid_period(api, patent):
    response = api.client.post(
        f"/patents/{patent['patent']['id']}/terminate-nonpayment",
        json={"detected_at": "2026-10-25"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "NO_PAID_PERIOD"


def test_terminate_nonpayment_too_early(api, patent, clock):
    api.pay(patent["patent"]["id"], period="2026-10")
    clock.set_today(date(2026, 10, 26))
    response = api.client.post(
        f"/patents/{patent['patent']['id']}/terminate-nonpayment",
        json={"detected_at": "2026-10-26"},
        headers={"X-User-Login": "admin"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "PAYMENT_PERIOD_NOT_EXPIRED"
