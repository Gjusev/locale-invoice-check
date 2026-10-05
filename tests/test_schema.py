"""The bundled JSON Schema validates the artifacts the package actually emits."""

from __future__ import annotations

import jsonschema

from locale_invoice_check.extractors import RegexBaselineExtractor
from locale_invoice_check.schema import SCHEMA_VERSION, load_result_schema
from locale_invoice_check.scoring import evaluate_corpus


def test_result_validates_against_bundled_schema(corpus):
    result = evaluate_corpus(corpus, RegexBaselineExtractor(),
                             min_field_accuracy=0.0, max_locale_delta=1.0,
                             max_money_error_rate=1.0)
    jsonschema.validate(result, load_result_schema())


def test_review_queue_wrapper_validates(corpus):
    result = evaluate_corpus(corpus, RegexBaselineExtractor())
    wrapper = {"schema_version": SCHEMA_VERSION,
               "review_queue": result["review_queue"]}
    schema = load_result_schema()
    items = schema["properties"]["review_queue"]["items"]
    for entry in wrapper["review_queue"]:
        jsonschema.validate(entry, items)
    assert wrapper["schema_version"] == "1.0"
