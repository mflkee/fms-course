"""Ошибки уровня приложения и их отображение в HTTP.

Предметные ошибки не знают про HTTP-коды «изнутри»: сервис бросает
``ConflictError``/``ValidationError``, а слой boundary превращает их в 409/422.
Так модель остаётся независимой от веб-фреймворка.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Базовая предметная ошибка."""

    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationFailure(DomainError):
    """Нарушены правила данных (422)."""

    status_code = 422
    code = "VALIDATION_ERROR"


class ConflictError(DomainError):
    """Ошибка состояния: действие противоречит текущему состоянию (409)."""

    status_code = 409
    code = "CONFLICT"


class NotFoundError(DomainError):
    """Сущность не найдена (404)."""

    status_code = 404
    code = "NOT_FOUND"


class ForbiddenError(DomainError):
    """Нет прав на операцию (403)."""

    status_code = 403
    code = "FORBIDDEN"


class AuthenticationError(DomainError):
    """Учётная запись не найдена или неактивна (401)."""

    status_code = 401
    code = "UNAUTHENTICATED"


class GatewayError(DomainError):
    """Внешняя система (ЕПГУ, Почта, ФНС) вернула ошибку (502)."""

    status_code = 502
    code = "GATEWAY_ERROR"


class EmptySelectionError(DomainError):
    """Выборка для отчёта пуста — отчёт не формируется (404 по контракту лаб. 3)."""

    status_code = 404
    code = "EMPTY_SELECTION"
