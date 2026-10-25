"""Репозиторий уведомлений (лаб. 5, ``РеестрУведомлений``).

История по договору не удаляется (ИНВ-8): ``history_by_contract`` возвращает
все уведомления, включая ошибочные и возвращённые.
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
        return max(history, key=lambda item: item.id)

    def by_channel(self, channel: str) -> list[Notification]:
        return self.filter(lambda notification: notification.channel.value == channel)
