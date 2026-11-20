"""Общая часть шлюзов ЕПГУ и Почты России.

Шлюз — формирователь комплекта и регистратор доказательств, а не транспорт.
Система ничего не отправляет и ни с кем не интегрируется (DESIGN.md, раздел 1):

* ``build_package`` формирует комплект (уведомление, копия договора, опись
  или подпись) — текст для исполнителя, без обращения к внешней системе;
* ``register_receipt`` / ``register_track`` регистрируют квитанцию ЕПГУ или
  трек-номер Почты, которые ввёл исполнитель после фактической отправки.

Отказ канала (по данным исполнителя) имитируется так же, как раньше:

* окружение ``FMS_GATEWAY_FAILURE=epgu,post`` (или ``all``) — отказ на уровне
  приложения;
* флаг ``simulate_failure`` в запросе — отказ на уровне одного вызова.

Оба режима дают ``GatewayError`` → HTTP 502; вызывающий сервис оставляет
задачу открытой и сохраняет доказательство неудачной попытки.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.errors import GatewayError

GATEWAY_FAILURE_ENV = "FMS_GATEWAY_FAILURE"
GATEWAY_NAMES = {"epgu", "post"}


class FailurePolicy:
    """Решение «канал отказал в регистрации отправления?»."""

    def __init__(self, failing: set[str] | None = None) -> None:
        self._failing = {item.strip().lower() for item in (failing or set()) if item.strip()}

    @classmethod
    def from_env(cls, variable: str = GATEWAY_FAILURE_ENV) -> FailurePolicy:
        raw = os.environ.get(variable, "")
        names = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
        if {"all", "*", "1", "true", "yes"} & names:
            names = set(GATEWAY_NAMES)
        return cls(names)

    @property
    def failing(self) -> set[str]:
        return set(self._failing)

    def should_fail(self, gateway: str, override: bool | None = None) -> bool:
        if override is True:
            return True
        if override is False:
            return False
        return gateway.lower() in self._failing

    def require_available(self, gateway: str, override: bool | None = None) -> None:
        if self.should_fail(gateway, override):
            raise GatewayError(
                f"канал «{gateway}» не принял отправление (режим имитации отказа)",
                code="GATEWAY_ERROR",
                details={"gateway": gateway, "mode": "simulated_failure"},
            )


@dataclass(kw_only=True)
class Package:
    """Комплект для исполнителя: что приложить и кому направить."""

    channel: str
    addressee: str
    enclosures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "addressee": self.addressee,
            "enclosures": list(self.enclosures),
        }


@dataclass(kw_only=True)
class Receipt:
    """Зарегистрированное доказательство: квитанция ЕПГУ или трек-номер Почты."""

    number: str
    registered_at: datetime
    channel: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "registered_at": self.registered_at.isoformat(),
            "channel": self.channel,
            "detail": self.detail,
        }


def utc_now() -> datetime:
    return datetime.now(UTC)
