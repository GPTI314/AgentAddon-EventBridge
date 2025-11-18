.PHONY: help install lint typecheck test coverage clean format

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Format code with ruff"
	@echo "  make typecheck  - Run mypy type checker"
	@echo "  make test       - Run tests"
	@echo "  make coverage   - Run tests with coverage"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make ci         - Run all CI checks (lint + typecheck + coverage)"

install:
	pip install -r requirements.txt

lint:
	ruff check app tests

format:
	ruff check --fix app tests
	ruff format app tests

typecheck:
	mypy app

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

ci: lint typecheck coverage
	@echo "✓ All CI checks passed!"
