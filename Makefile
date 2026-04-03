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

check_publish_ready:
	@git diff --quiet && git diff --cached --quiet || { echo "ERROR: repository is not clean."; exit 1; }
	@git describe --tags --exact-match --match 'v[0-9]*.[0-9]*.[0-9]*' HEAD > /dev/null 2>&1 || { echo "ERROR: HEAD has no vX.Y.Z[-...] tag."; exit 1; }
	@echo "OK: $(shell git describe --exact-match HEAD)"

publish: check_publish_ready build
	-git push origin $(shell git describe --exact-match HEAD)
	twine upload -r half-orm dist/*
