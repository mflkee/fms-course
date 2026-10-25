"""Репозитории участников и учётных записей."""

from __future__ import annotations

from app.entity.people import Employer, ForeignCitizen
from app.entity.user import User
from app.errors import AuthenticationError
from app.repository.base import InMemoryRepository


class CitizenRepository(InMemoryRepository[ForeignCitizen]):
    entity_name = "иностранный гражданин"


class EmployerRepository(InMemoryRepository[Employer]):
    entity_name = "работодатель"


class UserRepository(InMemoryRepository[User]):
    entity_name = "пользователь"

    def __init__(self) -> None:
        super().__init__()
        self._by_login: dict[str, User] = {}

    def add(self, item: User) -> User:
        self._by_login[item.login] = item
        return super().add(item)

    def by_login(self, login: str) -> User | None:
        return self._by_login.get(login)

    def authenticate(self, login: str) -> User:
        user = self.by_login(login)
        if user is None:
            raise AuthenticationError(
                f"учётная запись не найдена: {login}", code="UNAUTHENTICATED"
            )
        if not user.active:
            raise AuthenticationError(
                f"учётная запись заблокирована: {login}", code="ACCOUNT_BLOCKED"
            )
        return user

    def citizen_profile(self, citizen_id: str) -> User | None:
        for user in self.all():
            if getattr(user, "citizen_id", None) == citizen_id:
                return user
        return None
