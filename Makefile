PYTHON ?= python3
CANDIDATE ?= config/calibration-candidate.yaml
LABELS_INPUT ?= data/feedback/packages.jsonl

.PHONY: install install-release test lint build check dataset-check validation-sample validation-eval docker docker-run docker-report docker-smoke calibration calibration-loop calibration-search replay-v4 ci-index ci-publish-index label-intake onboarding-metrics high-band-review demo-db team-report calibration-drift main maintain snapshot validate clean

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
	$(PYTHON) -m twine check dist/*.whl dist/*.tar.gz

docker:
	docker build -t maintainerwatch:latest .

docker-run:
	docker run --rm -p 8000:8000 \
		-v "$$(pwd)/data:/app/data" \
		--user "$$(id -u):$$(id -g)" \
		maintainerwatch:latest

docker-report:
	docker compose run --rm api mw report --out /app/data/report.html

docker-smoke:
	bash scripts/docker_smoke.sh

calibration:
	$(PYTHON) -m mw.cli calibrate --candidate $(CANDIDATE)

calibration-search:
	$(PYTHON) -m mw.cli calibrate --search --bootstrap 1000 --out data/calibration/search.json

calibration-loop:
	bash scripts/calibration_loop.sh

replay-v4:
	$(PYTHON) scripts/validation_replay.py --dataset validation/v4 --config config/validation-v4.yaml --out data/validation-v4/replay.json
	$(PYTHON) scripts/replay_drift.py

ci-index:
	$(PYTHON) scripts/build_ci_index.py --out dist/maintainerwatch-index.json

ci-publish-index:
	PYTHON=$(PYTHON) bash scripts/publish_ci_index.sh

team-report:
	$(PYTHON) -m mw.cli team-report --root . --index dist/maintainerwatch-index.json --out data/team-report.html

	$(PYTHON) scripts/build_demo_db.py

high-band-review:
	$(PYTHON) scripts/high_band_review.py

onboarding-metrics:
	$(PYTHON) scripts/onboarding_metrics.py

calibration-drift:
	$(PYTHON) scripts/calibration_drift.py

label-intake:
	$(PYTHON) scripts/intake_osv_labels.py --input $(LABELS_INPUT)

main:
	$(PYTHON) -m mw.cli main

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
