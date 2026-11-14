# Dynamic analysis worker

This worker is a thin, isolated boundary between MaintainerWatch and a real
sandbox. It deliberately does **not** execute package code in the worker
process. Set `DYNAMIC_SANDBOX_COMMAND` to an isolated runner (gVisor/runsc,
Kata, or a dedicated Docker worker) that accepts a JSON request on stdin:

```json
{"system":"npm","name":"pkg","version":"1.0.0"}
```

and returns JSON on stdout, for example:

```json
{"risk_score":"high_risk","findings":[{"type":"network","target":"example.org"}]}
```

If no sandbox command is configured, `/scan` returns HTTP 503.

Safety requirements for the runner:

- no host mounts or host network;
- read-only root filesystem and a tmpfs workdir;
- non-root user, dropped capabilities, no-new-privileges;
- CPU/memory/PID limits and a hard timeout;
- network egress disabled or mediated by a logging proxy;
- the worker itself runs in a disposable VM/container, never on an analyst
  workstation.

Configure MaintainerWatch with:

```bash
export MAINTAINERWATCH_DYNAMIC_TOKEN=...
# config/default.yaml
dynamic:
  worker_url: http://worker:8090
  token_env: MAINTAINERWATCH_DYNAMIC_TOKEN
  timeout_s: 600
mw scan-dynamic --limit 20
```

Dynamic results are stored as context (`dynamic_risk_score`,
`dynamic_findings`); they are not model weights until a safe validation set
exists.
