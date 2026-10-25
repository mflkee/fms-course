"""Базовый in-memory репозиторий.

Интерфейс намеренно узкий: ``add``/``find``/``require``/``all``. Метода
удаления нет — это структурная реализация ИНВ-8 (уведомления и документы
хранятся бессрочно): удалить учётную сущность через репозиторий невозможно.
Замена на БД сводится к реализации этих же методов.
"""

from __future__ import annotations

from collections.abc import Callable

from app.errors import NotFoundError


class InMemoryRepository[T]:
    entity_name = "объект"

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    # --- запись ---------------------------------------------------------
    def add(self, item: T) -> T:
        self._items[item.id] = item  # type: ignore[attr-defined]
        return item

    save = add

    # --- чтение ---------------------------------------------------------
    def find(self, item_id: str) -> T | None:
        return self._items.get(item_id)

    def require(self, item_id: str, *, hint: str | None = None) -> T:
        item = self.find(item_id)
        if item is None:
            message = f"{self.entity_name} не найден: {item_id}"
            if hint:
                message = f"{message} ({hint})"
            raise NotFoundError(message, code="NOT_FOUND")
        return item

    def all(self) -> list[T]:
        return list(self._items.values())

    def filter(self, predicate: Callable[[T], bool]) -> list[T]:
        return [item for item in self._items.values() if predicate(item)]

    def count(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        """Только для тестов: сброс состояния между сценариями."""
        self._items.clear()
