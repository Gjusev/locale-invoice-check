# locale-invoice-check

[![PyPI](https://img.shields.io/pypi/v/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![Python](https://img.shields.io/pypi/pyversions/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![CI](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml/badge.svg)](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/Gjusev/locale-invoice-check/blob/main/LICENSE)

A regression harness for invoice extraction. It renders the same synthetic
invoices as PNG triplets in English, German, and Spanish, and changes only what
locale conventions change: labels, numeric separators, date format, and how the
euro sign sits next to the number. When accuracy drops between locales, locale
handling is the only possible cause.

Fields in v0.1 (exact set): `invoice_number`, `invoice_date`, `net_amount`,
`tax_amount`, `total_amount`.

## Demo video

https://github.com/Gjusev/locale-invoice-check/releases/download/v0.1.1/brag.mp4

## Why

OpenAI released GPT-6.1 Sol on September 29, 2026 with document understanding as
a headline capability ([announcement](https://openai.com/index/introducing-gpt-6-1-sol/)).
Whether that survives a German decimal comma is what this harness measures.

Nothing here shows a defect in that or any model. The harness gives you
controlled pairs and hard gates so you can measure your own extractors.

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

Public contract: `extract(image_path, field_list) -> dict`, returning a
JSON-compatible mapping of `{field: value}` or `{field: {"value": ..., "confidence": ...}}`.

### RegexBaselineExtractor (offline, deterministic)

Reads the visible text transcription stored in the PNG `rendered_text` metadata
chunk. This is an OCR surrogate, not OCR: the harness tests parsing and locale
handling, so the package ships no OCR engine. Canonical ground truth never
touches that metadata. Only the displayed text is stored, and DE/ES renderings
use their locale separators, so canonical dot-decimals and ISO dates cannot leak.

The money parser in the baseline interprets every comma as a thousands
separator. That is the classic English-only bug, and it is in there on purpose.
On the default corpus (30 invoices, seed 42) the result is exactly what the bug
predicts: EN parses perfectly, DE and ES amounts fail. These numbers are measured:

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

`locale_delta` = −0.60. The strict demo exits **1**; the relaxed demo exits **0**.

### LLMExtractor (optional `[llm]` extra)

An OpenAI-compatible vision endpoint, image sent as a data URI, `temperature: 0`.
Only the image and field instructions are sent, never ground truth. Error
messages never include response bodies or credentials.

```bash
pip install "locale-invoice-check[llm]"
export VISION_API_KEY=...      # required
export VISION_MODEL=...        # required
export VISION_BASE_URL=https://api.openai.com/v1   # optional, this is the default
locale-check run fixtures --extractor llm
```

Requests and errors are tested offline via `httpx.MockTransport`. No live network
test ships with the package.

## Metrics (deterministic, no LLM judge)

With `N` = number of invoices and five fields:

- `field_accuracy[locale][field]` = correct fields / N (15 metrics, 5 fields x 3 locales)
- `locale_accuracy[locale]` = correct fields / (5·N)
- `locale_delta` = min(locale_accuracy) − locale_accuracy[EN]. Signed: a
  12-point drop is `-0.12`
- `money_error_rate[locale]` = invoices with at least one wrong amount / N
- `date_swap_rate[locale]` = invoices with an observable day/month inversion / N

### Date swap observability

A day/month inversion can only hide when `day ≤ 12` and `day ≠ month`. In any
other case the swapped reading is either invalid or identical. For invoices
where the inversion is not observable, the swap rate cannot count it; a plain
date mismatch still fails the field.

### Amount and date normalization

Formatting is normalized. Wrong values are never repaired.

- IDs: equality after `strip()`.
- Dates: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD/MM/YYYY` → ISO `YYYY-MM-DD`.
  The slash format reads day-first (Spanish convention), as does the dot format.
- Amounts use `Decimal` with an inclusive absolute tolerance of **0.01**:
  - currency symbols (`€`, `EUR`), spaces, and NBSP are stripped;
  - both `.` and `,` present → the rightmost one is the decimal separator;
  - only `,` → a trailing group of exactly 3 digits means thousands (`1,234` →
    1234); otherwise decimal (`9,90` → 9.90);
  - only `.` → multiple dots mean thousands; a single dot is read as decimal
    (`12.000` → 12.0). This is a documented bias toward the EN reading. Some
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
| 1 | gates failed, artifacts are still written |
| 2 | configuration, data, or transport error |

A transport failure (network down, HTTP 5xx, invalid JSON from the vision
endpoint) is always exit 2. It is never silently turned into an extraction
failure.

## Artifacts

- `result.json` holds the full run: metrics, gates, and per-invoice/per-field
  details, with `schema_version: "1.0"`. A JSON Schema ships inside the package
  (`locale_invoice_check/schemas/result.v1.json`,
  `locale_invoice_check.load_result_schema()`). Changes within schema version
  1.0 are additive only.
- `review-queue.json` is `{schema_version, review_queue}`. Every failed or
  low-confidence field lists invoice, locale, field, expected, got, and reasons.
  Confidence comes only from the adapter; the harness never invents it.
- `report.html` is standalone. No server, no remote resources: one row per
  invoice, EN/DE/ES columns with base64 thumbnails, per-field expected/got,
  failures in red, and metrics, gates, and the review queue at the end. All
  external content is HTML-escaped.

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

`python -m locale_invoice_check` works wherever the console script is not on
your PATH.

## Reproducibility

- Generation is seeded (`--seed`). The manifest records seed, renderer
  configuration (Pillow version), relative image paths, and SHA-256 hashes.
  Loading a corpus verifies every hash, so a corpus and its results are
  redistributable and bit-reproducible.
- Results contain no timestamps or absolute paths. Runs are deterministic offline.
- The corpus is entirely synthetic: no real invoices, no personal data. It is
  Apache-2.0 licensed with the code.

## Reproduce in Kaggle

> The kernel installs `locale-invoice-check==0.1.2` from PyPI, so **this
> requires the package to be published on PyPI first**.

`kaggle-kernel/offline/script.py` plus `kaggle-kernel/kernel-metadata.json`
define a public CPU kernel (`enable_gpu: false`, `enable_internet: true`;
internet is only needed for the pip install). It runs the offline demo with
relaxed gates, which are explicitly not recommended production thresholds,
prints a summary, and writes `result.json`, `report.html`, and
`review-queue.json` to `/kaggle/working`.

Authenticate with a Kaggle API token (never commit it):

```bash
export KAGGLE_API_TOKEN=<your-token>   # official OAuth token variable
kaggle kernels push -p kaggle-kernel
kaggle kernels status gjusev/locale-invoice-check-demo
kaggle kernels output gjusev/locale-invoice-check-demo -p ./kernel-output
```

## Related benchmarks (by name, not instead of)

Real document-extraction benchmarks exist, and they are more representative of
production traffic than this corpus:

- **DocILE** (ICDAR 2023, Rossum) has ~6.7k annotated business documents as
  PDFs for key information localization and line-item recognition. Large and
  realistic, but the documents are not locale-controlled matched pairs.
- **DocuBench** (DocuPipe) scores real-world documents with JSON schemas and
  hand-verified labels on macro-average field accuracy.
- **Omni Extract Bench** (Datalab) is an extraction benchmark toolkit with
  provider prediction harnesses and interpretable scoring.

What this package adds is narrower: controlled pairs where only locale
conventions change, full offline determinism, redistributable synthetic data,
and gate semantics with exit codes for CI. It is not a leaderboard, and its
absolute numbers say nothing about real-world accuracy.

## Limitations

- Synthetic layout. A real OCR pipeline is out of scope; the baseline reads
  `rendered_text` metadata by design.
- Only PNG, only EUR, only the five v0.1 fields, only EN/DE/ES.
- Amount/date normalization resolves ambiguous separators with documented
  heuristics. Inherently ambiguous inputs are normalized, not repaired.
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

CI (`.github/workflows/test.yml`) runs Ruff and offline pytest on Python
3.10-3.13, asserts the relaxed demo exits 0, builds the wheel, and smoke-tests
it in a clean venv. Publishing (`.github/workflows/publish.yml`) uses `uv build`
and `uv publish` via Trusted Publishing on `release: published`. No tokens are
stored.

## License

[Apache-2.0](LICENSE)
