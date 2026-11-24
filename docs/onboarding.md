# Onboarding — first 10 minutes

The goal is time to the first useful answer, not time to run the full pipeline.
The public path must work without an account, API key or local ingest.

Start here: <https://ovidiurg.github.io/maintainerwatch/start.html>

## Paths

| Path | Time | What the user gets |
|---|---:|---|
| Lookup | 0–2 min | Score, band, confidence, coverage, top signals |
| GitHub Action | 3–6 min | PR comment and SARIF for changed manifests |
| Local CLI / Docker | 6–10 min | Full evidence, history and API; `mw lookup` works from the public index |

The full local pipeline remains an advanced setup path. Do not make it the
first step for a new user.

## Success criteria

- First useful lookup: under 2 minutes.
- First PR comment: under 10 minutes.
- The result explains uncertainty and links to methodology/limitations.
- A user can stop after lookup or CI without feeling that setup is incomplete.

## Feedback without default telemetry

We do not add default analytics. Feedback is opt-in through the repository issue
form:

<https://github.com/ovidiurg/maintainerwatch/issues/new?template=feedback.yml>

How to interpret results: [`interpretation.md`](interpretation.md).

Useful aggregate signals are:

- issue-form volume by path (lookup, CI, CLI, API);
- reports of time-to-first-result;
- false-positive/noisy-result reports;
- design-partner interviews and repeat usage;
- public CI/action adoption visible to users or shared with consent.

Do not collect personal contact data or private package names in the public
issue tracker.

### Opt-in metrics command

```bash
make onboarding-metrics
# or:
PYTHONPATH=. .venv/bin/python scripts/onboarding_metrics.py --format json
```

It reports feedback issue counts, open/closed state, label distribution,
self-reported steps, and median time to close. The issue form asks which steps
the reporter completed; this is opt-in self-report, not automatic analytics.
It does not measure unique visitors or hidden behavior.

## Demo database

For full evidence without a full ingest, download the compressed demo SQLite:

```bash
mkdir -p data/demo
curl -fsSL https://github.com/ovidiurg/maintainerwatch/releases/latest/download/maintainerwatch-demo.sqlite.zst \
  -o data/demo/maintainerwatch-demo.sqlite.zst
zstd -d -f data/demo/maintainerwatch-demo.sqlite.zst -o data/demo/maintainerwatch-demo.sqlite
mw scan lodash --system npm --config config/demo.yaml
```

The demo contains a cross-ecosystem sample, all high-band packages and full
signals/provider context for those packages.

## Validation log

Checked on 23 November 2026:

- clean venv: `pip install /home/ovidiu/code/research`, `mw --help`, and
  `mw lookup lodash --system npm` from the public index;
- Playwright Chromium: live lookup returned the lodash result, desktop nav
  stayed on one line, and the mobile start page had no horizontal overflow;
- local git fixture: `scan-diff` fails on an unwaived high finding and passes
  when a valid waiver is present.

## Definition of done for onboarding changes

- The lookup and CI paths are exercised from a clean browser/checkout.
- The action template is copy-paste runnable.
- The page states that high/medium/low are triage aids and not malware labels.
- README and the Pages start page link to each other.
