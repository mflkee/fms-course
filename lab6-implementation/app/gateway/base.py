"""Общая часть шлюзов к внешним системам (ЕПГУ, Почта России, ФНС).

Шлюз — единственное место, где модель соприкасается с внешним миром.
Заглушки отвечают предсказуемо (детерминированные номера квитанций и
трек-номеров) и умеют имитировать отказ источника:

* окружение ``FMS_GATEWAY_FAILURE=epgu,post,fns`` (или ``all``) — отказ на
  уровне приложения;
* флаг ``simulate_failure`` в запросе — отказ на уровне одного вызова.

Оба режима дают ``GatewayError`` → HTTP 502; вызывающий сервис оставляет
задачу открытой и сохраняет доказательство неудачной попытки (ИНВ-8).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.errors import GatewayError

GATEWAY_FAILURE_ENV = "FMS_GATEWAY_FAILURE"


class FailurePolicy:
    """Решение «источник должен вернуть ошибку?»."""

    def __init__(self, failing: set[str] | None = None) -> None:
        self._failing = {item.strip().lower() for item in (failing or set()) if item.strip()}

    @classmethod
    def from_env(cls, variable: str = GATEWAY_FAILURE_ENV) -> FailurePolicy:
        raw = os.environ.get(variable, "")
        names = {chunk.strip().lower() for chunk in raw.split(",") if chunk.strip()}
        if {"all", "*", "1", "true", "yes"} & names:
            names = {"epgu", "post", "fns"}
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
                f"источник «{gateway}» вернул ошибку (режим имитации отказа)",
                code="GATEWAY_ERROR",
                details={"gateway": gateway, "mode": "simulated_failure"},
            )


def deterministic_number(prefix: str, seed: str, width: int = 10) -> str:
    """Предсказуемый номер доказательства: одинаковый вход → одинаковый номер."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    return f"{prefix}-{digest[:width]}"


@dataclass(kw_only=True)
class Receipt:
    """Квитанция ЕПГУ или трек-номер почтового отправления."""

    number: str
    issued_at: datetime
    channel: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "issued_at": self.issued_at.isoformat(),
            "channel": self.channel,
            "detail": self.detail,
        }


@dataclass(kw_only=True)
class FnsCheckResult:
    """Результат сверки платежа с состоянием расчётов ФНС."""

    found: bool
    detail: str
    checked_at: date

    def to_dict(self) -> dict:
        return {"found": self.found, "detail": self.detail, "checked_at": self.checked_at.isoformat()}


def utc_now() -> datetime:
    return datetime.now(UTC)
