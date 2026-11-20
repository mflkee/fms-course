"""Операции 8–10: напоминания, пересчёт сроков и фиксация нарушения."""

from __future__ import annotations

from app.container import Container
from app.entity.enums import PointKind


def test_configure_reminders_creates_for_open_points(api, patent, container: Container):
    body = api.remind(channels=["email", "sms"], days=[30, 7, 1])

    assert body["settings"]["channels"] == ["email", "sms"]
    assert body["settings"]["days"] == [30, 7, 1]
    assert body["settings"]["consent"] is True
    assert body["reminders_count"] > 0

    open_point_ids = {
        point.id for point in container.points.open_by_patent(patent["patent"]["id"])
    }
    assert all(
        reminder["point_id"] in open_point_ids for reminder in body["reminders_created"]
    )
    assert all(
        reminder["planned_at"] >= "2026-10-25"
        for reminder in body["reminders_created"]
    )

    # повторная настройка не создаёт дублей активных напоминаний
    api.remind(channels=["email", "sms"], days=[30, 7, 1])
    scheduled = container.reminders.scheduled()
    keys = [(reminder.point_id, reminder.days_before) for reminder in scheduled]
    assert len(keys) == len(set(keys))

    # отзыв согласия снимает запланированные напоминания
    api.remind(channels=["email"], days=[30, 7, 1], consent=False)
    assert container.reminders.scheduled() == []


def test_configure_reminders_skips_closed_points(api, patent, contract, container):
    body = api.remind(days=[30, 14])
    assert body["skipped_closed_points"] >= 1
    conclude_point = container.points.latest_by_kind(
        patent["patent"]["id"], PointKind.CONCLUDE_CONTRACT
    )
    assert conclude_point.is_closed()
    assert all(
        reminder.point_id != conclude_point.id for reminder in container.reminders.all()
    )


def test_configure_reminders_requires_channels(api):
    response = api.client.put(
        "/reminder-settings",
        json={"citizen_id": api.citizen_id, "channels": [], "days": [30]},
    )
    body = api.expect(response, 422)
    assert body["code"] == "REQUEST_VALIDATION_ERROR"


def test_configure_reminders_unknown_citizen(api):
    response = api.client.put(
        "/reminder-settings",
        json={"citizen_id": "unknown", "channels": ["email"], "days": [30]},
    )
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"


def test_recalculate_marks_overdue_and_critical(api, container: Container):
    created = api.register_patent(series="72 26", number="930001", issue_date="2026-07-01")
    patent_id = created["patent"]["id"]

    body = api.recalculate(patent_id, reason="ежедневный контроль")
    summary = body["summary"]

    assert summary["employment_deadline"] == "2026-09-01"
    assert summary["counts"]["overdue"] >= 2
    overdue_kinds = {point["kind"] for point in summary["overdue"]}
    assert {"conclude_contract", "send_notification"} <= overdue_kinds
    assert all(point["status"] == "overdue" for point in summary["overdue"])
    assert all(point["critical"] for point in summary["overdue"])


def test_recalculate_keeps_closed_points_closed(api, patent, contract):
    body = api.recalculate(patent["patent"]["id"])
    open_points = body["summary"]["open"]
    assert all(point["kind"] != "conclude_contract" for point in open_points)
    assert {point["kind"] for point in open_points} == {
        "send_notification",
        "extend_patent",
    }


def test_recalculate_reschedules_reminders(api, patent):
    api.remind(days=[30, 7])
    body = api.recalculate(patent["patent"]["id"], reason="после изменения сроков")
    assert body["summary"]["counts"]["open"] == 3
    assert body["reason"] == "после изменения сроков"


def test_register_violation_creates_escalation(api):
    created = api.register_patent(series="72 26", number="930002", issue_date="2026-07-01")
    conclude_point = next(
        point
        for point in created["deadline_points"]
        if point["kind"] == "conclude_contract"
    )

    body = api.violate(conclude_point["id"], "2026-10-25")
    assert body["deadline_point"]["status"] == "overdue"
    assert body["deadline_point"]["critical"] is True
    assert body["deadline_point"]["violation_date"] == "2026-10-25"
    assert body["escalation_reminder"]["escalation"] is True
    assert body["escalation_reminder"]["status"] == "delivered"
    assert body["escalation_reminder"]["point_id"] == conclude_point["id"]


def test_register_violation_when_not_yet_due(api, patent):
    conclude_point = next(
        point
        for point in patent["deadline_points"]
        if point["kind"] == "conclude_contract"
    )
    response = api.client.post(
        f"/deadline-points/{conclude_point['id']}/violation",
        json={"detected_at": "2026-10-25"},
    )
    body = api.expect(response, 422)
    assert body["code"] == "POINT_NOT_OVERDUE"
    assert body["details"]["planned_date"] == "2026-12-01"

    future = api.client.post(
        f"/deadline-points/{conclude_point['id']}/violation",
        json={"detected_at": "2026-12-31"},
    )
    assert api.expect(future, 422)["code"] == "DATE_IN_FUTURE"


def test_register_violation_on_closed_point(api, patent, contract):
    conclude_point = next(
        point
        for point in patent["deadline_points"]
        if point["kind"] == "conclude_contract"
    )
    response = api.client.post(
        f"/deadline-points/{conclude_point['id']}/violation",
        json={"detected_at": "2026-10-25"},
    )
    body = api.expect(response, 409)
    assert body["code"] == "POINT_CLOSED"


def test_deadline_points_of_patent_are_listed(api, patent):
    body = api.expect(
        api.client.get(f"/patents/{patent['patent']['id']}/deadline-points"), 200
    )
    assert body["patent_id"] == patent["patent"]["id"]
    assert {point["kind"] for point in body["points"]} == {
        "conclude_contract",
        "send_notification",
        "extend_patent",
    }
    assert body["summary"]["counts"]["open"] == 3
