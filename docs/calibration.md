# Feedback and calibration loop

`mw calibrate` compares a candidate weight configuration with the current
baseline on the temporal validation samples. It does not retrain or silently
change the model.

## What it evaluates

- v1 case-control sample
- v2 full sample
- v2 temporal test slice (`>= 2026-01-01`)
- v5 fresh current-state diagnostic when `config/validation-v5.yaml` exists
- AUC, PR-AUC, Brier score and precision/recall/FPR at thresholds 25/40/50/60
- high-band precision, recall and false-positive rate
- evidence coverage and score distribution

The candidate weights are applied to the signal values already stored in the
validation databases, so the command is fast and does not use post-cutoff
labels to recompute candidate scores.

v5 is shown as a **diagnostic** row only. It is not part of the search
selection or the v2 guardrails; do not tune on it.

## Workflow

```bash
# Start from the current model.
cp config/default.yaml config/calibration-candidate.yaml
# Edit only weights/model_version in the candidate file.

mw calibrate \
  --candidate config/calibration-candidate.yaml \
  --fail-on-regression

cat data/calibration.md
```

The persistent history lives in `validation/calibration/history.jsonl` and is
committed. Run reports are local under `data/calibration/`.

```bash
make calibration-loop
cat docs/validation/calibration-drift.md
```

The loop deliberately runs only the baseline history/drift step. It does **not**
run a new weight search automatically, because repeatedly searching the same
v2 test slice would overfit the holdout. Run `mw calibrate --search` manually
only when you have a new/rolling holdout.

## Guardrails

The candidate fails when the v2 test slice:

- has fewer than 50 positives or 30 controls;
- loses more than 0.005 AUC or PR-AUC;
- loses more than 0.02 threshold-40 recall;
- increases threshold-40 FPR by more than 0.02;
- reduces high-band precision.

These are minimum guardrails, not a replacement for human review. Do not tune
on the test slice; use v1 and the v2 train slice for exploration, then treat the
test slice as a holdout.

## Candidate label intake

Create a review queue of packages you want to check against OSV:

```bash
mkdir -p data/feedback
cat > data/feedback/packages.jsonl <<'JSONL'
{"system":"npm","name":"example","version":"1.2.3","cutoff":"2025-01-01T00:00:00Z"}
JSONL

python scripts/intake_osv_labels.py \
  --input data/feedback/packages.jsonl \
  --out data/feedback/osv-labels.jsonl
```

The script writes candidate `MAL-*` labels with advisory ID, aliases and URL,
marked `status: candidate` and `reviewed: false`. It does **not** modify
`validation/v1`; a human must review and promote labels into the validation
dataset.

## Manual promotion

Promotion is intentionally a review step, not an automatic merge.

1. Inspect candidates:

```bash
jq -c 'select(.reviewed == false)' data/feedback/osv-labels.jsonl
```

2. Mark only verified candidates as approved. Use `reviewed: true` and
`status: "approved"`. Do not promote a record when the cutoff is after the
malicious release/disclosure or the advisory is ambiguous.

3. Add one `incidents.jsonl` row and one `incident_packages.jsonl` row to the
validation dataset. The minimum fields are in `validation/README.md`. Keep
`observation_cutoff` before the malicious release, use a unique `incident_id`,
and preserve the OSV URL in `source_urls`. Use `cutoff_basis: manual_review`
unless the incident has a stronger documented basis.

4. Keep the manifest consistent:

```python
import hashlib
import json
from pathlib import Path

base = Path("validation/v1")
manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
for name in ("incidents.jsonl", "incident_packages.jsonl", "controls.jsonl"):
    manifest["files"][name] = hashlib.sha256(
        (base / name).read_bytes()
    ).hexdigest()
manifest["counts"] = {
    "incidents": sum(1 for _ in (base / "incidents.jsonl").open(encoding="utf-8")),
    "incident_packages": sum(
        1 for _ in (base / "incident_packages.jsonl").open(encoding="utf-8")
    ),
    "controls": sum(1 for _ in (base / "controls.jsonl").open(encoding="utf-8")),
}
(base / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
```

Then verify:

```bash
python scripts/check_validation_dataset.py
```

5. Ingest and score the new package in the validation database, then recalibrate:

```bash
printf '%s\n' PACKAGE > /tmp/validation-seed.txt
mw ingest --system npm --seed-file /tmp/validation-seed.txt \
  --config config/validation.yaml --no-github
mw score-all --config config/validation.yaml
mw evaluate-validation --config config/validation.yaml
mw calibrate --candidate config/calibration-candidate.yaml
```

If the package has been removed from the registry, do **not** put it in the v1
current-state cohort: use `validation/historical/` instead. Historical labels
remain available for version-aware/replay work but do not change current-state
AUC/PR-AUC. Do not force-add a control that overlaps the new positive package.

For a temporary check without touching the tracked dataset, copy
`validation/v1` to a local directory and use
`mw evaluate-validation --dataset validation/local`; commit only after review.

## First cycle result (2026-11-15)

Reviewed 30 OSV `MAL-*` candidates. Their affected versions had been removed
from the registry, so they were moved to `validation/historical/` rather than
kept in the v1 current-state cohort. v1 was restored to its prior baseline
(AUC 0.862, PR-AUC 0.838) before the later `signing_gap` calibration; the 0.5.3
model then reached v1 AUC 0.875 and v2 AUC 0.891. This was a label-scope
correction, not a model regression.

## Rejected high-confidence candidates

- **Static content scan**: tested on 378 v1 packages. Positives had 4 `wallet`
  and 1 `install_hook` flag, while controls had 42 `install_hook`, 21 `wallet`
  and 3 `network_exec` flags. It is too noisy for high-confidence and remains
  context-only.
- **Current-version OSV advisory**: already implemented as `osv_risk`; v2 has
  0 current-version matches because most malicious versions were removed.
  Historical advisory matching belongs in replay, not current-state high band.

## Weekly loop

1. Add new labels from OSV MAL/advisories, documented incidents and
   false-positive reports to the validation datasets.
2. Keep the temporal holdout frozen.
3. Run `mw calibrate` plus the incident replay (`python
   scripts/incident_check.py`).
4. Review deltas and failure cases; run `mw evaluate-ablations` for signal
   attribution.
5. Bump `model_version` only after the candidate passes; record the decision in
   the model changelog and keep the previous version in the scores table.

The loop remains human-in-the-loop: OSV intake produces candidates, and labels
are promoted only after review. The append-only history and drift report are
implemented; scheduled execution remains deployment-specific.
