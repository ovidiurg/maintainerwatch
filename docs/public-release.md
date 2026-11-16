# Public release checklist

## Repository

- [ ] Confirm the intended visibility change with the maintainer.
- [ ] `git status` is clean and the release commit is pushed.
- [ ] Secret scan is clean (`detect-secrets`).
- [ ] No root `data/`, caches, reports, tokens, private docs or local databases
      are tracked.
- [ ] Local private notes and grant/roadmap drafts remain ignored.
- [ ] License and attribution files are present.

## CI and packaging

- [ ] Python 3.11–3.13 CI is green.
- [ ] Docker smoke passes locally and on a relevant PR.
- [ ] Wheel contains `mw/data/default.yaml`.
- [ ] `mw --help`, `mw scan-diff --help` and affected API endpoints work.
- [ ] Version and `model_version` are consistent across configs.
- [ ] Action install path is tested (`package-spec` empty installs the action
      checkout; package is not yet published on PyPI).

## Validation and model

- [ ] v1/v2 evaluation reports are regenerated.
- [ ] Incident replay is regenerated.
- [ ] Calibration history/drift are committed.
- [ ] No candidate weight is applied without the holdout guardrails.

## PR/CI integration

- [ ] Compact index builds and checksum verifies.
- [ ] SARIF is generated on a local git fixture.
- [ ] GitHub Action is tested on a real PR after the repository becomes public.
- [ ] Release asset `maintainerwatch-index.json` is published and checksummed
      (`DRY_RUN=1 make ci-publish-index`, then `make ci-publish-index`).
- [ ] Comment remains **disabled by default**.

## Site and contact

- [ ] GitHub Pages workflow can access the repository after visibility change.
- [ ] Site links to SECURITY, CONTRIBUTING, API, methodology and privacy docs.
- [ ] Private security advisory channel is available; no general email is
      published.
- [ ] Dual-use and GDPR notices are visible.
