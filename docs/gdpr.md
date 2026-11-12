# Privacy and data protection

MaintainerWatch processes **public, role-related** data about software
maintainers for the purpose of software supply-chain risk research. This note
describes the safeguards; it is not legal advice.

## Principles

- **Minimisation.** We use only identifiers needed to link a package to the
  person or team that publishes it.
- **Purpose limitation.** Data is used to compute package-level risk signals,
  not to profile individuals or make automated decisions about them.
- **Public sources only.** Registry metadata, public repositories, public
  commit metadata, public GPG keys and opt-in Keybase proofs.
- **No social-media scraping.** We do not enumerate social networks, check
  email registration, or use breach/dark-web data.

## Data we store

| Data | Storage |
|---|---|
| Package and version metadata | plain, public |
| Publisher/maintainer identifiers | plain where already public (registry fields) |
| Email addresses | only as evidence links for identity resolution; hash before any export |
| Repository statistics | aggregated counts and shares |
| Identity links | `id_a`, `id_b`, link type, confidence, evidence URL |

Emails are never included in the exported dataset. Exports contain
package-level aggregates and public evidence URLs.

## Lawful basis

Processing is limited to data manifestly made public by the data subject in a
professional capacity (registry and repository metadata) and to research
purposes. A legitimate-interest assessment and, where required, a DPIA should
be completed before any public deployment.

## Retention and correction

- Raw HTTP responses are cached for a short period (default 24 hours).
- Identity links are recomputed and can be removed on request.
- Any maintainer can request correction or removal of a link by contacting the
  project. A removal request does not change historical public registry data.
- Security-relevant findings follow coordinated disclosure; we do not publish
  unverified accusations about individuals.

## Access and security

- No accounts or personal data are collected from users of the tool.
- The database is local by default.
- If a public instance is deployed, access logs must be minimised and retained
  only as long as necessary.
