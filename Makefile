.PHONY: format lint typecheck test check

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
