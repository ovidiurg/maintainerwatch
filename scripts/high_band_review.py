#!/usr/bin/env python3
"""Generate a high-band review packet from the current database."""

from __future__ import annotations

import argparse
import json

from mw.config import load_config
from mw.high_band_review import build_packet, write_packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/reviews", help="Output directory.")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    parser.add_argument("--config", default=None, help="Config file path.")
    args = parser.parse_args()
    packet = build_packet(load_config(args.config))
    paths = write_packet(packet, args.out, args.format)
    print(json.dumps({"packages": packet["count"], "paths": [str(path) for path in paths]}))


if __name__ == "__main__":
    main()
