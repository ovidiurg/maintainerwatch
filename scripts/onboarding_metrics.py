#!/usr/bin/env python3
"""Summarize opt-in onboarding feedback from public GitHub issues."""

from __future__ import annotations

import argparse
import json
import subprocess

from mw.onboarding_metrics import format_markdown, summarize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    completed = subprocess.run(
        [
            "gh", "issue", "list", "--state", "all", "--limit", str(args.limit),
            "--json", "number,title,labels,createdAt,closedAt,state,body",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    summary = summarize(json.loads(completed.stdout))
    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(format_markdown(summary), end="")


if __name__ == "__main__":
    main()
