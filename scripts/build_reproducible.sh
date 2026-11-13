#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  DEFAULT_PYTHON="$ROOT/.venv/bin/python"
else
  DEFAULT_PYTHON="python3"
fi
PYTHON="${PYTHON:-$DEFAULT_PYTHON}"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"

normalize_sdist() {
  "$PYTHON" - "$1" "$SOURCE_DATE_EPOCH" <<'PY'
import gzip
import io
import sys
import tarfile

src, epoch = sys.argv[1], int(sys.argv[2])
with tarfile.open(src, "r:gz") as tar:
    members = sorted(tar.getmembers(), key=lambda m: m.name)
    entries = []
    for member in members:
        stream = tar.extractfile(member) if member.isfile() else None
        entries.append((member, stream.read() if stream else None))

buffer = io.BytesIO()
with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as out:
        for member, content in entries:
            member.mtime = epoch
            member.pax_headers = {}
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.mode = 0o755 if member.isdir() else 0o644
            if content is not None:
                member.size = len(content)
                out.addfile(member, io.BytesIO(content))
            else:
                out.addfile(member)
with open(src, "wb") as fh:
    fh.write(buffer.getvalue())
PY
}

build_once() {
  outdir="$1"
  "$PYTHON" -m build --outdir "$outdir" >/dev/null
  for sdist in "$outdir"/*.tar.gz; do
    [ -e "$sdist" ] || continue
    normalize_sdist "$sdist"
  done
}

A="$(mktemp -d)"
B="$(mktemp -d)"
trap 'rm -rf "$A" "$B" "$A.sha" "$B.sha"' EXIT

build_once "$A"
build_once "$B"

(cd "$A" && sha256sum ./* | sort) > "$A.sha"
(cd "$B" && sha256sum ./* | sort) > "$B.sha"

if diff -u "$A.sha" "$B.sha"; then
  echo "reproducible: both builds have identical hashes"
else
  echo "not reproducible: build hashes differ" >&2
  exit 1
fi
