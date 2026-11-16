# Public release checklist

## Repository

- [x] Confirm the intended visibility change with the maintainer.
- [x] `git status` is clean and the release commit is pushed.
- [x] Secret scan is clean (`detect-secrets`).
- [x] No root `data/`, caches, reports, tokens, private docs or local databases
      are tracked.
- [x] Local private notes and grant/roadmap drafts remain ignored.
- [x] License and attribution files are present.

## CI and packaging

- [x] Python 3.11–3.13 CI is green.
- [x] Docker smoke passes locally and on a relevant PR.
- [x] Wheel contains `mw/data/default.yaml`.
- [x] `mw --help`, `mw scan-diff --help` and affected API endpoints work.
- [x] Version and `model_version` are consistent across configs.
- [x] Action install path is tested (`package-spec` empty installs the action
      checkout; package is not yet published on PyPI).

## Validation and model

- [x] v1/v2 evaluation reports are regenerated.
- [x] Incident replay is regenerated.
- [x] Calibration history/drift are committed.
- [x] No candidate weight is applied without the holdout guardrails.

## PR/CI integration

- [x] Compact index builds and checksum verifies.
- [x] SARIF is generated on a local git fixture.
- [x] GitHub Action tested on a real private PR with a local index; SARIF
      upload was disabled.
- [x] GitHub Action tested with the public Release index after visibility change.
- [x] Release asset `maintainerwatch-index.json` is published and checksummed
      (`DRY_RUN=1 make ci-publish-index`, then `make ci-publish-index`).
- [x] Comment is **disabled by default**; one sticky comment was manually
      verified with `comment: true`.
- [x] Site links the latest public CI index asset.
- [ ] GitHub Action tested on a PR from a fork (no write token) after visibility
      change.

## Site and contact

- [x] GitHub Pages workflow can access the repository after visibility change.
- [x] Site links to SECURITY, CONTRIBUTING, API, methodology and privacy docs.
- [x] Private security advisory channel is available; no general email is
      published.
- [x] Dual-use and GDPR notices are visible.
