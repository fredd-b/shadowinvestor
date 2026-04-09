.PHONY: help install init check test lint dashboard clean

help:
	@echo "make install      - Create venv and install package + dev deps"
	@echo "make init         - Initialize SQLite DB (apply migrations)"
	@echo "make check        - Validate all YAML configs"
	@echo "make test         - Run pytest"
	@echo "make lint         - Run ruff lint + format check"
	@echo "make dashboard    - Start Streamlit dashboard (Phase 1)"
	@echo "make clean        - Remove build artifacts and DB"

install:
	uv venv
	. .venv/bin/activate && uv pip install -e ".[ml,dev]"

init:
	fesi init-db

check:
	fesi config-check

test:
	pytest -v

lint:
	ruff check src tests
	ruff format --check src tests

dashboard:
	streamlit run src/fesi/ops/dashboard.py

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	rm -f data/fesi.db
