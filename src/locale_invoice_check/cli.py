"""Exit 0: gates pass; 1: gates fail; 2: configuration, data, or transport error."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .corpus import generate_corpus
from .extractors import LLMExtractor, RegexBaselineExtractor
from .report import write_report
from .scoring import evaluate_corpus, summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="locale-check")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="generate synthetic matched PNG triplets")
    generate.add_argument("directory", nargs="?", default="fixtures")
    generate.add_argument("--count", type=int, default=30)
    generate.add_argument("--seed", type=int, default=42)
    for name in ("run", "demo"):
        command = sub.add_parser(name)
        if name == "run":
            command.add_argument("directory")
            command.add_argument("--extractor", choices=("regex", "llm"), default="regex")
        else:
            command.add_argument("--count", type=int, default=30)
            command.add_argument("--seed", type=int, default=42)
        command.add_argument("--min-field-accuracy", type=float, default=0.95)
        command.add_argument("--max-locale-delta", type=float, default=0.05)
        command.add_argument("--max-money-error-rate", type=float, default=0.05)
        command.add_argument("--max-date-swap-rate", type=float, default=0)
        command.add_argument("--min-confidence", type=float, default=0.8)
        command.add_argument("--json", action="store_true", help="JSON only on stdout")
        command.add_argument("--output", default="result.json")
        command.add_argument("--html", default="report.html")
        command.add_argument("--review-output", default="review-queue.json")
    return parser


def _run(args, directory: str) -> int:
    outputs = [Path(p).resolve() for p in (args.output, args.html, args.review_output)]
    if len(set(outputs)) != len(outputs):
        raise ValueError("output paths must be distinct")
    if any(path.is_relative_to(Path(directory).resolve()) for path in outputs):
        raise ValueError("write reports outside the input corpus directory")
    extractor = LLMExtractor.from_env() if getattr(args, "extractor", "regex") == "llm" else \
        RegexBaselineExtractor()
    try:
        result = evaluate_corpus(directory, extractor,
                                 min_field_accuracy=args.min_field_accuracy,
                                 max_locale_delta=args.max_locale_delta,
                                 max_money_error_rate=args.max_money_error_rate,
                                 max_date_swap_rate=args.max_date_swap_rate,
                                 min_confidence=args.min_confidence)
    finally:
        if isinstance(extractor, LLMExtractor):
            extractor.close()
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    write_report(result, directory, args.html)
    Path(args.output).write_text(serialized, encoding="utf-8")
    Path(args.review_output).write_text(json.dumps({"schema_version": "1.0",
                                      "review_queue": result["review_queue"]}, indent=2,
                                      ensure_ascii=False) + "\n", encoding="utf-8")
    print(serialized if args.json else summary(result), end="" if args.json else "\n")
    return 0 if result["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            print(generate_corpus(args.directory, args.count, args.seed))
            return 0
        if args.command == "demo":
            with tempfile.TemporaryDirectory(prefix="locale-check-") as directory:
                generate_corpus(directory, args.count, args.seed)
                return _run(args, directory)
        return _run(args, args.directory)
    except (ValueError, OSError, RuntimeError, ImportError, KeyError, TypeError,
            ArithmeticError) as error:
        print(f"locale-check: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
