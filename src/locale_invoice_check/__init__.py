"""Deterministic matched-pair invoice evaluation."""

from __future__ import annotations

from .corpus import FIELDS, LOCALES, generate_corpus, load_corpus
from .extractors import Extractor, LLMExtractor, RegexBaselineExtractor
from .schema import SCHEMA_VERSION, load_result_schema
from .scoring import evaluate_corpus

__version__ = "0.1.1"
__all__ = [
    "FIELDS",
    "LOCALES",
    "SCHEMA_VERSION",
    "Extractor",
    "LLMExtractor",
    "RegexBaselineExtractor",
    "__version__",
    "evaluate_corpus",
    "generate_corpus",
    "load_corpus",
    "load_result_schema",
]
