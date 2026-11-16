#!/usr/bin/env python3
"""Build the compact JSON risk index used by PR/CI integrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mw import db
from mw.ci_index import write_index
from mw.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--out", default="dist/maintainerwatch-index.json")
    parser.add_argument("--no-checksum", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    path, count = write_index(conn, cfg, args.out, checksum=not args.no_checksum)
    conn.close()
    print(json.dumps({"path": str(path), "records": count, "model_version": cfg.model_version}))


if __name__ == "__main__":
    main()
