#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="$("${PYTHON:-python3}" - <<'PY'
from mw.config import load_config
print(load_config().model_version)
PY
)"
DATE="$(date -u +%Y%m%d)"
TAG="${TAG:-ci-index-${DATE}}"
VERSIONED="maintainerwatch-index-${MODEL}-${DATE}.json"
LATEST="maintainerwatch-index.json"

mkdir -p dist
"${PYTHON:-python3}" scripts/build_ci_index.py --out "dist/${VERSIONED}"
cp "dist/${VERSIONED}" "dist/${LATEST}"
(cd dist && sha256sum "${VERSIONED}" > "${VERSIONED}.sha256")
(cd dist && sha256sum "${LATEST}" > "${LATEST}.sha256")

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "dry-run: would publish ${TAG}: ${VERSIONED}, ${LATEST} and checksums"
  exit 0
fi

if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" \
    "dist/${VERSIONED}" "dist/${VERSIONED}.sha256" \
    "dist/${LATEST}" "dist/${LATEST}.sha256" --clobber
else
  gh release create "$TAG" \
    "dist/${VERSIONED}" "dist/${VERSIONED}.sha256" \
    "dist/${LATEST}" "dist/${LATEST}.sha256" \
    --title "MaintainerWatch CI index ${DATE}" \
    --notes "Compact risk index for model ${MODEL}, generated locally from the MaintainerWatch database." \
    --latest
fi

echo "published ${TAG}"
