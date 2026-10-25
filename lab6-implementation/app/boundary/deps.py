"""Зависимости boundary-слоя: контейнер и текущий пользователь."""

from __future__ import annotations

from fastapi import Depends, Header, Request

from app.container import Container
from app.entity.user import User

DEFAULT_LOGIN = "admin"


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_actor(
    container: Container = Depends(get_container),
    x_user_login: str | None = Header(default=None, alias="X-User-Login"),
) -> User:
    """Учебная аутентификация: логин из заголовка, по умолчанию — администратор."""
    return container.access.resolve(x_user_login or DEFAULT_LOGIN)
