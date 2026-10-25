"""Шлюзы: предсказуемые ответы, детерминированные доказательства, режим отказа."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.entity.catalogs import MvdOffice
from app.entity.enums import NotificationChannel
from app.entity.notification import Notification
from app.errors import GatewayError
from app.gateway.base import FailurePolicy
from app.gateway.epgu import EpguGateway
from app.gateway.fns import FnsGateway
from app.gateway.post import PostGateway


def make_notification() -> Notification:
    return Notification(
        contract_id="contract-1",
        channel=NotificationChannel.EPGU,
        created_at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )


def test_epgu_receipt_is_deterministic_and_failure_is_configurable():
    notification = make_notification()
    gateway = EpguGateway(FailurePolicy())

    first = gateway.send(notification, signature="SIG", signed_at=date(2026, 10, 25))
    second = gateway.send(notification, signature="SIG", signed_at=date(2026, 10, 25))
    assert first.number == second.number
    assert first.number.startswith("EPGU-")

    failing = EpguGateway(FailurePolicy({"epgu"}))
    with pytest.raises(GatewayError) as error:
        failing.send(notification, signature="SIG", signed_at=date(2026, 10, 25))
    assert error.value.code == "GATEWAY_ERROR"
    assert error.value.details["gateway"] == "epgu"

    # явное «не отказывать» перекрывает политику окружения
    receipt = failing.send(
        notification,
        signature="SIG",
        signed_at=date(2026, 10, 25),
        simulate_failure=False,
    )
    assert receipt.number == first.number


def test_post_gateway_returns_track_number_and_document():
    notification = make_notification()
    gateway = PostGateway(FailurePolicy())
    office = MvdOffice(
        code="72-001",
        name="УВМ УМВД России по Тюменской области",
        address="г. Тюмень, ул. Водопроводная, 12",
        region_code="72",
    )

    receipt = gateway.send(
        notification,
        addressee=office,
        inventory="опись на 2 листах",
        sent_at=date(2026, 10, 25),
    )
    assert receipt.number.startswith("RU-")
    assert "опись" in receipt.detail

    document = gateway.return_document(receipt.number)
    assert document.filename.startswith("return-")
    assert document.owner_type == "notification"


def test_fns_gateway_statuses():
    gateway = FnsGateway(FailurePolicy())
    common = {
        "inn": "770123456789",
        "period": "2026-10",
        "amount": Decimal("6000.00"),
        "on_date": date(2026, 10, 25),
    }
    assert gateway.check_payment(**common).found is True
    not_found = gateway.check_payment(**common, simulate_status="not_found")
    assert not_found.found is False
    assert "не найдено" in not_found.detail
    returned = gateway.check_payment(**common, simulate_status="returned")
    assert returned.found is False
    assert "возвращён" in returned.detail
    assert gateway.confirm_absence(inn="770123456789", period="2026-11", on_date=date(2026, 10, 25)).found is False


def test_failure_policy_reads_environment(monkeypatch):
    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "epgu, post")
    policy = FailurePolicy.from_env()
    assert policy.failing == {"epgu", "post"}
    assert policy.should_fail("epgu") is True
    assert policy.should_fail("fns") is False
    assert policy.should_fail("epgu", override=False) is False

    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "all")
    assert FailurePolicy.from_env().failing == {"epgu", "post", "fns"}

    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "")
    assert FailurePolicy.from_env().failing == set()
