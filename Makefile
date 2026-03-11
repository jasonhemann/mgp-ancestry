.PHONY: format lint typecheck test check viz-gephi-open viz-graphviz

BLACK = .venv/bin/black
ISORT = .venv/bin/isort
FLAKE8 = .venv/bin/flake8
MYPY = .venv/bin/mypy
PYTEST = .venv/bin/pytest

format:
	$(BLACK) src tests
	$(ISORT) src tests

lint:
	$(FLAKE8) src tests

typecheck:
	$(MYPY) --config-file pyproject.toml src tests

test:
	$(PYTEST)

check: lint typecheck test

INPUT ?= out/lineage_75750.json
ID ?= 75750
FORMAT ?= all

viz-gephi-open:
	$(MAKE) -C viz gephi-open

viz-graphviz:
	$(MAKE) -C viz graphviz-render INPUT="$(abspath $(INPUT))" ID="$(ID)" FORMAT="$(FORMAT)"
