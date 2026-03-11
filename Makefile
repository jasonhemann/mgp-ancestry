.PHONY: sync format lint lint-fix typecheck test coverage check viz-gephi-open viz-graphviz

INPUT ?= out/lineage_75750.json
ID ?= 75750
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

check: lint typecheck test

viz-gephi-open:
	$(MAKE) -C viz gephi-open

viz-graphviz:
	$(MAKE) -C viz graphviz-render INPUT="$(abspath $(INPUT))" ID="$(ID)" FORMAT="$(FORMAT)"
