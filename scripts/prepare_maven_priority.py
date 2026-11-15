#!/usr/bin/env python3
"""Write missing popular Maven coordinates from Maven Central search groups."""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from mw.ingest.maven import SEED_MAVEN

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds" / "maven-priority.txt"
TARGET = 400
SEARCH = "https://search.maven.org/solrsearch/select"
GROUPS = [
    "org.springframework.boot", "org.springframework", "org.springframework.security",
    "org.springframework.data", "com.fasterxml.jackson.core",
    "com.fasterxml.jackson.module", "org.apache.commons",
    "org.apache.httpcomponents", "org.apache.httpcomponents.client5", "io.netty",
    "io.projectreactor", "org.junit.jupiter", "org.mockito", "org.assertj",
    "ch.qos.logback", "org.slf4j", "org.apache.logging.log4j",
    "com.google.guava", "com.google.code.gson", "org.jetbrains.kotlin",
]


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "MaintainerWatch/0.5.2"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    names: list[str] = []
    seen: set[str] = set()
    for group in GROUPS:
        url = f"{SEARCH}?q={urllib.parse.quote(f'g:\"{group}\"')}&rows=200&wt=json"
        try:
            docs = ((get_json(url).get("response") or {}).get("docs") or [])
        except OSError:
            continue
        for doc in docs:
            group_name, artifact = doc.get("g"), doc.get("a")
            if not group_name or not artifact:
                continue
            name = f"{group_name}:{artifact}"
            if name not in seen:
                seen.add(name)
                names.append(name)
    for name in SEED_MAVEN:
        if name not in seen:
            seen.add(name)
            names.append(name)
    conn = sqlite3.connect(DB)
    existing = {row[0] for row in conn.execute("SELECT name FROM packages WHERE system='maven'")}
    conn.close()
    missing = [name for name in names if name not in existing][:TARGET]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"{len(names)} candidates; {len(missing)} missing -> {OUT}")


if __name__ == "__main__":
    main()
