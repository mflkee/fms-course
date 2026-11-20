"""Слой шлюзов (DESIGN.md, раздел 6: ``ШлюзЕПГУ``, ``ШлюзПочты``).

Шлюзы формируют комплект и регистрируют доказательства, которые ввёл
исполнитель. Внешних вызовов нет.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.gateway.base import FailurePolicy, Package, Receipt
from app.gateway.epgu import EpguGateway
from app.gateway.post import PostGateway


@dataclass(kw_only=True)
class Gateways:
    epgu: EpguGateway
    post: PostGateway

    @classmethod
    def build(cls, policy: FailurePolicy | None = None) -> Gateways:
        policy = policy or FailurePolicy.from_env()
        return cls(
            epgu=EpguGateway(policy),
            post=PostGateway(policy),
        )


__all__ = [
    "EpguGateway",
    "FailurePolicy",
    "Gateways",
    "Package",
    "PostGateway",
    "Receipt",
]
