"""JSON Schema artifacts shipped inside the package for downstream validators."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

SCHEMA_VERSION = "1.0"

__all__ = ["SCHEMA_VERSION", "load_result_schema"]


def load_result_schema() -> dict[str, Any]:
    """Return the bundled JSON Schema for the ``result.json`` artifact."""
    resource = files("locale_invoice_check").joinpath("schemas/result.v1.json")
    return json.loads(resource.read_text(encoding="utf-8"))
