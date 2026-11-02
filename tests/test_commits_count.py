"""Classifier-only count semantics, exact arithmetic and normalization evidence."""

from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext

import pytest

from web3blockset_sampling.normalization import audit_commits_count, normalize_commits_count


@pytest.mark.parametrize("value,expected", [
    (0, "0"), (0.0, "0"), ("0.0", "0"), ("-0.0", "0"), ("000", "0"),
    (1, "1"), (1.0, "1"), (5, "5"), (5.0, "5"), (12.0, "12"), (100, "100"),
    ("1", "1"), ("5.0", "5"), ("12.000", "12"), (" 0005.00 ", "5"),
    ("+5", "5"), ("5e2", "500"), ("500e-2", "5"), (".0", "0"),
    (Decimal("12.0"), "12"), (Decimal("0"), "0"),
    (None, ""), (float("nan"), ""), (Decimal("NaN"), ""), ("NaN", ""),
    ("", ""), ("   ", ""), ("\t\r\n", ""), ("null", ""), (" NULL ", ""),
    ("abc", ""), (-1, ""), ("-1", ""), (Decimal("-0.001"), ""),
    (2.5, ""), ("2.5", ""), (Decimal("2.5"), ""), ("1e-100", ""),
    ("1.0000000000000000000000000000000000000001", ""),
    (float("inf"), ""), (float("-inf"), ""), ("Infinity", ""), ("-Infinity", ""),
    (Decimal("Infinity"), ""), ("1_000", ""), ("1,000", ""), ("5 0", ""),
    (True, ""), (False, ""), ([], ""), ({}, ""), (object(), ""), (1 + 0j, ""), (b"5", ""),
    (9007199254740993, "9007199254740993"),
    (1.0000000000000001e18, "1000000000000000128"),
    ("900719925474099312345678901234567890.0", "900719925474099312345678901234567890"),
    (Decimal("900719925474099312345678901234567890.0"), "900719925474099312345678901234567890"),
    (10**100, "1" + "0" * 100), ("1e100", "1" + "0" * 100),
])
def test_normalize_commits_count(value, expected):
    assert normalize_commits_count(value) == expected
    assert normalize_commits_count(value) == expected  # Deterministic for the same input.
    if expected:
        assert expected.isascii() and expected.isdigit()
        assert normalize_commits_count(expected) == expected


def test_large_values_are_exact_even_with_restrictive_decimal_context():
    original = "12345678901234567890123456789012345678901234567890"
    with localcontext() as context:
        context.prec = 3
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert normalize_commits_count(original + ".000") == original
        assert normalize_commits_count(original + ".00000000000000000000001") == ""
        assert normalize_commits_count("1e1000") == "1" + "0" * 1000


def test_audit_partitions_values_and_records_invalid_occurrence_ids():
    values = [("a", 0), ("b", "5"), ("c", "0.0"), ("d", "5.0"),
              ("e", None), ("f", "null"), ("g", "NaN"), ("h", "  "),
              ("i", "abc"), ("j", -1), ("k", "2.5"), ("l", "Infinity")]
    audit = audit_commits_count(values)
    assert audit == {
        "total": 12, "valid": 4, "integers_preserved": 2, "decimal_representations_converted": 2,
        "zeros_preserved": 2, "missing": 4, "invalid": 4,
        "invalid_records": [
            {"sampling_unit_id": "i", "original_value": "abc", "reason": "non_numeric"},
            {"sampling_unit_id": "j", "original_value": "-1", "reason": "negative"},
            {"sampling_unit_id": "k", "original_value": "2.5", "reason": "fractional"},
            {"sampling_unit_id": "l", "original_value": "Infinity", "reason": "non_finite"},
        ],
    }
    assert audit_commits_count(iter(values)) == audit
    assert values[2] == ("c", "0.0")


def test_invalid_values_stay_invalid_with_decimal_traps_disabled():
    with localcontext() as context:
        context.traps[InvalidOperation] = False
        audit = audit_commits_count([("bad", "abc"), ("nan", Decimal("NaN"))])
        assert audit["missing"] == audit["invalid"] == 1
        assert normalize_commits_count("abc") == ""


def test_integer_beyond_python_string_conversion_limit():
    assert normalize_commits_count(10**5000) == "1" + "0" * 5000
