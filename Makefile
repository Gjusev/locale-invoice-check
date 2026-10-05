.PHONY: install test lint build demo check

install:
	uv sync

test:
	uv run pytest -q -m "not live"

lint:
	uv run ruff check src tests kaggle-kernel

build:
	uv build

# The strict demo exits 1 by design (seeded parser bug in the regex baseline):
# first command asserts exit code exactly 1, then the relaxed demo must exit 0.
# Artifacts (result.json, report.html, review-queue.json) land in the current
# directory and are gitignored.
demo:
	@uv run locale-check demo --count 4 --seed 42; \
	status=$$?; \
	if [ $$status -ne 1 ]; then echo "strict demo should exit 1, got $$status" >&2; exit 1; fi; \
	echo "strict demo exited 1 as expected (seeded DE/ES parser bug)"; \
	uv run locale-check demo --count 4 --seed 42 \
		--min-field-accuracy 0 --max-locale-delta 1 --max-money-error-rate 1

check: lint test demo
