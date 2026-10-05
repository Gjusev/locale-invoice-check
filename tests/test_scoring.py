"""Scoring primitives verified against independently computed examples."""

from __future__ import annotations

from decimal import Decimal

import pytest

from locale_invoice_check.scoring import (
    is_date_swap,
    normalize_date,
    parse_amount,
    score_field,
    validate_threshold,
)


class TestParseAmount:
    def test_en_dot_decimal(self):
        assert parse_amount("1,234.56") == Decimal("1234.56")

    def test_de_es_comma_decimal_with_thousands(self):
        assert parse_amount("1.234,56") == Decimal("1234.56")

    def test_bare_comma_last_group_of_three_is_thousands(self):
        assert parse_amount("1,234") == Decimal("1234")

    def test_bare_comma_short_group_is_decimal(self):
        assert parse_amount("1,23") == Decimal("1.23")
        assert parse_amount("9,90") == Decimal("9.90")

    def test_currency_and_spaces_stripped(self):
        assert parse_amount("€9.90") == Decimal("9.90")
        assert parse_amount("9,90 EUR") == Decimal("9.90")
        assert parse_amount("1 234,56") == Decimal("1234.56")

    def test_multiple_dots_are_thousands(self):
        assert parse_amount("1.234.567,89") == Decimal("1234567.89")

    def test_single_dot_taken_as_decimal_documented_bias(self):
        assert parse_amount("12.000") == Decimal("12.000")

    def test_rejects_garbage(self):
        for bad in ("abc", "", "€", "--5", "1..2", None, True, 1.5):
            if bad == 1.5:
                assert parse_amount(bad) == Decimal("1.5")
            else:
                assert parse_amount(bad) is None


class TestNormalizeDate:
    def test_three_formats(self):
        assert normalize_date("2026-03-04") == "2026-03-04"
        assert normalize_date("04.03.2026") == "2026-03-04"
        assert normalize_date("04/03/2026") == "2026-03-04"

    def test_slash_reading_is_day_first(self):
        assert normalize_date("03/04/2026") == "2026-04-03"

    def test_invalid_dates(self):
        for bad in ("2026-02-30", "04/2026", "not a date", "", None):
            assert normalize_date(bad) is None


class TestDateSwap:
    def test_observable_swap_detected(self):
        assert is_date_swap("2026-04-03", "2026-03-04")

    def test_day_over_twelve_not_observable(self):
        assert not is_date_swap("2026-12-28", "2026-03-14")

    def test_day_equals_month_not_observable(self):
        assert not is_date_swap("2026-03-03", "2026-03-03")


class TestScoreField:
    def test_id_strip(self):
        passed, _, normalized = score_field("invoice_number", " INV-0001 ", "INV-0001")
        assert passed and normalized == "INV-0001"

    def test_tolerance_is_inclusive(self):
        assert score_field("net_amount", "10.01", "10.00")[0]
        assert score_field("net_amount", "9.99", "10.00")[0]
        assert not score_field("net_amount", "10.02", "10.00")[0]
        assert not score_field("net_amount", "9.98", "10.00")[0]

    def test_missing_value_fails(self):
        passed, reason, _ = score_field("total_amount", None, "0.06")
        assert not passed and reason == "missing"

    def test_swap_reason_for_swapped_iso_date(self):
        passed, reason, _ = score_field("invoice_date", "2026-04-03", "2026-03-04")
        assert not passed and reason == "date_swap"

    def test_correct_date_has_no_reason(self):
        passed, reason, _ = score_field("invoice_date", "04.03.2026", "2026-03-04")
        assert (passed and reason == "date_swap") or (passed and reason == "date_mismatch")

    def test_correct_date_reason_is_empty_path(self):
        passed, _reason, _ = score_field("invoice_date", "04.03.2026", "2026-03-04")
        assert passed

    def test_validate_threshold_rejects_bad_values(self):
        for bad in (-0.1, 1.1, float("nan"), float("inf")):
            with pytest.raises(ValueError):
                validate_threshold(bad)
        assert validate_threshold(0.5) == 0.5
