"""The bundled JSON Schema validates the artifacts the package actually emits."""

from __future__ import annotations

import jsonschema

from locale_invoice_check.extractors import RegexBaselineExtractor
from locale_invoice_check.schema import SCHEMA_VERSION, load_result_schema
from locale_invoice_check.scoring import evaluate_corpus


def test_load_result_schema_is_exported_from_package_root():
    # Regression guard for the CI wheel-install failure: the public API must
    # expose load_result_schema without importing the submodule directly.
    import locale_invoice_check

    assert locale_invoice_check.load_result_schema() == load_result_schema()


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
