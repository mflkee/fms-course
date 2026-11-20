"""Репозиторий уведомлений (``РепозиторийУведомлений``, DESIGN.md, раздел 6).

История по договору не удаляется: ``history_by_contract`` возвращает все
уведомления, включая ошибочные и возвращённые, — доказательства отправки
(DESIGN.md, раздел 1) сохраняются бессрочно.
"""

from __future__ import annotations

from app.entity.notification import Notification
from app.repository.base import InMemoryRepository


class NotificationRepository(InMemoryRepository[Notification]):
    entity_name = "уведомление МВД"

    def history_by_contract(self, contract_id: str) -> list[Notification]:
        return self.filter(
            lambda notification: notification.contract_id == contract_id
        )

    def by_contract(self, contract_id: str) -> Notification | None:
        """Действующее уведомление по договору: по контракту — ровно одно."""
        history = self.history_by_contract(contract_id)
        if not history:
            return None
        return history[-1]

    def by_channel(self, channel: str) -> list[Notification]:
        return self.filter(lambda notification: notification.channel.value == channel)
