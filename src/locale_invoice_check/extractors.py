"""Extractor boundary: extract(image_path, field_list) -> JSON-compatible mapping."""

from __future__ import annotations

import base64
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from PIL import Image

from .corpus import FIELDS, LABELS


class Extractor(Protocol):
    def extract(self, image_path: Path, field_list: list[str]) -> dict:
        """Return field values, optionally {value, confidence} per field."""
        ...


class RegexBaselineExtractor:
    """Intentionally naive EN number parser over rendered PNG metadata, NOT OCR."""

    def extract(self, image_path: Path, field_list: list[str]) -> dict:
        with Image.open(image_path) as image:
            text = image.info.get("rendered_text")
        if not isinstance(text, str):
            raise ValueError("regex baseline needs generated PNG rendered_text metadata (not OCR)")
        result = {}
        for field in field_list:
            labels = "|".join(re.escape(labels[FIELDS.index(field)]) for labels in LABELS.values())
            match = re.search(rf"^(?:{labels}): (.+)$", text, re.MULTILINE)
            value = match.group(1) if match else None
            if value is not None and field.endswith("amount"):
                number = re.search(r"\d[\d.,]*", value)
                # Deliberate reproducible bug: assumes every comma is a thousands separator.
                try:
                    value = str(Decimal(number.group().replace(",", ""))) if number else None
                except ArithmeticError:
                    value = None
            result[field] = value
        return result


class LLMExtractor:
    """Optional OpenAI-compatible vision adapter. Credentials never enter artifacts."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1",
                 *, transport=None, timeout: float = 60.0) -> None:
        try:
            import httpx
        except ImportError as error:
            raise ImportError("LLMExtractor requires the [llm] extra: "
                              "pip install 'locale-invoice-check[llm]'") from error

        url = urlsplit(base_url)
        if url.scheme not in ("http", "https") or not url.netloc or url.username or url.query:
            raise ValueError("base URL must be HTTP(S), without credentials or query parameters")
        if not api_key or not model:
            raise ValueError("VISION_API_KEY and VISION_MODEL are required")
        self._model = model
        self._client = httpx.Client(base_url=base_url.rstrip("/") + "/",
                                    headers={"Authorization": f"Bearer {api_key}"},
                                    transport=transport, timeout=timeout)

    @classmethod
    def from_env(cls) -> LLMExtractor:
        return cls(os.environ.get("VISION_API_KEY", ""), os.environ.get("VISION_MODEL", ""),
                   os.environ.get("VISION_BASE_URL", "https://api.openai.com/v1"))

    def close(self) -> None:
        self._client.close()

    def extract(self, image_path: Path, field_list: list[str]) -> dict:
        import httpx

        image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = ("Extract only these invoice fields as a JSON object: " + ", ".join(field_list)
                  + ". Missing fields must be null. Dates: ISO YYYY-MM-DD. Amounts: decimal "
                  "strings with a dot decimal separator and no thousands separator. No markdown.")
        payload = {"model": self._model, "temperature": 0, "messages": [{"role": "user",
                   "content": [{"type": "text", "text": prompt}, {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{image}"}}]}]}
        try:
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except httpx.HTTPStatusError as error:
            raise RuntimeError(
                f"vision endpoint returned HTTP {error.response.status_code}") from None
        except httpx.TransportError:
            raise RuntimeError("vision endpoint transport failed") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("vision endpoint returned invalid extraction JSON") from None
