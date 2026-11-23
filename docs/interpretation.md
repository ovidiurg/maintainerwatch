# How to read a MaintainerWatch result

MaintainerWatch is a triage aid, not a malware verdict. The output is designed
to help a human decide what to inspect next.

## Score and band

- **low** — below 25; routine monitoring.
- **medium** — 25–49; inspect the evidence before acting.
- **high** — 50+; review promptly, but do not treat the band alone as proof.

A high numerical score can be capped to medium when the evidence is only
hygiene, name similarity or metadata. Use the evidence and provider context,
not the number alone.

## Confidence

- **high** — at least one high-confidence behavioural or advisory signal is
  present.
- **evidence-only** — the result is still explainable, but rests on weaker
  metadata/context signals.

## Evidence coverage

Coverage is the share of the model weight with applicable signals. Low coverage
means fewer inputs were available; it is not automatically a safe result.

## Top signals

The compact lookup shows up to three weighted signals. The full dataset and
`mw scan` expose every signal, its value, evidence and `inputs_hash`.

## High-band review

At the current snapshot, 11 of 17 high-band packages are corroborated by OSV or
deps.dev. Six remain review cases driven by publisher/continuity or repository
evidence:

- `@cloudbase/wx-cloud-client-sdk`
- `pgpass`
- `caniuse-api`
- `@apideck/better-ajv-errors`
- `p-shells`
- `libbz2-rs-sys`

They are precision warnings, not malware labels. See
[high-band review](validation/high-band-review.md).

## Safe action

1. Read the top signals and provider context.
2. Check the current version, affected ranges and maintainer history.
3. Reproduce locally with `mw scan` or the dataset export.
4. Record a false positive through the feedback form instead of assuming the
   package is clean.

See [methodology](methodology.md) and [GDPR/privacy](gdpr.md).
