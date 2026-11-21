#!/usr/bin/env python3
"""Fill OSV affected ranges/summaries from local npm/PyPI OSV archives."""

from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from pathlib import Path

from mw.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npm-zip", default="/tmp/opencode/osv2/npm-all.zip")
    parser.add_argument("--pypi-zip", default="/tmp/opencode/osv2/pypi-all.zip")
    args = parser.parse_args()
    cfg = load_config()
    conn = sqlite3.connect(cfg.db_path)
    details = {}
    for path in (Path(args.npm_zip), Path(args.pypi_zip)):
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith(".json"):
                    continue
                try:
                    record = json.loads(archive.read(name))
                except (KeyError, json.JSONDecodeError):
                    continue
                vuln_id = record.get("id")
                affected = record.get("affected")
                if vuln_id and isinstance(affected, list):
                    details[vuln_id] = (
                        json.dumps(affected, sort_keys=True),
                        record.get("summary"),
                        record.get("modified"),
                    )
    rows = []
    for vuln_id, (affected, summary, modified) in details.items():
        rows.append((affected, summary, modified, vuln_id))
    conn.executemany(
        """UPDATE osv SET affected_json=?, summary=COALESCE(?, summary),
                         modified_at=COALESCE(?, modified_at)
           WHERE vuln_id=?""",
        rows,
    )
    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM osv WHERE affected_json IS NULL").fetchone()[0]
    conn.close()
    print(json.dumps({
        "archives": [args.npm_zip, args.pypi_zip],
        "records": len(rows),
        "remaining_without_affected": remaining,
    }, indent=2))


if __name__ == "__main__":
    main()
