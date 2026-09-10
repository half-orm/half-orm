# PostgreSQL port used by the test database. The .config/* connection files
# deliberately omit `port` so that libpq resolves it from PGPORT, which
# defaults to 5432 here — the same port they used to hard-code. Point the
# tests at another cluster with `make py_test PGPORT=5435`, or by exporting
# PGPORT in the environment.
PGPORT ?= 5432
export PGPORT

release: test
	@python3 scripts/do_release.py

py_test:
	export LC_MESSAGES=C PYTHONPATH=$$PWD HALFORM_CONF_DIR=$$PWD/.config && pytest -x -vv --assert=plain --cov-config=.coveragerc --cov=half_orm --cov-report html test
	flake8 half_orm --count --select=E9,F63,F7,F82 --show-source --statistics

test: clean_coverage py_test

build: test clean_build
	python -m build

clean: clean_coverage clean_build

clean_coverage:
	rm -rf htmlcov

clean_build:
	rm -rf dist

docs-deps:
	pip install -r docs/requirements.txt

docs: docs-deps
	mkdocs build

docs-serve: docs-deps
	mkdocs serve

check_publish_ready:
	@git diff --quiet && git diff --cached --quiet || { echo "ERROR: repository is not clean."; exit 1; }
	@git describe --tags --exact-match --match 'v[0-9]*.[0-9]*.[0-9]*' HEAD > /dev/null 2>&1 || { echo "ERROR: HEAD has no vX.Y.Z[-...] tag."; exit 1; }
	@echo "OK: $(shell git describe --exact-match HEAD)"

publish: check_publish_ready build
	-git push origin $(shell git describe --exact-match HEAD)
	twine upload -r half-orm dist/*
