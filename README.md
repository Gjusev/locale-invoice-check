# locale-invoice-check

[![PyPI](https://img.shields.io/pypi/v/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![Python](https://img.shields.io/pypi/pyversions/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![CI](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml/badge.svg)](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/Gjusev/locale-invoice-check/blob/main/LICENSE)

A regression harness for invoice extraction built on **matched triplet pairs**: the
same data and layout rendered in **English, German, and Spanish** as synthetic PNG
invoices. Only locale conventions vary — labels, numeric separators, date format,
and currency presentation — so any accuracy difference between locales is directly
attributable to locale handling, not to document content.

Fields in v0.1 (exact set): `invoice_number`, `invoice_date`, `net_amount`,
`tax_amount`, `total_amount`.

## Why

GPT-6.1 Sol (released September 29, 2026) emphasizes document understanding
([announcement](https://openai.com/index/introducing-gpt-6-1-sol/)). The motivating
question of this harness: do those capabilities survive European locale
conventions? This project does **not** claim to have found a real defect in that
(or any) model; it provides controlled pairs and deterministic gates so you can
measure your own extractors.

## Quick start (no credentials)

```bash
pip install locale-invoice-check

locale-check generate fixtures --count 30 --seed 42
locale-check run fixtures --extractor regex --json --output result.json
locale-check demo

# strict demo: exits 1 (the bundled baseline intentionally fails DE/ES money)
# relaxed demo: exits 0
locale-check demo --min-field-accuracy 0 --max-locale-delta 1 --max-money-error-rate 1

## Extractors

Public contract: `extract(image_path, field_list) -> dict` returning a
JSON-compatible mapping of `{field: value}` or `{field: {"value": ..., "confidence": ...}}`.

### RegexBaselineExtractor (offline, deterministic)

Reads the visible text transcription stored in the PNG `rendered_text` metadata
chunk. **This is explicitly an OCR surrogate, not OCR**: the harness needs to test
parsers and locale handling without a heavyweight OCR dependency. Canonical ground
truth is never stored in that metadata (only the displayed text is; DE/ES renderings
use their locale separators, so canonical dot-decimals and ISO dates cannot leak).

The baseline's money parser **intentionally** interprets every comma as a thousands
separator (the classic EN-only bug). Expected seeded result on the default corpus:
EN parses perfectly, DE/ES amounts fail. The numbers below are measured, not
invented (30 invoices, seed 42):

| field_accuracy      | EN     | DE     | ES     |
|---------------------|--------|--------|--------|
| invoice_number      | 100.0% | 100.0% | 100.0% |
| invoice_date        | 100.0% | 100.0% | 100.0% |
| net_amount          | 100.0% | 0.0%   | 0.0%   |
| tax_amount          | 100.0% | 0.0%   | 0.0%   |
| total_amount        | 100.0% | 0.0%   | 0.0%   |

| rollup             | EN     | DE     | ES     |
|--------------------|--------|--------|--------|
| locale_accuracy    | 100.0% | 40.0%  | 40.0%  |
| money_error_rate   | 0.0%   | 100.0% | 100.0% |
| date_swap_rate     | 0.0%   | 0.0%   | 0.0%   |

`locale_delta` = −0.60 (strict demo exits **1**; relaxed demo exits **0**).

### LLMExtractor (optional `[llm]` extra)

OpenAI-compatible vision endpoint, image sent as a data URI, `temperature: 0`.
Only the image and field instructions are sent — never ground truth. Error
messages never include response bodies or credentials.

```bash
pip install "locale-invoice-check[llm]"
export VISION_API_KEY=...      # required
export VISION_MODEL=...        # required
export VISION_BASE_URL=https://api.openai.com/v1   # optional, this is the default
locale-check run fixtures --extractor llm
```

Requests and errors are tested offline via `httpx.MockTransport`; no live network
test ships with the package.

## Metrics (deterministic, no LLM judge)

With `N` = number of invoices and five fields:

- `field_accuracy[locale][field]` = correct fields / N — 15 metrics (5 × 3 locales)
- `locale_accuracy[locale]` = correct fields / (5·N)
- `locale_delta` = min(locale_accuracy) − locale_accuracy[EN] — **signed**: a
  12-point drop is `-0.12`
- `money_error_rate[locale]` = invoices with at least one wrong amount / N
- `date_swap_rate[locale]` = invoices with an observable day/month inversion / N

**Date swap observability.** An inversion can only hide when `day ≤ 12` and
`day ≠ month` (otherwise the swapped reading is either invalid or identical). For
invoices where the inversion is not observable, the swap rate simply cannot count
it; a plain date mismatch still fails the field.

**Amount/date normalization (format only — wrong values are never repaired).**

- IDs: equality after `strip()`.
- Dates: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY` → ISO `YYYY-MM-DD`.
  The slash format reads day-first (Spanish convention); dot format likewise.
- Amounts (Decimal, inclusive absolute tolerance **0.01**):
  - currency symbols (`€`, `EUR`), spaces, and NBSP are stripped;
  - both `.` and `,` present → the rightmost one is the decimal separator;
  - only `,` → a trailing group of exactly 3 digits means thousands (`1,234` →
    1234); otherwise decimal (`9,90` → 9.90);
  - only `.` → multiple dots mean thousands; a single dot is read as decimal
    (`12.000` → 12.0). This is a documented bias toward the EN reading; some
    ambiguous cases are inherently undecidable and are normalized, not repaired;
  - consecutive separators (`1..2`) are rejected.

## Gates

| flag | strict default | relaxed demo |
|------|----------------|--------------|
| `--min-field-accuracy` | 0.95 (applies to all 15 metrics) | 0 |
| `--max-locale-delta` | 0.05 (positive magnitude of allowed drop) | 1 |
| `--max-money-error-rate` | 0.05 | 1 |
| `--max-date-swap-rate` | 0.0 | 0.0 |
| `--min-confidence` | 0.8 (confidence only feeds the review queue, never gates) | 0.8 |

## Exit codes

| code | meaning |
|------|---------|
| 0 | all gates satisfied |
| 1 | gates failed — artifacts are still written |
| 2 | configuration, data, or transport error |

A transport failure (network down, HTTP 5xx, invalid JSON from the vision
endpoint) is always exit 2, never silently turned into an extraction failure.

## Artifacts

- `result.json` — full run: metrics, gates, per-invoice/per-field details with
  `schema_version: "1.0"`. A JSON Schema ships inside the package
  (`locale_invoice_check/schemas/result.v1.json`,
  `locale_invoice_check.load_result_schema()`); changes within schema version 1.0
  are additive only.
- `review-queue.json` — `{schema_version, review_queue}` where every failed or
  low-confidence field lists invoice, locale, field, expected, got, and reasons.
  Confidence is taken only from the adapter; the harness never invents it.
- `report.html` — standalone, no server, no remote resources: one row per
  invoice, EN/DE/ES columns with base64 thumbnails, per-field expected/got,
  failures in red, metrics/gates/review queue at the end. All external content
  is HTML-escaped.

## Python API

```python
from locale_invoice_check import (FIELDS, LOCALES, LLMExtractor,
                                  RegexBaselineExtractor, evaluate_corpus,
                                  generate_corpus, load_corpus)

generate_corpus("fixtures", count=30, seed=42)          # 30 x EN/DE/ES PNGs
_, manifest = load_corpus("fixtures")                    # validated, hash-checked
result = evaluate_corpus("fixtures", RegexBaselineExtractor())
result["passed"]            # bool
result["metrics"]["field_accuracy"]["DE"]["net_amount"]
```

## Reproducibility

- Generation is seeded (`--seed`); the manifest records seed, renderer
  configuration (Pillow version), relative image paths, and SHA-256 hashes.
  Loading a corpus verifies every hash, so a corpus and its results are fully
  redistributable and bit-reproducible.
- Results contain no timestamps or absolute paths; runs are deterministic offline.
- The corpus is entirely synthetic — no real invoices, no personal data — and is
  Apache-2.0 licensed with the code.

## Reproduce in Kaggle

> The kernel installs `locale-invoice-check==0.1.0` from PyPI, so **this requires
> the package to be published on PyPI first**.

`kaggle-kernel/offline/script.py` + `kaggle-kernel/kernel-metadata.json` define a
public CPU kernel (`enable_gpu: false`, `enable_internet: true` — internet is only
needed for the pip install) that runs the offline demo with **relaxed gates,
explicitly not recommended production thresholds**, prints a summary, and writes
`result.json`, `report.html`, and `review-queue.json` to `/kaggle/working`.

Authenticate with a Kaggle API token (never commit it):

```bash
export KAGGLE_API_TOKEN=<your-token>   # official OAuth token variable
kaggle kernels push -p kaggle-kernel
kaggle kernels status gjusev/locale-invoice-check-demo
kaggle kernels output gjusev/locale-invoice-check-demo -p ./kernel-output
```

## Related benchmarks (by name, not instead of)

Real document-extraction benchmarks exist and are more representative of
production traffic than this corpus:

- **DocILE** (ICDAR 2023, Rossum) — ~6.7k annotated business documents as PDFs for
  key information localization and line-item recognition; large and realistic,
  but documents are not locale-controlled matched pairs.
- **DocuBench** (DocuPipe) — real-world documents with JSON schemas and
  hand-verified labels, scored on macro-average field accuracy.
- **Omni Extract Bench** (Datalab) — extraction benchmark toolkit with provider
  prediction harnesses and interpretable scoring.

What this package adds that those do not target: **controlled pairs** where only
locale conventions change, fully offline determinism, redistributable synthetic
data, and CI gate semantics with exit codes. It is a regression harness, not a
leaderboard, and its absolute numbers say nothing about real-world accuracy.

## Limitations

- Synthetic layout: a real OCR pipeline is out of scope (the baseline reads
  `rendered_text` metadata by design).
- Only PNG, only EUR, only the five v0.1 fields, only EN/DE/ES.
- Amount/date normalization resolves ambiguous separators with documented
  heuristics; inherently ambiguous inputs are normalized, not repaired.
- Date-swap detection cannot observe inversions when day ≤ 12 is violated.
- Confidence comes only from adapters that provide it.

## Development

```bash
make install   # uv sync
make test      # pytest, network hard-blocked
make lint      # ruff (E, F, I, UP, RUF; line-length 100)
make build
make demo      # strict demo must exit 1, relaxed must exit 0
```

CI (`.github/workflows/test.yml`) runs Ruff + offline pytest on Python
3.10–3.13, asserts the relaxed demo exits 0, builds the wheel, and smoke-tests
it in a clean venv. Publishing (`.github/workflows/publish.yml`) uses `uv build`
+ `uv publish` via Trusted Publishing on `release: published` — no tokens stored.

## License

[Apache-2.0](LICENSE)
