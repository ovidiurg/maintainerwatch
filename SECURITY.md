# Security policy

## Supported versions

Security fixes are applied to the current 0.4.x research-preview line. Older
model or app versions are kept for reproducibility but are not actively patched.

## Reporting a vulnerability

Do **not** open a public issue for a security vulnerability. Use the private
GitHub security advisory channel:

https://github.com/ovidiurg/maintainerwatch/security/advisories/new

Please include:

- affected command, endpoint or artifact;
- app/model version;
- a minimal reproduction using public metadata;
- impact and any suggested mitigation.

Do not include credentials, private data, malware samples or personal data in
the report.

## Scope and safety

MaintainerWatch is a read-only metadata and static-analysis tool. It must never
execute untrusted package code in the analyst or API process. Dynamic analysis
is delegated to a separately configured, isolated worker.

A high score is a review indicator, not proof of compromise. Do not use the
project for automated accusations, harassment or offensive targeting.

## Response

Reports are acknowledged on a best-effort basis. Confirmed issues are fixed in
a versioned release and documented without publishing exploitable details or
personal data.
