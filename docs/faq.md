# FAQ

## Is MaintainerWatch a malware detector?

No. It is a research-preview triage aid. High/medium/low bands are review
signals, not malware labels.

## What does it analyse?

Public registry/forge metadata, maintainer history, OSV, deps.dev, OpenSSF
Scorecard and bounded package archives. It does not execute package code in the
analyst process.

## Mai este relevant „bus factor” când codul este scris cu agenți AI?

Da, dar bus factor-ul util nu mai este „câți oameni scriu cod”, ci „câți
oameni pot controla și răspunde pentru un release”.

Agenții AI pot reduce concentrarea cunoașterii asupra codului, dar nu rezolvă
ownership-ul real: conturi de registry, chei de semnare, acces CI/CD, secrets,
capacitatea de a publica advisory-uri și relația cu comunitatea. Un singur om
poate genera un volum mare de commit-uri prin agenți și poate avea în continuare
întregul control asupra release-urilor.

În MaintainerWatch, `bus_factor` este calculat din concentrarea commit-urilor și
rămâne un indiciu, nu un verdict. Cu agenți AI, volumul de commit-uri poate
reflecta un singur operator, deci semnalul poate deveni zgomotos. Interpretați-l
împreună cu `publisher_change`, `maintainer_continuity`, semnare/provenance,
Scorecard și istoricul release-urilor.

Următorul pas este un semnal separat pentru **release-authority concentration**:
cine poate publica, semna, aproba advisory-uri și accesa CI/CD.

## Why are some signals high without an advisory?

Publisher/continuity, commit or dependency evidence can raise a package to high.
Those cases are reviewed manually and remain warnings, not accusations. See
[high-band review](validation/high-band-review.md).

## How do I handle a false positive?

Use the feedback form; for CI, add an expiring waiver with reason and ticket.
See [feedback](feedback.md) and [waivers](waivers.md).

## Is the dataset live?

No. It is a dated snapshot with a public changelog and compact index. Check
[changelog](changelog.md) and [dataset releases](dataset-releases.md).

## Does it store personal data?

Only public, role-related data. No social-media scraping, breach data or email
registration checks. See [privacy](gdpr.md).

## Can I use it in CI?

Yes. The GitHub Action runs advisory by default and checks changed dependency
manifests against the compact index. See [PR/CI](pr-ci.md).

## Is it production-ready?

No. It is a research preview without an SLA. See the limitations in
[methodology](methodology.md).
