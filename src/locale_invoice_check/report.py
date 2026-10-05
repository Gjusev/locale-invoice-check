"""Self-contained, escaped HTML. No server, scripts, or external resources."""

from __future__ import annotations

import base64
import io
from html import escape
from pathlib import Path

from PIL import Image

from .corpus import FIELDS, LOCALES
from .scoring import summary


def write_report(result: dict, corpus_dir: str | Path, output: str | Path) -> None:
    rows = []
    for invoice in result["invoices"]:
        columns = []
        for locale in LOCALES:
            data = invoice["locales"][locale]
            with Image.open(Path(corpus_dir) / data["image"]) as image:
                image.thumbnail((450, 270))
                buffer = io.BytesIO()
                image.save(buffer, "PNG")
            uri = base64.b64encode(buffer.getvalue()).decode("ascii")
            cells = []
            for field in FIELDS:
                cell = data["fields"][field]
                status = "pass" if cell["passed"] else "fail"
                details = f"expected {cell['expected']} | got {cell['got']}"
                cells.append(f'<li class="{status}">{escape(field)}: {status.upper()} '
                             f'<small>{escape(details)}</small></li>')
            columns.append(f'<td><img alt="{locale} synthetic invoice" '
                           f'src="data:image/png;base64,{uri}"><ul>{"".join(cells)}</ul></td>')
        rows.append(f"<tr><th>{escape(invoice['id'])}</th>{''.join(columns)}</tr>")
    metrics = result["metrics"]
    metric_rows = []
    for field in FIELDS:
        values = "".join(f"<td>{metrics['field_accuracy'][loc][field]:.2%}</td>" for loc in LOCALES)
        metric_rows.append(f"<tr><th>{field}</th>{values}</tr>")
    for metric in ("locale_accuracy", "money_error_rate", "date_swap_rate"):
        values = "".join(f"<td>{metrics[metric][loc]:.2%}</td>" for loc in LOCALES)
        metric_rows.append(f"<tr><th>{metric}</th>{values}</tr>")
    queue = "".join("<tr>" + "".join(f"<td>{escape(str(row[key]))}</td>" for key in
                                  ("invoice_id", "locale", "field", "expected", "got", "reasons"))
                    + "</tr>" for row in result["review_queue"])
    gate_rows = "".join(f"<li>{escape(g['name'])}: {'PASS' if g['passed'] else 'FAIL'} "
                        f"({g['measured']:.4f}; threshold {g['threshold']:.4f})</li>"
                        for g in result["gates"])
    note = ("Offline baseline: rendered-text metadata is an OCR surrogate. The number parser "
            "intentionally assumes English separators. These are synthetic failures, "
            "not model scores."
            if result["extractor"] == "RegexBaselineExtractor" else
            "Synthetic matched-pair evaluation. These results apply only to this corpus and run.")
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Locale Invoice Check</title><style>
body{{font:15px system-ui;margin:30px;color:#142b40;background:#f6f8fa}}
table{{border-collapse:collapse;width:100%;background:white;margin:20px 0}}
td,th{{border:1px solid #cad3dc;padding:12px;text-align:left;vertical-align:top}}
img{{width:100%;max-width:450px}}small{{display:block}}li{{margin:8px 0}}
.fail{{color:#a11323}}.pass{{color:#116538}}pre{{white-space:pre-wrap}}
</style><h1>Locale Invoice Check</h1><p>{escape(note)}</p>
<table><tr><th>Invoice</th><th>EN</th><th>DE</th><th>ES</th></tr>
{''.join(rows)}</table>
<h2>Metrics summary</h2><pre>{escape(summary(result))}</pre>
<table><tr><th>Metric</th><th>EN</th><th>DE</th><th>ES</th></tr>
{''.join(metric_rows)}</table>
<h2>Gates</h2><ul>{gate_rows}</ul>
<h2>Review queue</h2><table><tr><th>Invoice</th><th>Locale</th>
<th>Field</th><th>Expected</th><th>Got</th><th>Reasons</th></tr>{queue}</table></html>'''
    Path(output).write_text(html, encoding="utf-8")
