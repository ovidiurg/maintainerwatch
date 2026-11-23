# CI waivers

A waiver is an explicit, expiring exception for a finding that a team has
reviewed and accepted temporarily. A waiver does not hide the result from the
data; it only changes whether `scan-diff` treats it as active.

Start from `.maintainerwatch/waivers.example.yml`:

```yaml
waivers:
  - system: npm
    name: example-package
    reason: "Maintainer handover reviewed; migration tracked in SEC-123"
    expires_at: 2026-12-31
    owner: security-team
    ticket: SEC-123
```

Required fields:

- `system` and `name`
- `reason`
- `expires_at` (`YYYY-MM-DD` or ISO datetime)

Optional matching:

- `band` — only waive a specific band;
- `signal` — only waive when that signal is in the compact index top signals.

## Behaviour

- `scan-diff --waivers .maintainerwatch/waivers.yml` marks matching findings as
  waived.
- Waived findings remain in JSON/SARIF with `properties.waived: true` and the
  reason/expiry.
- SARIF level becomes `note` for waived findings.
- `--fail-on` ignores waived findings.
- The GitHub Action reads `.maintainerwatch/waivers.yml` automatically when it
  exists and shows the waived count in the sticky PR comment.
- Expired waivers are ignored and the finding becomes active again.

Do not use a waiver as a permanent allowlist. Review expiries and remove or
renew them with fresh evidence.
