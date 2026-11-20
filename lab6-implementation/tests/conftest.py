"""Общие фикстуры: контейнер с неподвижными часами, приложение и API-хелпер."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.container import Container, build_container
from app.entity.clock import FixedClock
from app.gateway.base import FailurePolicy
from app.main import create_app
from app.seed import seed_demo_data

TODAY = date(2026, 10, 25)


class Api:
    """Короткие вызовы эндпоинтов с проверкой ожидаемого статуса."""

    def __init__(self, client: TestClient, container: Container) -> None:
        self.client = client
        self.container = container
        self._counter = 0

    # --- утилиты --------------------------------------------------------
    @staticmethod
    def expect(response, *codes: int) -> dict:
        expected = codes or (200,)
        assert response.status_code in expected, (
            f"ожидался статус {expected}, получен {response.status_code}: {response.text}"
        )
        return response.json()

    @property
    def citizen_id(self) -> str:
        return self.container.citizens.all()[0].id

    @property
    def employer_id(self) -> str:
        return self.container.employers.all()[0].id

    def _next_requisites(self) -> tuple[str, str]:
        self._counter += 1
        return "72 26", f"{self._counter:06d}"

    # --- операции -------------------------------------------------------
    def register_patent(self, **overrides) -> dict:
        series, number = self._next_requisites()
        payload = {
            "citizen_id": self.citizen_id,
            "series": series,
            "number": number,
            "issue_date": "2026-10-01",
            "region_code": "72",
            "activity_codes": ["driver"],
            "issuing_authority": "УВМ УМВД России по Тюменской области",
            "scan": {"filename": f"patent-{number}.pdf"},
        }
        payload.update(overrides)
        response = self.client.post("/patents", json=payload)
        return self.expect(response, 201)

    def conclude(self, patent_id: str, **overrides) -> dict:
        payload = {
            "patent_id": patent_id,
            "employer_id": self.employer_id,
            "activity_code": "driver",
            "conclusion_date": "2026-10-05",
            "kind": "employment",
            "position": "Водитель автомобиля",
            "document": {"filename": "dogovor.pdf"},
        }
        payload.update(overrides)
        response = self.client.post("/contracts", json=payload)
        return self.expect(response, 201)

    def notify(self, contract_id: str, **overrides) -> dict:
        payload = {
            "contract_id": contract_id,
            "channel": "epgu",
            "confirmation": {"signature": "SIGNATURE-1"},
        }
        payload.update(overrides)
        response = self.client.post("/notifications", json=payload)
        return self.expect(response, 201)

    def remind(self, **overrides) -> dict:
        payload = {
            "citizen_id": self.citizen_id,
            "channels": ["email"],
            "days": [30, 14, 7, 3, 1],
            "consent": True,
        }
        payload.update(overrides)
        response = self.client.put("/reminder-settings", json=payload)
        return self.expect(response, 200)

    def archive(self, patent_id: str, **overrides) -> dict:
        payload = {"basis": "new_patent", "reason": "выдан новый патент"}
        payload.update(overrides)
        response = self.client.post(f"/patents/{patent_id}/archive", json=payload)
        return self.expect(response, 200)

    def recalculate(self, patent_id: str, **overrides) -> dict:
        payload = {"reason": "контроль сроков"}
        payload.update(overrides)
        response = self.client.post(f"/patents/{patent_id}/recalculate", json=payload)
        return self.expect(response, 200)

    def violate(self, point_id: str, detected_at: str = "2026-10-25") -> dict:
        response = self.client.post(
            f"/deadline-points/{point_id}/violation", json={"detected_at": detected_at}
        )
        return self.expect(response, 200)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(TODAY)


@pytest.fixture
def container(clock: FixedClock) -> Container:
    built = build_container(clock=clock, policy=FailurePolicy())
    return seed_demo_data(built)


@pytest.fixture
def app(container: Container):
    return create_app(container, seed=False)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def api(client: TestClient, container: Container) -> Api:
    return Api(client, container)


@pytest.fixture
def patent(api: Api) -> dict:
    return api.register_patent()


@pytest.fixture
def contract(api: Api, patent: dict) -> dict:
    return api.conclude(patent["patent"]["id"])


@pytest.fixture
def notified(api: Api, contract: dict) -> dict:
    return api.notify(contract["contract"]["id"])
