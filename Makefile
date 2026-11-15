# Commerce Intelligence Platform - one command rebuilds everything from the raw CSVs.
PY ?= python3
export PYTHONPATH := src

.PHONY: all data warehouse analyze bi report notebook test lint clean help

help:
	@echo "make all        download data, build warehouse, run analyses, export BI, build dashboard"
	@echo "make data       download + validate the 11 raw Olist CSVs (~125 MB)"
	@echo "make warehouse  dbt build (staging views + star-schema marts + 59 tests) into DuckDB"
	@echo "make analyze    run all 12 analysis modules -> reports/tables, reports/figures, results.json"
	@echo "make bi         export CSV/Parquet marts + Tableau .hyper extract"
	@echo "make report     build reports/dashboard.html (+ docs/index.html for GitHub Pages)"
	@echo "make notebook   execute notebooks/commerce_intelligence_walkthrough.ipynb in place"
	@echo "make test       pytest (data contracts, metric reconciliation, model sanity)"

all: data warehouse analyze bi report

data:
	$(PY) -m commerce_intel data

warehouse:
	$(PY) -m commerce_intel warehouse

analyze:
	$(PY) -m commerce_intel analyze

bi:
	$(PY) -m commerce_intel bi

report:
	$(PY) -m commerce_intel report

notebook:
	jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/commerce_intelligence_walkthrough.ipynb

test:
	pytest -q

lint:
	ruff check src tests

clean:
	rm -rf data/warehouse/*.duckdb dbt/target dbt/logs reports/tables reports/figures bi/data bi/tableau/*.hyper
