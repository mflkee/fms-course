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
    assert body["escalation_reminder"]["status"] == "scheduled"
    assert body["escalation_reminder"]["channel"] == "personal_account"
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


def _due(api) -> dict:
    return api.expect(
        api.client.get("/reminders/due", params={"citizen_id": api.citizen_id}), 200
    )


def test_due_reminders_are_shown_and_stay_while_point_is_open(api, patent):
    # 37 дней до срока 2026-12-01 — момент напоминания совпадает с сегодняшним днём
    api.remind(days=[37])

    first = _due(api)
    assert first["today"] == "2026-10-25"
    assert first["count"] == 2
    assert {reminder["status"] for reminder in first["reminders"]} == {"shown"}
    assert all(reminder["sent_at"] for reminder in first["reminders"])

    # показанное остаётся актуальным, пока точка открыта; повторный вызов безопасен
    second = _due(api)
    assert second["count"] == 2


def test_escalation_reminder_appears_in_cabinet(api):
    created = api.register_patent(series="72 26", number="930003", issue_date="2026-07-01")
    conclude_point = next(
        point
        for point in created["deadline_points"]
        if point["kind"] == "conclude_contract"
    )
    api.violate(conclude_point["id"], "2026-10-25")

    body = _due(api)
    escalations = [reminder for reminder in body["reminders"] if reminder["escalation"]]
    assert len(escalations) == 1
    assert escalations[0]["point_id"] == conclude_point["id"]
    assert escalations[0]["status"] == "shown"


def test_reminders_of_closed_point_are_skipped_not_shown(api, patent, container: Container):
    api.remind(days=[37])
    points = {point["kind"]: point["id"] for point in patent["deadline_points"]}
    api.conclude(patent["patent"]["id"])

    body = _due(api)
    assert {reminder["point_id"] for reminder in body["reminders"]} == {
        points["send_notification"]
    }
    own = container.reminders.by_point(points["conclude_contract"])
    assert own
    assert all(item.status.value == "skipped" for item in own)
    assert all(item.skip_reason == "контрольная точка выполнена" for item in own)


def test_due_reminders_unknown_citizen(api):
    response = api.client.get("/reminders/due", params={"citizen_id": "unknown"})
    body = api.expect(response, 404)
    assert body["code"] == "NOT_FOUND"
