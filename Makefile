.PHONY: help install dev-install format lint test clean build
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -e .

dev-install: ## Install with development dependencies
	pip install -e ".[dev]"

format: ## Format code with black and isort
	black ytmusic_cli/ tests/
	isort ytmusic_cli/ tests/

lint: ## Run all linters
	black --check ytmusic_cli/ tests/
	isort --check-only ytmusic_cli/ tests/
	ruff check ytmusic_cli/ tests/
	mypy ytmusic_cli/

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=ytmusic_cli --cov-report=html --cov-report=term

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
	python -m build

run: ## Run the application
	python -m ytmusic_cli

dev: ## Run in development mode with textual dev tools
	textual run --dev ytmusic_cli/main.py

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

setup-pre-commit: ## Setup pre-commit hooks
	pre-commit install
