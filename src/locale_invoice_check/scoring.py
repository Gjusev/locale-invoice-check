"""Deterministic scoring. Locale formatting is normalized without repairing wrong values."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .corpus import FIELDS, LOCALES, load_corpus
from .extractors import Extractor


def parse_amount(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().replace("€", "").replace("EUR", "").strip()
    raw = raw.replace("\u00a0", "").replace(" ", "")
    if not re.fullmatch(r"[+-]?\d[\d.,]*", raw) or re.search(r"[.,]{2}", raw):
        return None
    if "," in raw and "." in raw:
        decimal_mark = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_mark == "," else ","
        raw = raw.replace(thousands, "").replace(decimal_mark, ".")
    elif "," in raw:
        pieces = raw.split(",")
        raw = "".join(pieces) if len(pieces[-1]) == 3 else raw.replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        result = Decimal(raw)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def normalize_date(value) -> str | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def is_date_swap(value, expected: str) -> bool:
    truth = date.fromisoformat(expected)
    if truth.day == truth.month or truth.day > 12:
        return False
    return normalize_date(value) == date(truth.year, truth.day, truth.month).isoformat()


def score_field(field: str, value, expected: str) -> tuple[bool, str, str | None]:
    if value is None:
        return False, "missing", None
    if field == "invoice_number":
        normalized = str(value).strip()
        return normalized == expected.strip(), "id_mismatch", normalized
    if field == "invoice_date":
        normalized = normalize_date(value)
        reason = "date_swap" if is_date_swap(value, expected) else "date_mismatch"
        return normalized == expected, reason if normalized else "invalid_date", normalized
    amount = parse_amount(value)
    if amount is None:
        return False, "invalid_amount", None
    return abs(amount - Decimal(expected)) <= Decimal("0.01"), "amount_mismatch", str(amount)


def validate_threshold(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("thresholds must be finite numbers between 0 and 1")
    return value


def evaluate_corpus(directory: str | Path, extractor: Extractor, *,
                    min_field_accuracy: float = 0.95,
                    max_locale_delta: float = 0.05, max_money_error_rate: float = 0.05,
                    max_date_swap_rate: float = 0.0, min_confidence: float = 0.8) -> dict:
    thresholds = {"min_field_accuracy": min_field_accuracy, "max_locale_delta": max_locale_delta,
                  "max_money_error_rate": max_money_error_rate,
                  "max_date_swap_rate": max_date_swap_rate, "min_confidence": min_confidence}
    for value in thresholds.values():
        validate_threshold(value)
    root, manifest = load_corpus(directory)
    correct = {loc: dict.fromkeys(FIELDS, 0) for loc in LOCALES}
    money_errors, swaps = dict.fromkeys(LOCALES, 0), dict.fromkeys(LOCALES, 0)
    invoices, queue = [], []
    for invoice in manifest["invoices"]:
        record = {"id": invoice["id"], "locales": {}}
        for locale in LOCALES:
            extracted = extractor.extract(root / invoice["images"][locale], list(FIELDS))
            if not isinstance(extracted, dict):
                raise ValueError("extractor must return a JSON object")
            fields = {}
            for field in FIELDS:
                raw = extracted.get(field)
                confidence = None
                if isinstance(raw, dict):
                    confidence, raw = raw.get("confidence"), raw.get("value")
                if confidence is not None:
                    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                        raise ValueError("confidence must be a number between 0 and 1")
                    validate_threshold(confidence)
                if raw is not None and (isinstance(raw, (dict, list, bool)) or
                                         not isinstance(raw, (str, int, float))):
                    raise ValueError("field values must be JSON scalars or null")
                if isinstance(raw, float) and not math.isfinite(raw):
                    raise ValueError("field values must be finite")
                expected = invoice["truth"][field]
                passed, reason, normalized = score_field(field, raw, expected)
                correct[locale][field] += int(passed)
                reasons = [] if passed else [reason]
                if confidence is not None and confidence < min_confidence:
                    reasons.append("low_confidence")
                cell = {"expected": expected, "got": raw, "normalized": normalized,
                        "passed": passed, "confidence": confidence, "reasons": reasons}
                fields[field] = cell
                if reasons:
                    queue.append({"invoice_id": invoice["id"], "locale": locale,
                                  "field": field, **cell})
            money_errors[locale] += int(any(not fields[f]["passed"] for f in FIELDS[2:]))
            swaps[locale] += int("date_swap" in fields["invoice_date"]["reasons"])
            record["locales"][locale] = {"image": invoice["images"][locale], "fields": fields}
        invoices.append(record)
    count = len(invoices)
    field_accuracy = {loc: {f: correct[loc][f] / count for f in FIELDS} for loc in LOCALES}
    accuracy = {loc: sum(correct[loc].values()) / (count * len(FIELDS)) for loc in LOCALES}
    metrics = {"field_accuracy": field_accuracy, "locale_accuracy": accuracy,
               "locale_delta": min(accuracy.values()) - accuracy["EN"],
               "money_error_rate": {loc: money_errors[loc] / count for loc in LOCALES},
               "date_swap_rate": {loc: swaps[loc] / count for loc in LOCALES}}
    checks = [
        ("min_field_accuracy", min(v for loc in field_accuracy.values() for v in loc.values()),
         min_field_accuracy, "min"),
        ("max_locale_delta", -metrics["locale_delta"], max_locale_delta, "max"),
        ("max_money_error_rate", max(metrics["money_error_rate"].values()),
         max_money_error_rate, "max"),
        ("max_date_swap_rate", max(metrics["date_swap_rate"].values()), max_date_swap_rate, "max"),
    ]
    gates = [{"name": name, "measured": measured, "threshold": threshold, "direction": direction,
              "passed": measured + 1e-12 >= threshold if direction == "min"
              else measured <= threshold + 1e-12}
                 for name, measured, threshold, direction in checks]
    return {"schema_version": "1.0", "package_version": "0.1.0", "count": count,
            "seed": manifest["seed"], "renderer": manifest["renderer"],
            "extractor": type(extractor).__name__, "fields": list(FIELDS), "locales": list(LOCALES),
            "thresholds": thresholds, "metrics": metrics, "gates": gates,
            "passed": all(gate["passed"] for gate in gates), "invoices": invoices,
            "review_queue": queue}


def summary(result: dict) -> str:
    metrics = result["metrics"]
    lines = [f"invoices={result['count']} extractor={result['extractor']}"]
    for locale in LOCALES:
        lines.append(f"{locale}: accuracy={metrics['locale_accuracy'][locale]:.2%} "
                     f"money_error_rate={metrics['money_error_rate'][locale]:.2%}")
    lines.append(f"locale_delta={metrics['locale_delta']:+.2%}")
    lines.append(f"review_fields={len(result['review_queue'])} gates="
                 + ("PASS" if result["passed"] else "FAIL"))
    return "\n".join(lines)
