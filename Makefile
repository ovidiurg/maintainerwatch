PYTHON ?= python3

.PHONY: install install-release test lint build check dataset-check validation-sample validation-eval docker docker-run docker-report maintain snapshot validate clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

install-release:
	$(PYTHON) -m pip install -e ".[dev,release]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m compileall -q src scripts tests

build:
	$(PYTHON) -m build

check: test build dataset-check
	$(PYTHON) -m twine check dist/*

docker:
	docker build -t maintainerwatch:latest .

docker-run:
	docker run --rm -p 8000:8000 \
		-v "$$(pwd)/data:/app/data" \
		--user "$$(id -u):$$(id -g)" \
		maintainerwatch:latest

docker-report:
	docker compose run --rm api mw report --out /app/data/report.html

maintain:
	mw maintain

snapshot:
	mw snapshot

dataset-check:
	$(PYTHON) scripts/check_validation_dataset.py

validation-sample:
	$(PYTHON) scripts/prepare_validation_sample.py

validation-eval:
	$(PYTHON) -m mw.cli evaluate-validation --config config/validation.yaml

validate:
	$(PYTHON) scripts/incident_check.py

clean:
	rm -rf build dist *.egg-info .pytest_cache
