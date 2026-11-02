"""Lossless commits_count normalization for classifier exports only."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext

_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_INTEGER = re.compile(r"[+-]?[0-9]+")


@dataclass(frozen=True)
class _NormalizedCount:
    value: str
    status: str
    reason: str = ""


def _analyze(value: object) -> _NormalizedCount:
    if value is None:
        return _NormalizedCount("", "missing")
    # bool is an int subclass, but is not a recorded commit count.
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return _NormalizedCount("", "invalid", "non_numeric_type")
    text = format(Decimal(value), "f") if isinstance(value, int) else str(value).strip()
    if text.casefold() in {"", "null", "nan"}:
        return _NormalizedCount("", "missing")
    try:
        # Invalid strings remain invalid even if the caller disabled this trap.
        with localcontext() as context:
            context.traps[InvalidOperation] = True
            number = Decimal.from_float(value) if isinstance(value, float) else Decimal(text)
    except InvalidOperation:
        return _NormalizedCount("", "invalid", "non_numeric")
    if number.is_nan():
        return _NormalizedCount("", "missing")
    if not number.is_finite():
        return _NormalizedCount("", "invalid", "non_finite")
    if not _NUMBER.fullmatch(text):
        return _NormalizedCount("", "invalid", "non_numeric")
    if number < 0:
        return _NormalizedCount("", "invalid", "negative")
    integral = number.to_integral_value()
    if number != integral:
        return _NormalizedCount("", "invalid", "fractional")
    # Decimal construction and fixed-point formatting do not use context precision.
    exported = "0" if number.is_zero() else format(integral, "f")
    status = "integers_preserved" if _INTEGER.fullmatch(text) else "decimal_representations_converted"
    return _NormalizedCount(exported, status)


def normalize_commits_count(value: object) -> str:
    """Return a canonical nonnegative integer, or an empty cell; never round.

    None, blank/whitespace, null (case insensitive) and NaN are missing.
    Negative, fractional, infinite and nonnumeric values are invalid. Decimal
    strings and integers never pass through float, including very large counts.
    """
    return _analyze(value).value


def audit_commits_count(values: Iterable[tuple[str, object]]) -> dict:
    """Count disjoint outcomes; zeros are an overlapping subset of valid values."""
    audit = dict.fromkeys(("total", "valid", "integers_preserved", "decimal_representations_converted",
                          "zeros_preserved", "missing", "invalid"), 0)
    audit["invalid_records"] = []
    for uid, original in values:
        result = _analyze(original)
        audit["total"] += 1
        audit[result.status] += 1
        if result.value:
            audit["valid"] += 1
            audit["zeros_preserved"] += result.value == "0"
        elif result.status == "invalid":
            audit["invalid_records"].append({"sampling_unit_id": uid, "original_value": str(original),
                                             "reason": result.reason})
    return audit
