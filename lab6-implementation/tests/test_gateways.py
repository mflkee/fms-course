"""Шлюзы: формирование комплекта, регистрация доказательств, режим отказа канала.

Шлюзы не обращаются к внешним системам: квитанция и трек-номер приходят от
исполнителя и только регистрируются.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.entity.catalogs import MvdOffice
from app.entity.enums import NotificationChannel
from app.entity.notification import Notification
from app.errors import GatewayError
from app.gateway.base import FailurePolicy
from app.gateway.epgu import EpguGateway
from app.gateway.post import PostGateway

OFFICE = MvdOffice(
    code="72-001",
    name="УВМ УМВД России по Тюменской области",
    address="г. Тюмень, ул. Водопроводная, 12",
    region_code="72",
)


def make_notification() -> Notification:
    return Notification(
        contract_id="contract-1",
        channel=NotificationChannel.EPGU,
        created_at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )


def test_epgu_package_lists_enclosures_without_sending():
    gateway = EpguGateway(FailurePolicy())
    package = gateway.build_package(
        addressee=OFFICE, signed_at=date(2026, 10, 25), contract_copy_attached=True
    )
    assert package.channel == "epgu"
    assert package.addressee == OFFICE.name
    assert package.enclosures == [
        "уведомление МВД",
        "копия договора",
        "электронная подпись от 2026-10-25",
    ]


def test_epgu_registers_receipt_entered_by_executor():
    notification = make_notification()
    gateway = EpguGateway(FailurePolicy())

    receipt = gateway.register_receipt(notification, receipt_number="EPGU-99-001")
    assert receipt.number == "EPGU-99-001"
    assert receipt.channel == "epgu"


def test_epgu_failure_is_configurable():
    notification = make_notification()
    failing = EpguGateway(FailurePolicy({"epgu"}))

    with pytest.raises(GatewayError) as error:
        failing.register_receipt(notification, receipt_number="EPGU-99-001")
    assert error.value.code == "GATEWAY_ERROR"
    assert error.value.details["gateway"] == "epgu"

    # явное «не отказывать» перекрывает политику окружения
    receipt = failing.register_receipt(
        notification, receipt_number="EPGU-99-001", simulate_failure=False
    )
    assert receipt.number == "EPGU-99-001"


def test_post_package_and_track_registration():
    notification = make_notification()
    gateway = PostGateway(FailurePolicy())

    package = gateway.build_package(
        addressee=OFFICE,
        inventory="опись на 2 листах",
        sent_at=date(2026, 10, 25),
        contract_copy_attached=False,
    )
    assert package.channel == "post"
    assert package.enclosures == [
        "уведомление МВД",
        "опись вложения: опись на 2 листах (отправка 2026-10-25)",
    ]

    receipt = gateway.register_track(notification, track_number="RU123456789")
    assert receipt.number == "RU123456789"
    assert receipt.channel == "post"


def test_post_failure_is_configurable():
    notification = make_notification()
    failing = PostGateway(FailurePolicy({"post"}))

    with pytest.raises(GatewayError) as error:
        failing.register_track(notification, track_number="RU1")
    assert error.value.details["gateway"] == "post"


def test_failure_policy_reads_environment(monkeypatch):
    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "epgu, post")
    policy = FailurePolicy.from_env()
    assert policy.failing == {"epgu", "post"}
    assert policy.should_fail("epgu") is True
    assert policy.should_fail("post") is True
    assert policy.should_fail("epgu", override=False) is False

    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "all")
    assert FailurePolicy.from_env().failing == {"epgu", "post"}

    monkeypatch.setenv("FMS_GATEWAY_FAILURE", "")
    assert FailurePolicy.from_env().failing == set()
