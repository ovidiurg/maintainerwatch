#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%d)}"
TAG="${TAG:-dataset-${STAMP}}"
JSON="data/maintainerwatch-${STAMP}.json"
CHECKSUM="${JSON}.sha256"

if [ ! -f "$JSON" ]; then
  "${PYTHON:-python3}" -m mw.cli export --format json
fi
sha256sum "$JSON" > "$CHECKSUM"

if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$JSON" "$CHECKSUM" --clobber
else
  gh release create "$TAG" "$JSON" "$CHECKSUM" \
    --title "MaintainerWatch dataset ${STAMP}" \
    --notes "JSON dataset with scored packages and normalized provider_context. No raw package archives. Checksum included."
fi
echo "published ${TAG}"
