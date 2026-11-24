# Soft launch plan

Goal: get real users and design partners without overclaiming or triggering a
premature HN/Reddit backlash.

## Launch gate

- [x] High-band review documented; no package labelled malicious without advisory.
- [x] Public lookup, CI action and first-10-minutes path tested.
- [x] Demo SQLite published and API-smoked.
- [x] Waivers, weekly diff and static team report available.
- [x] Privacy, methodology, limitations and dual-use boundaries documented.
- [x] Public snapshot/index refreshed.
- [ ] Five user interviews completed.
- [ ] At least three design partners identified.
- [ ] FAQ/objection-handling page published.
- [ ] Monitoring capacity for the first 48 hours confirmed.

## Channels

Start small, in this order:

1. personal network and design partners;
2. one or two targeted communities (`r/opensource`, `r/devops`, or relevant
   ecosystem communities) after checking self-promotion rules;
3. technical write-up with methodology and limitations;
4. HN `Show HN` only after feedback and at least a few repeat users.

Do not lead with “AI”, “malware detector” or a ranked list of risky packages.

## Suggested HN framing

> Show HN: MaintainerWatch – open dataset and CLI for maintainer-level
> supply-chain risk

Body should state:

- static, metadata-driven research preview;
- no code execution in the analyst process;
- explainable signals and confidence;
- public dataset/index and CI action;
- known limitations and how to report false positives;
- request for design partners and feedback, not sales.

## Objection handling

- “This is just another score.” → show evidence, confidence, coverage, provider
  context and waivers.
- “Why should I trust it?” → reproducible dataset, methodology, high-band
  review, no automatic accusations.
- “It will be noisy.” → waiver flow, feedback loop, advisory default in CI.
- “Why not full registry coverage?” → sampled research preview; data and
  limitations are explicit.
- “Is this a target list?” → no; no ranked targets, no maintainer dossiers.

## Stop conditions

Pause promotion if:

- high-band review finds an unresolved accusation;
- false-positive reports exceed the team’s triage capacity;
- CI action blocks legitimate PRs unexpectedly;
- public data/index is stale or inconsistent.

## Success signals

- 10 teams run a real scan or CI check in 90 days;
- 3 design partners;
- 2 repeat weekly users;
- 5 completed user interviews;
- false-positive reports handled within one release.
