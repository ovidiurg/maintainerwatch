# Research notes — signal ideas

Sources reviewed on 2026-11-23. These are candidate ideas, not applied weights.

## Directly useful

- **What are Weak Links in the npm Supply Chain?** — arXiv `2112.10165`.
  Install scripts, expired maintainer domains, inactive packages/maintainers and
  overloaded maintainers. Three signals were supported by practitioners:
  expired domain, install scripts, unmaintained packages.
- **Malicious Package Detection using Metadata Information (MeMPtec)** —
  arXiv `2402.07444`. Separates easy-to-manipulate (ETM) from
  difficult-to-manipulate (DTM) metadata. DTM features are temporal or
  restricted-control: package age, maintainer service time, forks, issues,
  stars.
- **From Commits to Confidence** — arXiv `2508.02487`. Unstable repositories
  strongly correlate with top-3 contributor concentration (odds ratio 24.57 in
  the paper's sample). Supports longitudinal bus-factor/concentration signals.
- **XZ Utils analysis and socio-technical threat detection** — arXiv
  `2504.17473` and `2510.21452`. XZ was visible through combined social and
  technical changes: contributor influence, commit patterns, escalation of
  control, communication pressure.
- **ConfuGuard** — arXiv `2502.20528`. Metadata rules reduce typosquat FPR from
  80% to 28%: active development, comprehensive metadata, overlapping
  maintainers, fork detection, distinct purpose.
- **Modeling Interconnected Social and Technical Risks** — arXiv `2205.04268`.
  Maintainer identity and dependency networks should be modeled together; the
  same maintainer can be a systemic failure point across several packages.
- **Forecasting the Maintained Score** — arXiv `2601.18344`. OpenSSF
  `Maintained` is retrospective; trend/bucket forecasts are feasible with simple
  models.

## Detection pipelines

- **Amalfi** — arXiv `2202.13953`: classifiers + source reproducibility +
  clone detection.
- **DONAPI** — arXiv `2403.08334`: behavior sequence knowledge mapping.
- **OSCAR** — arXiv `2409.09356`: sandbox + fuzz + behavior hooks; F1 0.95 npm,
  0.91 PyPI; strong FPR reduction.
- **Cerebro** — arXiv `2309.02637`: one malicious behavior sequence model for
  npm and PyPI.
- **SocketAI** — arXiv `2403.12196`: static pre-screening + LLM review;
  precision 0.99 in benchmark.
- **How Effective Are NPM Malicious Package Detectors?** — arXiv `2603.27549`:
  large benchmark; combination effectiveness equals complementarity minus new
  false positives.

## Applied now

- Signal robustness classification: DTM/ETM.
- Typosquat benignity rules (available subset).
- Maintainer systemic exposure context.
- Scorecard trend history.

## Not applied

- Dynamic/LLM detection: keep behind the existing isolated worker boundary.
- Domain expiry scoring: see below.

## Expired maintainer domain verdict

Not consistent enough for scoring:

- ICANN says RDAP replaced WHOIS for gTLDs as of 2025-01-28, except `.com`,
  `.name`, `.post`; ccTLD RDAP adoption is around 9%.
- WHOIS/RDAP comparison over 164M records found 7.6% inconsistency in important
  fields and 4.4% expiration-date inconsistency.
- Registry expiry and registrar expiry can legitimately differ.
- Maintainer identities in npm are often public mailbox domains (`gmail.com`),
  role aliases, malformed multi-maintainer strings or `noreply` addresses.

A safe future implementation could mark `domain_status: unknown|rdap_expired|
rdap_ok|public_provider|unparseable` for clean single-email custom domains, with
a long TTL cache. It should stay context-only, never a scored signal.
