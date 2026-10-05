"""Adapter contract: regex baseline seeded bug and LLM adapter via MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from locale_invoice_check.corpus import FIELDS, load_corpus
from locale_invoice_check.extractors import LLMExtractor, RegexBaselineExtractor

FIELDS_LIST = list(FIELDS)


class TestRegexBaseline:
    def test_en_amounts_parse_correctly(self, corpus):
        _, manifest = load_corpus(corpus)
        extractor = RegexBaselineExtractor()
        record = manifest["invoices"][0]
        got = extractor.extract(corpus / record["images"]["EN"], FIELDS_LIST)
        assert got["invoice_number"] == record["truth"]["invoice_number"]
        assert got["invoice_date"] == "2026-03-04"
        for field in ("net_amount", "tax_amount", "total_amount"):
            assert got[field] == record["truth"][field]

    def test_de_es_amounts_fail_seeded_bug(self, corpus):
        _, manifest = load_corpus(corpus)
        extractor = RegexBaselineExtractor()
        for record in manifest["invoices"]:
            for locale in ("DE", "ES"):
                got = extractor.extract(corpus / record["images"][locale], FIELDS_LIST)
                amounts_ok = sum(
                    got[f] == record["truth"][f]
                    for f in ("net_amount", "tax_amount", "total_amount"))
                assert amounts_ok < 3, (record["id"], locale, got)


class TestLLMAdapter:
    @staticmethod
    def _client_transport(handler):
        return httpx.MockTransport(handler)

    def test_success_returns_fields_and_sends_no_ground_truth(self, corpus):
        _, manifest = load_corpus(corpus)
        record = manifest["invoices"][0]
        truth = record["truth"]

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["temperature"] == 0
            assert body["model"] == "test-model"
            content = body["messages"][0]["content"]
            assert content[0]["type"] == "text"
            url = content[1]["image_url"]["url"]
            assert url.startswith("data:image/png;base64,")
            prompt = content[0]["text"]
            for value in truth.values():
                assert value not in prompt  # ground truth never leaves the machine
            answer = dict(truth)
            answer["invoice_date"] = "2026-03-04"
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(answer)}}]})

        extractor = LLMExtractor("key", "test-model",
                                 transport=httpx.MockTransport(handler))
        got = extractor.extract(corpus / record["images"]["EN"], FIELDS_LIST)
        assert got["invoice_number"] == truth["invoice_number"]

    def test_http_error_hides_response_body_and_api_key(self, corpus):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "SENSITIVE-BODY-LEAK"}})

        extractor = LLMExtractor("sk-test-secret", "test-model",
                                 transport=httpx.MockTransport(handler))
        with pytest.raises(RuntimeError, match="HTTP 401"):
            extractor.extract(corpus / "INV-0001-EN.png", FIELDS_LIST)
        try:
            extractor.extract(corpus / "INV-0001-EN.png", FIELDS_LIST)
        except RuntimeError as error:
            assert "sk-test-secret" not in str(error)
            assert "SENSITIVE-BODY-LEAK" not in str(error)

    def test_transport_error_is_runtimeerror(self, corpus):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        extractor = LLMExtractor("key", "test-model",
                                 transport=httpx.MockTransport(handler))
        with pytest.raises(RuntimeError, match="transport"):
            extractor.extract(corpus / "INV-0001-EN.png", FIELDS_LIST)

    def test_invalid_json_content(self, corpus):
        cases = ["not json", "null", "[1, 2]"]
        for content in cases:
            def handler(request: httpx.Request, content=content) -> httpx.Response:
                return httpx.Response(200, json={
                    "choices": [{"message": {"content": content}}]})

            extractor = LLMExtractor("key", "test-model",
                                     transport=httpx.MockTransport(handler))
            with pytest.raises(RuntimeError, match="invalid extraction JSON"):
                extractor.extract(corpus / "INV-0001-EN.png", FIELDS_LIST)

    def test_from_env_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("VISION_API_KEY", "k")
        monkeypatch.setenv("VISION_MODEL", "m")
        monkeypatch.setenv("VISION_BASE_URL", "https://example.invalid/v1")
        extractor = LLMExtractor.from_env()
        assert extractor._model == "m"

    def test_from_env_requires_credentials(self, monkeypatch):
        monkeypatch.delenv("VISION_API_KEY", raising=False)
        monkeypatch.delenv("VISION_MODEL", raising=False)
        with pytest.raises(ValueError, match="VISION_API_KEY"):
            LLMExtractor.from_env()

    def test_base_url_validation(self):
        for bad in ("ftp://x", "https://u:p@host", "https://host?q=1", "not a url"):
            with pytest.raises(ValueError, match="base URL"):
                LLMExtractor("k", "m", base_url=bad)
