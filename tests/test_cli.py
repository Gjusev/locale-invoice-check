"""CLI exit codes: 0 gates pass, 1 gates fail (artifacts written), 2 config error."""

from __future__ import annotations

import json

from locale_invoice_check import cli

RELAXED = ["--min-field-accuracy", "0", "--max-locale-delta", "1",
           "--max-money-error-rate", "1"]


def test_run_strict_regex_fails_with_exit_1(corpus, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = cli.main(["run", str(corpus), "--extractor", "regex"])
    assert code == 1
    for name in ("result.json", "report.html", "review-queue.json"):
        assert (tmp_path / name).exists(), name  # artifacts written despite gate fail


def test_run_relaxed_regex_passes_with_exit_0(corpus, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = cli.main(["run", str(corpus), "--extractor", "regex", *RELAXED])
    assert code == 0
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["passed"] is True
    assert result["schema_version"] == "1.0"


def test_run_json_flag_prints_only_json(capfd, corpus, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = cli.main(["run", str(corpus), "--extractor", "regex", "--json", *RELAXED])
    captured = capfd.readouterr()
    assert code == 0
    parsed = json.loads(captured.out)  # stdout must be pure JSON, nothing else
    assert parsed["schema_version"] == "1.0"
    assert captured.err == ""


def test_demo_strict_exits_1_seeded_bug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = cli.main(["demo", "--count", "4", "--seed", "42"])
    assert code == 1  # strict gates: seeded DE/ES money bug


def test_demo_relaxed_exits_0(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = cli.main(["demo", "--count", "4", "--seed", "42", *RELAXED])
    assert code == 0


def test_corrupt_manifest_exits_2(tmp_path, monkeypatch):
    from locale_invoice_check.corpus import generate_corpus
    generate_corpus(tmp_path, count=1, seed=1)
    manifest_path = tmp_path / "manifest.json"
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    doc["schema_version"] = "0.0"
    manifest_path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.chdir(tmp_path / "..")
    code = cli.main(["run", str(tmp_path), "--output", "out.json",
                     "--html", "out.html", "--review-output", "out.queue"])
    assert code == 2
