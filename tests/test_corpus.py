"""Corpus generation, manifest integrity, and the rendered_text leak guard."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from locale_invoice_check.corpus import LOCALES, generate_corpus, load_corpus


def _read_metadata(path):
    with Image.open(path) as image:
        return image.info.get("rendered_text", "")


def test_generate_and_load_roundtrip(tmp_path):
    generate_corpus(tmp_path, count=4, seed=7)
    root, manifest = load_corpus(tmp_path)
    assert manifest["seed"] == 7
    assert len(manifest["invoices"]) == 4
    for record in manifest["invoices"]:
        for locale in LOCALES:
            assert (root / record["images"][locale]).exists()


def test_nonempty_directory_refused(tmp_path):
    generate_corpus(tmp_path / "fx", count=1, seed=1)
    with pytest.raises(ValueError, match="empty"):
        generate_corpus(tmp_path / "fx", count=1, seed=1)


def test_count_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        generate_corpus(tmp_path, count=0, seed=1)


def test_tampered_image_fails_hash_check(tmp_path):
    generate_corpus(tmp_path, count=1, seed=1)
    target = next(tmp_path.glob("*.png"))
    target.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_corpus(tmp_path)


def test_unsupported_schema_version(tmp_path):
    generate_corpus(tmp_path, count=1, seed=1)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "9.9"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        load_corpus(tmp_path)


def test_image_must_stay_inside_corpus_dir(tmp_path):
    generate_corpus(tmp_path, count=1, seed=1)
    manifest_path = tmp_path / "manifest.json"
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    doc["invoices"][0]["images"]["EN"] = "../evil.png"
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        load_corpus(tmp_path)


def test_rendered_text_never_contains_canonical_truth(corpus):
    """DE/ES renderings must not leak canonical ISO dates or dot-decimal amounts."""
    _, manifest = load_corpus(corpus)
    for record in manifest["invoices"]:
        for locale in ("DE", "ES"):
            text = _read_metadata(corpus / record["images"][locale])
            assert record["truth"]["invoice_date"] not in text
            assert record["truth"]["net_amount"] not in text
            assert record["truth"]["tax_amount"] not in text
            assert record["truth"]["total_amount"] not in text


def test_rendered_text_is_display_text(corpus):
    _, manifest = load_corpus(corpus)
    text = _read_metadata(corpus / manifest["invoices"][0]["images"]["DE"])
    assert "Rechnungsdatum" in text
    assert "," in text  # German decimal comma
    assert chr(8364) in text  # euro sign


def test_missing_image_is_an_error(tmp_path):
    generate_corpus(tmp_path, count=1, seed=1)
    next(tmp_path.glob("*.png")).unlink()
    with pytest.raises(OSError):
        load_corpus(tmp_path)


def test_missing_locale_image_entry_is_an_error(tmp_path):
    generate_corpus(tmp_path, count=1, seed=1)
    manifest_path = tmp_path / "manifest.json"
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    del doc["invoices"][0]["images"]["ES"]
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="missing locale image"):
        load_corpus(tmp_path)
