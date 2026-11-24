#!/usr/bin/env python3
"""Build a small SQLite demo database from the local MaintainerWatch DB."""

from __future__ import annotations

import argparse
import json

from mw.config import load_config
from mw.demo_db import DEFAULT_QUOTAS, build_demo_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=None)
    parser.add_argument("--out", default="data/demo/maintainerwatch-demo.sqlite")
    parser.add_argument("--config", default=None)
    parser.add_argument("--npm", type=int, default=DEFAULT_QUOTAS["npm"])
    parser.add_argument("--pypi", type=int, default=DEFAULT_QUOTAS["pypi"])
    parser.add_argument("--crates", type=int, default=DEFAULT_QUOTAS["crates"])
    parser.add_argument("--maven", type=int, default=DEFAULT_QUOTAS["maven"])
    parser.add_argument("--github", type=int, default=DEFAULT_QUOTAS["github"])
    parser.add_argument("--no-high", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    source = args.source or cfg.db_path
    quotas = {
        "npm": args.npm, "pypi": args.pypi, "crates": args.crates,
        "maven": args.maven, "github": args.github,
    }
    print(json.dumps(build_demo_db(cfg, source, args.out, quotas, not args.no_high)))


if __name__ == "__main__":
    main()
