"""Права доступа (лаб. 5, ``МодульПравДоступа``).

Аутентификация упрощена до заголовка ``X-User-Login``: в учебной системе нет
ни паролей, ни внешнего IdP. Матрица прав при этом настоящая: роль решает,
какие операции доступны, а право на персональные данные — отдельное право.
"""

from __future__ import annotations

from app.entity.enums import Role
from app.entity.user import SystemAdministrator, User
from app.errors import ForbiddenError
from app.repository.people import UserRepository


class AccessService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    # --- аутентификация -------------------------------------------------
    def resolve(self, login: str) -> User:
        return self._users.authenticate(login)

    # --- роли -----------------------------------------------------------
    def require_role(self, user: User | None, *roles: Role) -> User:
        if user is None:
            raise ForbiddenError(
                "операция доступна только аутентифицированному пользователю",
                code="FORBIDDEN",
            )
        if user.role not in roles:
            allowed = ", ".join(role.value for role in roles)
            raise ForbiddenError(
                f"роль «{user.role.value}» не имеет права на операцию (требуется: {allowed})",
                code="FORBIDDEN",
                details={"role": user.role.value, "required_roles": allowed},
            )
        return user

    def require_citizen(self, user: User | None) -> User:
        return self.require_role(user, Role.CITIZEN, Role.ADMIN)

    def require_employer_rep(self, user: User | None) -> User:
        """Представитель работодателя или администратор (системный вызов)."""
        return self.require_role(user, Role.EMPLOYER_REP, Role.ADMIN)

    def require_employer_or_admin(self, user: User | None) -> User:
        return self.require_role(user, Role.EMPLOYER_REP, Role.ADMIN)

    def require_admin(self, user: User | None) -> SystemAdministrator:
        resolved = self.require_role(user, Role.ADMIN)
        return resolved  # type: ignore[return-value]

    # --- отдельные права ------------------------------------------------
    def require_export_right(self, user: User | None) -> SystemAdministrator:
        admin = self.require_admin(user)
        if not admin.may_export():
            raise ForbiddenError(
                "у администратора нет права на выгрузку отчётов",
                code="EXPORT_FORBIDDEN",
            )
        return admin

    def may_see_personal_data(self, user: User | None) -> bool:
        return bool(
            user is not None
            and user.role is Role.ADMIN
            and isinstance(user, SystemAdministrator)
            and user.may_see_personal_data()
        )

    def require_personal_data_right(self, user: User | None) -> None:
        if not self.may_see_personal_data(user):
            raise ForbiddenError(
                "нет права на персональные данные: выгрузка возможна только в обезличенном виде",
                code="PERSONAL_DATA_FORBIDDEN",
            )

    # --- владение объектом ----------------------------------------------
    def ensure_citizen_owns(self, user: User, citizen_id: str) -> None:
        if user.role is Role.CITIZEN and getattr(user, "citizen_id", None) != citizen_id:
            raise ForbiddenError(
                "иностранный гражданин может работать только со своим патентном",
                code="FORBIDDEN",
                details={"citizen_id": citizen_id},
            )
