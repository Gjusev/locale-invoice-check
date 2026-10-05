"""Deterministic matched-pair invoice evaluation."""

from __future__ import annotations

from .corpus import FIELDS, LOCALES, generate_corpus, load_corpus
from .extractors import Extractor, LLMExtractor, RegexBaselineExtractor
from .scoring import evaluate_corpus

__version__ = "0.1.0"
__all__ = [
    "FIELDS",
    "LOCALES",
    "Extractor",
    "LLMExtractor",
    "RegexBaselineExtractor",
    "__version__",
    "evaluate_corpus",
    "generate_corpus",
    "load_corpus",
]
