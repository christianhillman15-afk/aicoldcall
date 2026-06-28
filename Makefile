.PHONY: install dev test lint fmt init demo serve run report clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests

fmt:
	ruff check --fix src tests

init:
	coldy init

# End-to-end local demo WITHOUT placing real calls.
demo:
	coldy init
	coldy import data/sample_leads.csv --campaign demo
	coldy consent add --phone "+16125550142" --source "demo seed (sample only)"
	coldy campaign start demo
	coldy run --campaign demo --dry-run
	coldy report --campaign demo

serve:
	coldy serve

run:
	coldy run --campaign $(CAMPAIGN)

report:
	coldy report --campaign $(CAMPAIGN)

clean:
	rm -f coldy.db
	find . -type d -name __pycache__ -exec rm -rf {} +
