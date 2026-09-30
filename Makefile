.PHONY: setup indexes seed synonyms smoke evaluate test run dist verify-dist

PORT ?= 8035

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

indexes:
	PYTHONPATH=. .venv/bin/python scripts/create_indexes.py

seed:
	PYTHONPATH=. .venv/bin/python scripts/seed_findcare.py

synonyms:
	PYTHONPATH=. .venv/bin/python scripts/seed_synonyms.py

smoke:
	PYTHONPATH=. .venv/bin/python scripts/smoke_search.py

evaluate:
	PYTHONPATH=. .venv/bin/python scripts/evaluate_search.py

test:
	PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -v
	node --check static/app.js

run:
	PORT=$(PORT) ./run.sh

dist:
	PYTHONPATH=. .venv/bin/python scripts/build_dist.py

verify-dist: dist
	PYTHONPATH=. .venv/bin/python scripts/verify_dist.py
