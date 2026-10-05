"""HTML report: escaping of extractor output, base64 thumbnails, structure."""

from __future__ import annotations

from locale_invoice_check.report import write_report
from locale_invoice_check.scoring import evaluate_corpus


def test_report_escapes_hostile_extractor_output(corpus, tmp_path):
    class Hostile:
        def extract(self, image_path, field_list):
            return dict.fromkeys(field_list, "<script>alert(1)</script>")

    result = evaluate_corpus(corpus, Hostile(), min_field_accuracy=0.0,
                             max_locale_delta=1.0, max_money_error_rate=1.0)
    out = tmp_path / "report.html"
    write_report(result, corpus, out)
    html = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "data:image/png;base64," in html
    assert "Review queue" in html
    assert 'class="fail"' in html  # money errors and other failures in red
