# HTB Discord Service Makefile

.PHONY: install dev test lint format clean run validate generate-config help

# Default target
help:
	@echo "HTB Discord Service Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install          Install dependencies using uv"
	@echo "  dev              Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  run              Run the service in development mode"
	@echo "  validate         Validate configuration file"
	@echo "  generate-config  Generate sample configuration"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linting (ruff)"
	@echo "  format           Format code (black + ruff)"
	@echo "  typecheck        Run type checking (mypy)"
	@echo "  test             Run tests"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean            Clean generated files"
	@echo "  update           Update dependencies"

# Installation
install:
	uv sync

dev:
	uv sync --group dev

# Development
run:
	uv run htb-discord

validate:
	uv run htb-discord validate

generate-config:
	uv run htb-discord generate-config

# Code quality
lint:
	uv run ruff check .

format:
	uv run black .
	uv run ruff check --fix .

typecheck:
	uv run mypy src/

test:
	uv run pytest

# Maintenance
clean:
	rm -rf .uv/
	rm -rf .mypy_cache/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf dist/
	rm -rf build/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

update:
	uv lock --upgrade

# Service management (requires sudo)
install-service:
	sudo ./install.sh

start-service:
	sudo systemctl start htb-discord

stop-service:
	sudo systemctl stop htb-discord

status-service:
	sudo systemctl status htb-discord

logs:
	sudo journalctl -u htb-discord -f