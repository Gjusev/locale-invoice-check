"""Metrics and gates checked against hand-computed expectations."""

from __future__ import annotations

import pytest

from locale_invoice_check.corpus import FIELDS, LOCALES
from locale_invoice_check.scoring import evaluate_corpus


class CorrectExtractor:
    """Locale-aware rendered_text reader: a hypothetically perfect extractor."""

    def extract(self, image_path, field_list):
        import re

        from PIL import Image

        from locale_invoice_check.corpus import LABELS
        from locale_invoice_check.scoring import normalize_date, parse_amount
        with Image.open(image_path) as image:
            text = image.info["rendered_text"]
        lines = dict(re.findall(r"^(.+?): (.+)$", text, re.MULTILINE))
        locale = "DE" if "Rechnungsdatum" in lines else \
            "ES" if "Fecha de factura" in lines else "EN"
        values = {}
        for field in field_list:
            value = lines.get(LABELS[locale][FIELDS.index(field)])
            if field == "invoice_date":
                values[field] = normalize_date(value)
            elif field.endswith("amount"):
                values[field] = str(parse_amount(value))
            else:
                values[field] = value.strip() if value else None
        return values


class StaticExtractor:
    """Returns a fixed mapping, optionally wrapped as {value, confidence}."""

    def __init__(self, values, confidence=None):
        self.values = values
        self.confidence = confidence

    def extract(self, image_path, field_list):
        if self.confidence is None:
            return dict(self.values)
        return {f: {"value": v, "confidence": self.confidence}
                for f, v in self.values.items()}


def _evaluate(corpus, extractor, **gates):
    return evaluate_corpus(corpus, extractor, **gates)


def test_perfect_extractor_scores_one_everywhere(corpus):
    result = _evaluate(corpus, CorrectExtractor(),
                       min_field_accuracy=1.0, max_locale_delta=0.0)
    assert result["passed"]
    for locale in LOCALES:
        assert result["metrics"]["locale_accuracy"][locale] == 1.0
        for field in FIELDS:
            assert result["metrics"]["field_accuracy"][locale][field] == 1.0
    assert result["metrics"]["locale_delta"] == 0.0
    assert result["metrics"]["money_error_rate"] == {"EN": 0.0, "DE": 0.0, "ES": 0.0}
    assert result["review_queue"] == []


def test_money_error_rate_counts_invoices_not_fields(corpus):
    # Corrupt net_amount in every invoice, DE only.
    def extractor_factory(base):
        class E:
            def extract(self, image_path, field_list):
                got = base(image_path, field_list)
                if str(image_path).endswith("-DE.png"):
                    got["net_amount"] = "0.00"
                return got
        return E()

    base = CorrectExtractor()
    inner = extractor_factory(base.extract)
    result = _evaluate(corpus, inner, max_money_error_rate=1.0)
    money = result["metrics"]["money_error_rate"]
    assert money == {"EN": 0.0, "DE": 1.0, "ES": 0.0}, money


def test_signed_locale_delta(corpus):
    # Regex baseline: EN perfect, DE/ES broken by the seeded bug.
    from locale_invoice_check.extractors import RegexBaselineExtractor
    result = _evaluate(corpus, RegexBaselineExtractor())
    metrics = result["metrics"]
    acc = metrics["locale_accuracy"]
    assert acc["EN"] > acc["DE"] and acc["EN"] > acc["ES"]
    delta = metrics["locale_delta"]
    assert delta == min(acc.values()) - acc["EN"]
    assert delta < 0
    # max-locale-delta gate receives a positive magnitude of allowed drop.
    delta_gate = next(g for g in result["gates"] if g["name"] == "max_locale_delta")
    assert delta_gate["measured"] == -delta and delta_gate["measured"] > 0


def test_date_swap_rate_counts_observable_swaps(corpus):
    class SwapDE:
        def extract(self, image_path, field_list):
            got = CorrectExtractor().extract(image_path, field_list)
            if str(image_path).endswith("-DE.png"):
                truth_iso = got["invoice_date"]
                year, month, day = truth_iso.split("-")
                got["invoice_date"] = f"{year}-{day}-{month}"  # swapped ISO output
            return got
    result = _evaluate(corpus, SwapDE(), max_date_swap_rate=1.0)
    # 3 of the 4 fixture invoices have day<=12 != month: observable inversions.
    assert result["metrics"]["date_swap_rate"]["DE"] == 0.75
    assert result["metrics"]["date_swap_rate"]["EN"] == 0.0


def test_low_confidence_enters_review_queue_without_failing_gates(corpus):
    class LowConfidence(CorrectExtractor):
        def extract(self, image_path, field_list):
            values = super().extract(image_path, field_list)
            return {f: {"value": v, "confidence": 0.5} for f, v in values.items()}

    result = _evaluate(corpus, LowConfidence(), min_confidence=0.8,
                       min_field_accuracy=0.0)
    # Confidence never affects gates; it only fills the review queue.
    assert result["passed"]
    entries = result["review_queue"]
    assert len(entries) == 4 * 3 * 5
    assert all("low_confidence" in e["reasons"] for e in entries)
    assert all(e["confidence"] == 0.5 for e in entries)


def test_extractors_returning_non_dict_raises(corpus):
    class Junk:
        def extract(self, image_path, field_list):
            return ["not", "a", "dict"]

    with pytest.raises(ValueError, match="JSON object"):
        _evaluate(corpus, Junk())
