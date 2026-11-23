# Alert examples

Alerts are optional. Start with `--dry-run` and a small threshold, then integrate
one channel at a time.

## Slack-compatible webhook

Set `alerts.webhook_format: slack` in a local config, then run:

```bash
mw alerts \
  --config config/local.yaml \
  --rules \
  --webhook "$SLACK_WEBHOOK" \
  --dry-run
```

Remove `--dry-run` after checking the matched packages. Keep the webhook URL in
the environment, not in git.

## Email

SMTP settings live under `alerts.smtp`; the password is read from
`alerts.smtp.password_env` (default `SMTP_PASSWORD`).

```bash
export SMTP_PASSWORD='...'
mw alerts \
  --config config/local.yaml \
  --rules \
  --email security@example.com \
  --dry-run
```

## One-off checks

```bash
mw alerts --min-score 40 --dry-run
mw alerts --min-score 40 --signal publisher_change --min-signal 0.5 --dry-run
```

Alert rules live under `alerts.rules` in the config. Use `mw alerts --help` for
the authoritative options. Do not send alerts about unconfirmed packages as
malware claims.
