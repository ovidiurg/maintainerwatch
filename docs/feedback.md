# Feedback intake

Public feedback arrives through the opt-in issue form:

<https://github.com/ovidiurg/maintainerwatch/issues/new?template=feedback.yml>

There is no default product telemetry. Issue-form submissions, design-partner
interviews and public CI usage are the feedback signals.

## Automatic intake

The `Feedback intake` workflow runs when an issue title starts with
`[feedback]`. It:

- applies `feedback` and `needs-triage`;
- adds `false-positive` when the report mentions noise or a false positive;
- adds `ci` for GitHub Action / pull-request reports;
- adds `onboarding` for lookup, first-run or documentation friction;
- posts one acknowledgment with this process link;
- does not close, assign, or promise a fix automatically.

## Triage flow

1. **Classify** the report: onboarding, docs, CI, false positive, bug, or feature.
2. **Reproduce** against the public lookup, latest index, or local snapshot.
   Never ask for private package names or credentials.
3. **Check evidence**: provider context, current version, affected ranges,
   maintainer history and signal applicability.
4. **Decide**:
   - onboarding/docs: improve the first-10-minutes path;
   - CI: adjust action defaults, comments or SARIF;
   - false positive: add a regression test or a documented limitation/waiver;
   - confirmed issue: open/link a focused fix issue.
5. **Close the loop** with the reporter and link the fix or limitation.
6. **Review weekly** for repeated themes and convert them into roadmap items.

## Response boundaries

- No automatic accusation about a maintainer or package.
- No pay-to-remove, no ranked target list, no early vulnerability access.
- Do not publish private reports or personal data.
- High/medium/low are triage aids, not malware labels.

## Labels

- `feedback` — opt-in report
- `needs-triage` — not yet classified
- `false-positive` — noisy or incorrect ranking report
- `onboarding` — first-run, lookup, or docs friction
- `ci` — GitHub Action, pull-request or `scan-diff` feedback

## Metrics

Track issue volume by label, time to first response, time to resolution,
repeated themes and false-positive reports. Use public issue counts and
opt-in/design-partner feedback; do not add hidden analytics.
