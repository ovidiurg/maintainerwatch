#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-maintainerwatch:ci}"
CONTAINER="${CONTAINER:-mw-docker-smoke}"
PORT="${PORT:-18080}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$ROOT"
docker build -t "$IMAGE" .

# CLI and packaged-config/report smoke.
docker run --rm "$IMAGE" mw --help >/dev/null
docker run --rm "$IMAGE" sh -c '
  mw init --config /app/config/default.yaml >/dev/null
  mw report --out /app/data/report.html
  test -s /app/data/report.html
'

# Compose configuration must render.
docker compose config >/dev/null

# API startup and endpoints.
cleanup
rm -f /tmp/mw-docker-health.json
docker run -d --rm --name "$CONTAINER" -p "${PORT}:8000" "$IMAGE" >/dev/null
ready=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/mw-docker-health.json 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  docker logs "$CONTAINER" || true
  echo "API did not become ready" >&2
  exit 1
fi
cat /tmp/mw-docker-health.json
echo
curl -fsS "http://127.0.0.1:${PORT}/packages?limit=1" >/dev/null
