PYTHON ?= python3.11
CASE ?= examples/company.json
OUT ?= output

.PHONY: example
example: .venv/.dependencies
	.venv/bin/python value.py "$(CASE)" --out "$(OUT)"

.venv/.dependencies: requirements.lock
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --require-hashes -r requirements.lock
	touch $@
