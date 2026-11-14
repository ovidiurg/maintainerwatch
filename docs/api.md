# API

The read-only API is served by FastAPI:

```bash
mw serve --host 127.0.0.1 --port 8000
```

- Interactive docs: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status, app version and model version. |
| GET | `/systems` | Package counts per ecosystem. |
| GET | `/packages` | Paginated scored packages (`system`, `band`, `min_score`, `limit`, `offset`). |
| GET | `/packages/{system}/{name}` | Score, signal evidence, context and dependencies for one package. |
| GET | `/top` | First page of the highest-risk packages (`system`, `limit`, `offset`). |
| GET | `/alerts` | Ad-hoc alert query (`min_score`, `signal`, `min_signal`, `limit`; limit ≤ 500). |
| GET | `/alert-rules` | Runs the alert rules from `config/default.yaml` without delivering them. |

## Response shapes

`/packages` items contain `system`, `name`, `score`, `band`, `downloads_weekly`,
`osv_count`, `fan_in`, `fan_in_transitive`, `dependencies_count`, `repo_url`
and `license`.

`/packages/{system}/{name}` returns the score, `inputs_hash`, `computed_at`,
`evidence_coverage`, `risk_type`, `risk_note`, `next_step`, the `context` block
and every signal with its `value` and `evidence` (including `install_script`
scripts for npm). The risk fields are populated for medium/high scores and are
empty for low scores. Run `mw score-all` before querying.

## Pagination

`/packages` and `/top` accept `limit` (1–500) and `offset` (0-based).
`/packages` additionally accepts `system`, `band` and `min_score`; `/top` only
accepts `system`, `limit` and `offset`. The response body is a JSON array;
pagination metadata is returned in headers:

```
X-Total-Count: 1713
X-Limit: 50
X-Offset: 0
X-Next-Offset: 50
```

`X-Next-Offset` is empty on the last page.

```bash
curl 'http://127.0.0.1:8000/packages?system=npm&band=high&limit=20&offset=0'
```

## Authentication

Set an API key to require it on every endpoint except `/health`, `/docs`,
`/openapi.json` and `/redoc`:

```bash
export MAINTAINERWATCH_API_KEY=secret
mw serve
curl -H 'X-API-Key: secret' 'http://127.0.0.1:8000/packages?limit=5'
```

The environment variable name is configurable via `api.api_key_env`. Without
the env var, the API is open.

## Rate limiting

A simple in-memory per-client (or per-key) limit is available:

```yaml
api:
  api_key_env: MAINTAINERWATCH_API_KEY
  rate_limit_rpm: 60   # 0 disables it
```

Exceeding the limit returns `429` with `Retry-After: 60`. The bucket resets on
process restart; use a reverse proxy for production-grade limits.

## Alert rules

`config/default.yaml` defines rules that the CLI and `/alert-rules` evaluate:

```yaml
alerts:
  rules:
    - name: high-risk
      min_score: 45
      min_signal: 0.5
      limit: 100
    - name: publisher-change
      min_score: 30
      signal: publisher_change
      min_signal: 0.5
      limit: 100
  webhook: null
  webhook_format: generic   # generic | slack | discord
  email: null
  smtp:
    host: null
    port: 587
    username: null
    password_env: SMTP_PASSWORD
    sender: null
    use_tls: true
```

Run them without delivery:

```bash
mw alerts --rules --dry-run
```

Run them and write the full results:

```bash
mw alerts --rules --out data/alerts.json
```

Deliver matches to a webhook or email:

```bash
export ALERT_WEBHOOK=https://example.org/hook
mw alerts --rules --webhook "$ALERT_WEBHOOK"
mw alerts --rules --email security@example.org
```

Webhook payloads are generic JSON by default; `slack` and `discord` formats are
available. Email requires the `smtp` block and `SMTP_PASSWORD` in the
environment. Delivery is best-effort and reported per rule.

## Security and responsible use

The API is read-only, but it exposes ranked risk scores, signal evidence and
maintainer identifiers. Bind it to localhost by default. For a public
deployment, require `MAINTAINERWATCH_API_KEY`, enable rate limiting, terminate
TLS at a reverse proxy and minimise access logs.

Do not expose the raw SQLite database or turn the API into a public “target
list”. Share aggregate findings only, with identities minimised. A high score
is a request for review, not proof of compromise.

## Notes

- The API reads the same SQLite database as the CLI; run `mw score-all` first.
- Scores are filtered by the configured `model_version` from `config/default.yaml`.
- It is read-only: there are no write endpoints.
- `install_script`, `evidence_coverage` and the other model additions are
  returned automatically; no endpoint change is needed.
- The OpenAPI schema includes parameter descriptions and examples; `/docs`
  renders it interactively.
