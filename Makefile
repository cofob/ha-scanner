# Makefile for print-scanner project

.PHONY: help install dev-install list scan dev-api clean lint format test

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

dev-install: install  ## Install with dev dependencies
	uv sync --all-extras

list:  ## List available scanner devices
	uv run python main.py --list

scan:  ## Scan a document (interactive)
	uv run python main.py --scan --output "scan_{dateandtime}.{format_suffix}" --format jpeg

dev-api:  ## Run development API server
	uv run python -m app.main

clean:  ## Clean generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -name "scan_*.jpeg" -delete
	find . -name "scan_*.png" -delete

lint:  ## Run linting (if tools are available)
	-uv run ruff check .
	-uv run mypy .

format:  ## Format code (if tools are available)
	-uv run ruff format .

test:  ## Run tests (if available)
	-uv run pytest

# Docker targets for addon development
docker-build:  ## Build the Home Assistant addon Docker image
	cd addon/scanner && docker build -t ha-scanner:dev .

docker-run:  ## Run the addon Docker image locally (for testing)
	docker run --rm -it \
		-p 46201:46201 \
		-v $(PWD)/test-data:/data \
		-v $(PWD)/test-media:/media \
		--privileged \
		ha-scanner:dev