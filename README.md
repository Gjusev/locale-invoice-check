<p align="center">
  <img src="https://raw.githubusercontent.com/Gjusev/locale-invoice-check/main/docs/assets/logo.png" width="100" height="100" alt="locale-invoice-check logo">
</p>

<h1 align="center">locale-invoice-check</h1>

<p align="center"><strong>Same invoice. Three locales. Measure the difference.</strong></p>

[![PyPI](https://img.shields.io/pypi/v/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![Python](https://img.shields.io/pypi/pyversions/locale-invoice-check)](https://pypi.org/project/locale-invoice-check/)
[![CI](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml/badge.svg)](https://github.com/Gjusev/locale-invoice-check/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/Gjusev/locale-invoice-check/blob/main/LICENSE)

[Quick start](#quick-start-no-credentials) · [Metrics](#what-it-measures) ·
[Python API](#python-api) · [Run on Kaggle](https://www.kaggle.com/code/gjusev/locale-invoice-check-demo)

An invoice parser can read `1,234.56` correctly and misread `1.234,56`.
This Python CLI makes that regression reproducible: render the **same synthetic
invoice data as English, German, and Spanish PNGs**, run your extractor, and
compare field accuracy with deterministic CI gates.

Matched triplets vary labels, numeric separators, date formats, and currency
placement while keeping the underlying business data and layout controlled.
Live-provider nondeterminism can still affect results; a delta is a signal to
investigate, not proof of its cause.

**Offline demo · No API key · No LLM judge · Standalone HTML · Python 3.10+**

Fields in v0.1 (exact set): `invoice_number`, `invoice_date`, `net_amount`,
`tax_amount`, `total_amount`.

## Quick start (no credentials)

```bash
pip install locale-invoice-check
locale-check demo
```

**Exit 1 is expected.** The bundled baseline deliberately misreads DE/ES money
separators. Open `report.html` to see wrong amounts in red, with expected and
actual values. Every failed field also appears in `review-queue.json`.
The baseline reads PNG text metadata; it is an OCR surrogate, not an OCR engine.

To exercise the passing exit path with the same seeded failures:

```bash
locale-check demo --min-field-accuracy 0 --max-locale-delta 1 --max-money-error-rate 1
```

These permissive thresholds are for the demo only. They do not fix the extractor.
After installation, both commands run entirely offline.

<a href="https://github.com/Gjusev/locale-invoice-check/releases/download/v0.1.1/brag.mp4">
  <img src="https://github.com/Gjusev/locale-invoice-check/releases/download/v0.1.1/brag.gif" alt="Demo: EN invoices parse perfectly while the seeded regex bug trips DE and ES money separators; the strict gate exits 1" width="720">
</a>

Or [reproduce it on Kaggle](https://www.kaggle.com/code/gjusev/locale-invoice-check-demo).

To retain and reuse the corpus separately from evaluation:

```bash
locale-check generate fixtures --count 30 --seed 42
locale-check run fixtures --extractor regex --json --output result.json
```

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
export VISION_API_KEY="your-api-key"      # required
export VISION_MODEL="your-vision-model"  # required
export VISION_BASE_URL=https://api.openai.com/v1   # optional, this is the default
locale-check run fixtures --extractor llm
```

In PowerShell, use `$env:VISION_API_KEY = "..."` and
`$env:VISION_MODEL = "..."` instead of `export`. Choose a vision endpoint/model
compatible with the adapter's request settings. Requests and errors are tested
offline via `httpx.MockTransport`; the demo does not establish live-model performance.

## What it measures

With `N` = number of invoices and five fields:

| Metric | Definition | What it tells you |
|---|---|---|
| `field_accuracy[locale][field]` | Correct values / N | Which of the 15 field/locale combinations regressed |
| `locale_accuracy[locale]` | Correct values / (5 × N) | Overall extraction accuracy in each locale |
| `locale_delta` | Worst locale accuracy − EN accuracy | Signed drop; 12 percentage points is `-0.12` |
| `money_error_rate[locale]` | Invoices with any wrong amount / N | How often money fields need attention |
| `date_swap_rate[locale]` | Observable day/month inversions / N | How often an ambiguous date was inverted |

All scoring is deterministic; no LLM judge is involved.

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
from locale_invoice_check import (
    RegexBaselineExtractor,
    evaluate_corpus,
    generate_corpus,
)

generate_corpus("fixtures", count=30, seed=42)          # 30 x EN/DE/ES PNGs
result = evaluate_corpus("fixtures", RegexBaselineExtractor())
print(result["metrics"]["locale_delta"])
print(result["passed"])
```

`python -m locale_invoice_check` works wherever the console script is not on
your PATH.

## Reproducibility

- Generation is seeded (`--seed`). The manifest records seed, renderer
  configuration (Pillow version), relative image paths, and SHA-256 hashes.
  Loading a corpus verifies every hash. Keep the renderer environment fixed
  when you need byte-identical regeneration; seeded values alone do not pin Pillow.
- Results contain no timestamps or absolute paths. Runs are deterministic offline.
- The corpus is entirely synthetic: no real invoices, no personal data. It is
  Apache-2.0 licensed with the code.

## Reproduce in Kaggle

[Open the public CPU kernel](https://www.kaggle.com/code/gjusev/locale-invoice-check-demo).
It installs the published `locale-invoice-check==0.1.2` from PyPI.

`kaggle-kernel/offline/script.py` plus `kaggle-kernel/kernel-metadata.json`
define a public CPU kernel (`enable_gpu: false`, `enable_internet: true`;
internet is only needed for the pip install). It runs the offline demo with
relaxed gates, which are explicitly not recommended production thresholds,
prints a summary, and writes `result.json`, `report.html`, and
`review-queue.json` to `/kaggle/working`.

Authenticate with a Kaggle API token (never commit it):

```bash
export KAGGLE_API_TOKEN="your-token"
kaggle kernels push -p kaggle-kernel
kaggle kernels status gjusev/locale-invoice-check-demo
kaggle kernels output gjusev/locale-invoice-check-demo -p ./kernel-output
```

PowerShell: `$env:KAGGLE_API_TOKEN = "your-token"`. To publish a fork, update
the kernel owner/id in `kernel-metadata.json` first.

## Why this exists

On **September 29, 2026**, OpenAI introduced
[GPT-6.1 Sol](https://openai.com/index/introducing-gpt-6-1-sol/), highlighting
document understanding and professional workflows. That motivates a narrower
deployment question: does your extractor preserve accuracy when invoice
conventions change? This package supplies the experiment, not evidence of a
defect in that model.

## Related benchmarks

Real document-extraction benchmarks exist, and they are more representative of
production traffic than this corpus:

- **[DocILE](https://docile.rossum.ai/)** (ICDAR 2023, Rossum) has ~6.7k annotated business documents as
  PDFs for key information localization and line-item recognition. Large and
  realistic, but the documents are not locale-controlled matched pairs.
- **[DocuBench](https://www.docupipe.ai/benchmarks/docubench)** (DocuPipe) scores real-world documents with JSON schemas and
  hand-verified labels on macro-average field accuracy.
- **[Omni Extract Bench](https://github.com/datalab-to/omni_extract_bench)** (Datalab) is an extraction benchmark toolkit with
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
- Date-swap detection observes inversions only when `day <= 12` and `day != month`.
- Confidence comes only from adapters that provide it.

## Development

```bash
make install   # uv sync
make test      # pytest, network hard-blocked
make lint      # Ruff: src, tests, and Kaggle scripts; line-length 100
make build
make demo      # strict demo must exit 1, relaxed must exit 0
```

Without Make: `uv sync`, `uv run ruff check src tests kaggle-kernel`,
`uv run pytest -q -m "not live"`, and `uv build`.

CI (`.github/workflows/test.yml`) runs Ruff and offline pytest on Python
3.10-3.13, asserts strict exit 1 and relaxed exit 0, builds the wheel, and smoke-tests
it in a clean venv. Publishing (`.github/workflows/publish.yml`) uses `uv build`
and `uv publish` via Trusted Publishing on `release: published`. No tokens are
stored.

## License

[Apache-2.0](LICENSE) · [Logos and social preview](docs/assets/README.md)
