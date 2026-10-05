"""Offline demo of locale-invoice-check on a Kaggle CPU kernel.

Installs locale-invoice-check==0.1.2 from PyPI, generates synthetic matched
EN/DE/ES invoice triplets locally, and runs the fully offline regex-baseline
demo. No network is needed after the pip install; no credentials are used.

The RELAXED gates below are explicitly NOT production thresholds. The bundled
regex baseline carries an intentional number-parsing bug that must fail on
DE/ES (strict default gates exit 1 by design); the relaxed values only make
the demo terminate successfully for illustration.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORK = Path("/kaggle/working")
WORK.mkdir(parents=True, exist_ok=True)

print("Installing locale-invoice-check==0.1.2 from PyPI ...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "locale-invoice-check==0.1.2"],
    check=True,
)

command = [
    sys.executable, "-m", "locale_invoice_check", "demo",
    "--count", "30",
    "--seed", "42",
    # Relaxed gates for demonstration only -- not recommended production values.
    "--min-field-accuracy", "0",
    "--max-locale-delta", "1",
    "--max-money-error-rate", "1",
    "--output", str(WORK / "result.json"),
    "--html", str(WORK / "report.html"),
    "--review-output", str(WORK / "review-queue.json"),
]
print("Running:", " ".join(command))
run = subprocess.run(command, capture_output=True, text=True)
print(run.stdout)
if run.stderr:
    print(run.stderr, file=sys.stderr)
if run.returncode != 0:
    raise SystemExit(f"locale-check demo failed with exit code {run.returncode}")

result = json.loads((WORK / "result.json").read_text(encoding="utf-8"))
metrics = result["metrics"]
print("=== locale-invoice-check offline demo summary ===")
print("extractor:", result["extractor"])
for locale in result["locales"]:
    accuracy = metrics["locale_accuracy"][locale]
    money = metrics["money_error_rate"][locale]
    print(f"{locale}: locale_accuracy={accuracy:.2%} money_error_rate={money:.2%}")
print("locale_delta:", f"{metrics['locale_delta']:+.2%}")
print("gates:", "PASS" if result["passed"] else "FAIL")
print("Artifacts written to /kaggle/working: result.json, report.html, review-queue.json")
