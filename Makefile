.PHONY: help sync fmt lint typecheck test check

help: ## Show available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

sync: ## Install dependencies from the lockfile
	uv sync

fmt: ## Format code and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Check formatting and lint rules (no changes)
	uv run ruff format --check .
	uv run ruff check .

typecheck: ## Run mypy in strict mode
	uv run mypy

test: ## Run the test suite
	uv run pytest

check: lint typecheck test ## Everything CI runs: lint, types, tests
