.PHONY: help install dev-install format lint test test-cov clean build run dev pre-commit setup-pre-commit
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev-install: ## Install with development dependencies
	uv sync --all-groups

format: ## Format code and organize imports with ruff
	uv run ruff format ytmusic_cli/ tests/
	uv run ruff check --fix ytmusic_cli/ tests/

lint: ## Run all linters (ruff format check, ruff lint, mypy)
	uv run ruff format --check ytmusic_cli/ tests/
	uv run ruff check ytmusic_cli/ tests/
	uv run mypy ytmusic_cli/

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=ytmusic_cli --cov-report=html --cov-report=term

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: ## Build the package
	uv build

run: ## Run the application
	uv run ytmusic-cli

dev: ## Run in development mode with textual dev tools
	uv run textual run --dev ytmusic_cli/main.py

pre-commit: ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

setup-pre-commit: ## Setup pre-commit hooks
	uv run pre-commit install
