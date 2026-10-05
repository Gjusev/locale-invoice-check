"""Synthetic PNG fixtures; only locale conventions vary within a matched triplet."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from PIL import __version__ as pillow_version

FIELDS = ("invoice_number", "invoice_date", "net_amount", "tax_amount", "total_amount")
LOCALES = ("EN", "DE", "ES")
LABELS = {
    "EN": ("Invoice", "Invoice date", "Net amount", "Tax amount", "Total due"),
    "DE": ("Rechnung", "Rechnungsdatum", "Nettobetrag", "Steuerbetrag", "Gesamtbetrag"),
    "ES": ("Factura", "Fecha de factura", "Importe neto", "Impuesto", "Total a pagar"),
}
DATE_FORMATS = {"EN": "%Y-%m-%d", "DE": "%d.%m.%Y", "ES": "%d/%m/%Y"}


def money_text(value: str, locale: str) -> str:
    number = f"{Decimal(value):,.2f}"
    if locale != "EN":
        number = number.translate(str.maketrans({",": ".", ".": ","}))
        return f"{number} EUR" if locale == "ES" else f"{number} €"
    return f"€{number}"


def render_invoice(truth: dict[str, str], locale: str, path: Path) -> None:
    image = Image.new("RGB", (900, 540), "#ffffff")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=23)
    heading = ImageFont.load_default(size=30)
    draw.rectangle((0, 0, 900, 80), fill="#142b40")
    draw.text((35, 23), "SYNTHETIC / DEMO", fill="white", font=heading)
    lines = []
    for index, field in enumerate(FIELDS):
        value = truth[field]
        if field == "invoice_date":
            value = date.fromisoformat(value).strftime(DATE_FORMATS[locale])
        elif field.endswith("amount"):
            value = money_text(value, locale)
        line = f"{LABELS[locale][index]}: {value}"
        lines.append(line)
        draw.text((35, 125 + 65 * index), line, font=font, fill="#142b40")
    metadata = PngImagePlugin.PngInfo()
    # Only the displayed text, never canonical ground truth. This is an OCR surrogate.
    metadata.add_text("rendered_text", "\n".join(lines))
    image.save(path, pnginfo=metadata)


def generate_corpus(directory: str | Path, count: int = 30, seed: int = 42) -> Path:
    if count < 1:
        raise ValueError("count must be positive")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("fixture directory must be empty; choose a new output directory")
    rng = random.Random(seed)
    edges = ["0.05", "9.90", "1234.56", "100000.00", "999999.90", "10.00"]
    dates = [(3, 4), (4, 3), (3, 14), (12, 11), (11, 12), (12, 28)]
    records = []
    for index in range(count):
        net = (Decimal(edges[index]) if index < len(edges)
               else Decimal(rng.randrange(1, 20000000)) / 100)
        tax = (net * Decimal("0.19")).quantize(Decimal("0.01"))
        month, day = dates[index % len(dates)]
        truth = {
            "invoice_number": f"INV-{index + 1:04d}",
            "invoice_date": date(2026, month, day).isoformat(),
            "net_amount": f"{net:.2f}",
            "tax_amount": f"{tax:.2f}",
            "total_amount": f"{net + tax:.2f}",
        }
        images, hashes = {}, {}
        for locale in LOCALES:
            relative = f"{truth['invoice_number']}-{locale}.png"
            render_invoice(truth, locale, root / relative)
            images[locale] = relative
            hashes[locale] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        records.append({"id": truth["invoice_number"], "truth": truth, "images": images,
                        "sha256": hashes})
    manifest = {"schema_version": "1.0", "seed": seed, "renderer": f"Pillow {pillow_version}",
                "fields": list(FIELDS), "locales": list(LOCALES), "invoices": records}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_corpus(directory: str | Path) -> tuple[Path, dict]:
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise ValueError("unsupported corpus schema")
    if manifest.get("fields") != list(FIELDS) or manifest.get("locales") != list(LOCALES):
        raise ValueError("corpus must contain the five v0.1 fields and EN/DE/ES")
    records = manifest.get("invoices")
    if not isinstance(records, list) or not records:
        raise ValueError("corpus must contain invoices")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("invalid invoice record")
        if record["id"] in seen:
            raise ValueError("duplicate invoice id")
        seen.add(record["id"])
        truth = record.get("truth", {})
        if not isinstance(truth, dict) or set(truth) != set(FIELDS):
            raise ValueError("invalid ground truth fields")
        if not all(isinstance(v, str) and v.strip() for v in truth.values()):
            raise ValueError("ground truth must contain nonempty strings")
        date.fromisoformat(truth["invoice_date"])
        for field in FIELDS[2:]:
            if not Decimal(truth[field]).is_finite():
                raise ValueError("ground truth amounts must be finite")
        for locale in LOCALES:
            relative = record.get("images", {}).get(locale)
            if not isinstance(relative, str):
                raise ValueError("missing locale image")
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or path.suffix.lower() != ".png":
                raise ValueError("corpus images must be PNG files within the corpus directory")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != record.get("sha256", {}).get(locale):
                raise ValueError("image hash mismatch; regenerate the corpus")
            with Image.open(path) as image:
                if image.format != "PNG":
                    raise ValueError("corpus image is not PNG")
                image.verify()
    return root, manifest
