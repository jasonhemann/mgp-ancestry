.PHONY: sync format lint lint-fix typecheck test coverage check viz-gephi-open viz-graphviz repo-hygiene

INPUT ?=
ID ?=
FORMAT ?= all

sync:
	uv sync --group dev

format:
	uv run ruff format src tests

lint:
	uv run ruff check src tests

lint-fix:
	uv run ruff check src tests --fix

typecheck:
	uv run basedpyright

test:
	uv run pytest -q

coverage:
	@echo "Coverage target (warn-only in wave 1): 80%"
	uv run pytest --cov=src/genealogy_tree --cov-report=term-missing -q

check: repo-hygiene lint typecheck test

repo-hygiene:
	bash scripts/check_tracked_runtime_artifacts.sh

viz-gephi-open:
	$(MAKE) -C viz gephi-open INPUT="$(abspath $(INPUT))"

viz-graphviz:
	@if [ -z "$(INPUT)" ] || [ -z "$(ID)" ]; then \
		echo "Usage: make viz-graphviz INPUT=out/lineage_<id>.json ID=<id> [FORMAT=svg|png|dot|all]"; \
		exit 1; \
	fi
	$(MAKE) -C viz graphviz-render INPUT="$(abspath $(INPUT))" ID="$(ID)" FORMAT="$(FORMAT)"
