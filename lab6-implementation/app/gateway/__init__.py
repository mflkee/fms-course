"""Слой шлюзов к внешним системам."""

from __future__ import annotations

from dataclasses import dataclass

from app.gateway.base import FailurePolicy, FnsCheckResult, Receipt
from app.gateway.epgu import EpguGateway
from app.gateway.fns import FnsGateway
from app.gateway.post import PostGateway


@dataclass(kw_only=True)
class Gateways:
    epgu: EpguGateway
    post: PostGateway
    fns: FnsGateway

    @classmethod
    def build(cls, policy: FailurePolicy | None = None) -> Gateways:
        policy = policy or FailurePolicy.from_env()
        return cls(
            epgu=EpguGateway(policy),
            post=PostGateway(policy),
            fns=FnsGateway(policy),
        )


__all__ = [
    "EpguGateway",
    "FailurePolicy",
    "FnsCheckResult",
    "FnsGateway",
    "Gateways",
    "PostGateway",
    "Receipt",
]
