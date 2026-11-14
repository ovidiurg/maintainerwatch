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
| Email addresses | public registry/commit fields may be stored in the local database; not exported; hash or minimise before any public deployment |
| Repository statistics | aggregated counts and shares |
| Identity links | `id_a`, `id_b`, link type, confidence, evidence URL |

Emails are not included in the exported dataset. Exports contain package-level
aggregates and public evidence URLs. Raw caches and the SQLite database can
still contain public email fields and must be protected accordingly.

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
- The database is local by default and should be treated as sensitive because
  it contains maintainer identifiers and public email fields.
- If a public instance is deployed, protect the API with an API key, rate
  limits and a TLS reverse proxy; minimise and retain access logs only as long
  as necessary.
- Do not publish the raw database, maintainer dossiers or ranked target lists.
  Share aggregate findings with identities minimised.

## Contact and removal requests

We do not publish a general contact email address, to reduce spam and
unsolicited bulk mail. Use GitHub's private security advisory channel for
privacy, correction or removal requests:
<https://github.com/ovidiurg/maintainerwatch/security/advisories/new>.
Include the ecosystem, package name and, if applicable, the identity link or
field you want reviewed; do not post personal data in a public issue. General
questions can use GitHub Issues.

For a local deployment, remove a package and its versions, maintainers,
signals, scores, snapshots, commits, OSV rows, repository stats, dependencies
and identity links with:

```bash
mw delete-package --system npm --name PACKAGE --yes
```

Run the same command without `--yes` for a dry-run count. Package-level
deletion also removes the package's identity links; inbound dependency edges
from other packages are removed as well. Keep a backup if the removal may need
to be audited. We aim to acknowledge removal requests within 30 days.

## Dual-use

MaintainerWatch is dual-use: the same risk ranking that supports defensive
triage can be repurposed for target selection or social engineering. It does
not contain exploits, credentials, private data or attack tooling. A high score
is a request for review, not proof of compromise, and must not be treated as an
automated accusation against a maintainer. Security-relevant findings should
follow coordinated disclosure.
