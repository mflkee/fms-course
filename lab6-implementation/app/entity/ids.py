"""Идентификаторы сущностей."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """UUID как строка: идентификаторы не переиспользуются и не угадываются."""
    return str(uuid.uuid4())
