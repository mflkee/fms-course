"""Денежные суммы: Decimal, две знака после запятой, без float-погрешностей."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - защита от мусора
        raise ValueError(f"некорректная сумма: {value!r}") from exc
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def money_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(money(value))


def money_equals(left: Decimal, right: Decimal) -> bool:
    return money(left) == money(right)


def shortfall(expected: Decimal, actual: Decimal) -> Decimal:
    """Сколько не хватает до ожидаемой суммы (0, если хватает)."""
    diff = money(expected) - money(actual)
    return diff if diff > 0 else Decimal("0.00")
