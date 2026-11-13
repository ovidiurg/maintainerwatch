#!/usr/bin/env python3
"""Build the hybrid validation dataset metadata.

Usage:
    python scripts/build_validation_dataset.py

Fetches public malicious-package / incident metadata, normalises it to the
validation schema and writes JSONL under validation/v1/. Samples are never
downloaded or committed; only metadata and source attribution are stored.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation" / "v1"
DB = ROOT / "data" / "maintainerwatch.sqlite"

DATASET_VERSION = "v1"
SCHEMA_VERSION = "1.0"
GENERATED_AT = datetime.now(timezone.utc).isoformat()
RECENT_FROM = "2024-01-01"

SYSTEM_MAP = {
    "npm": "npm",
    "PyPI": "pypi",
    "pypi": "pypi",
    "crates.io": "crates",
    "crates": "crates",
    "Maven": "maven",
    "maven": "maven",
    "RubyGems": "rubygems",
    "rubygems": "rubygems",
    "Go": "go",
    "NuGet": "nuget",
    "Packagist": "packagist",
}

OSV_ZIPS = {
    "npm": "https://osv-vulnerabilities.storage.googleapis.com/npm/all.zip",
    "PyPI": "https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip",
    "crates.io": "https://osv-vulnerabilities.storage.googleapis.com/crates.io/all.zip",
    "Maven": "https://osv-vulnerabilities.storage.googleapis.com/Maven/all.zip",
}

CAPS = {
    "osv": 15000,
    "dependencywatch": 8000,
    "datadog": 3000,
    "tstromberg": 3000,
    "maloss": 2000,
    "controls": 500,
}

SOURCES = {
    "ossf-malicious-packages": {
        "name": "OpenSSF Malicious Packages",
        "url": "https://github.com/ossf/malicious-packages",
        "license": "Apache-2.0",
        "access": "public",
        "usage": "positive",
    },
    "osv": {
        "name": "OSV.dev",
        "url": "https://osv.dev",
        "license": "public data",
        "access": "public",
        "usage": "positive",
    },
    "dependencywatch": {
        "name": "DependencyWatch.io",
        "url": "https://dependencywatch.io",
        "license": "free reuse with attribution",
        "access": "public",
        "usage": "positive + incident context",
    },
    "datadog": {
        "name": "Datadog Malicious Software Packages Dataset",
        "url": "https://github.com/DataDog/malicious-software-packages-dataset",
        "license": "Apache-2.0",
        "access": "public metadata; encrypted samples",
        "usage": "positive snapshot",
    },
    "tstromberg": {
        "name": "upstream-supplychain-attacks",
        "url": "https://github.com/tstromberg/upstream-supplychain-attacks",
        "license": "Apache-2.0",
        "access": "public",
        "usage": "incident context",
    },
    "maloss": {
        "name": "MalOSS",
        "url": "https://github.com/osssanitizer/maloss",
        "license": "MIT (code/lists); samples restricted",
        "access": "public metadata",
        "usage": "positive historical",
    },
    "manual": {
        "name": "MaintainerWatch curated dossiers",
        "url": "docs/incident-validation.md",
        "license": "public reports",
        "access": "public",
        "usage": "curated takeover/sabotage",
    },
}

MANUAL = [
    {
        "id": "manual-event-stream-2018",
        "title": "event-stream malicious flatmap-stream dependency",
        "system": "npm",
        "package": "event-stream",
        "versions": ["3.3.6"],
        "compromise": "2018-11-21",
        "disclosure": "2018-11-26",
        "attack_type": "account_takeover",
        "severity": "high",
        "url": "https://github.com/dominictarr/event-stream/issues/116",
    },
    {
        "id": "manual-ua-parser-js-2021",
        "title": "ua-parser-js account hijack",
        "system": "npm",
        "package": "ua-parser-js",
        "versions": ["0.7.29", "0.7.30", "1.0.0"],
        "compromise": "2021-10-22",
        "disclosure": "2021-10-22",
        "attack_type": "account_takeover",
        "severity": "critical",
        "url": "https://github.com/faisalman/ua-parser-js/issues/536",
    },
    {
        "id": "manual-colors-2022",
        "title": "colors maintainer sabotage",
        "system": "npm",
        "package": "colors",
        "versions": ["1.4.44-liberty-2"],
        "compromise": "2022-01-08",
        "disclosure": "2022-01-08",
        "attack_type": "protestware",
        "severity": "high",
        "url": "https://github.com/Marak/colors.js/issues/285",
    },
    {
        "id": "manual-node-ipc-2022",
        "title": "node-ipc protestware",
        "system": "npm",
        "package": "node-ipc",
        "versions": ["10.1.1", "10.1.2", "11.0.0", "9.2.3"],
        "compromise": "2022-03-15",
        "disclosure": "2022-03-15",
        "attack_type": "protestware",
        "severity": "high",
        "url": "https://github.com/RIAEvangelist/node-ipc/issues/233",
    },
    {
        "id": "manual-xz-utils-2024",
        "title": "xz-utils backdoor",
        "system": "github",
        "package": "tukaani-project/xz",
        "versions": ["5.6.0", "5.6.1"],
        "compromise": "2024-02-24",
        "disclosure": "2024-03-29",
        "attack_type": "account_takeover",
        "severity": "critical",
        "url": "https://www.openwall.com/lists/oss-security/2024/03/29/4",
    },
]


def http_json(client: httpx.Client, url: str):
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def http_text(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def iso(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def cutoff_before(value: str | None) -> str | None:
    if not value:
        return None
    try:
        day = date.fromisoformat(value[:10]) - timedelta(days=1)
    except ValueError:
        return None
    return f"{day.isoformat()}T00:00:00Z"


def infer_attack_type(text: str) -> str:
    lowered = text.lower()
    if "typosquat" in lowered:
        return "typosquat"
    if "dependency confusion" in lowered or "dependency-confusion" in lowered:
        return "dependency_confusion"
    if "account takeover" in lowered or "hijack" in lowered or "compromised maintainer" in lowered:
        return "account_takeover"
    if "sabotage" in lowered:
        return "maintainer_sabotage"
    if "protest" in lowered or "protestware" in lowered:
        return "protestware"
    if "worm" in lowered:
        return "worm"
    return "malicious_package"


def incident_record(
    incident_id: str,
    title: str,
    ecosystem: str,
    attack_type: str,
    summary: str,
    disclosure: str | None,
    cutoff: str | None,
    cutoff_basis: str,
    source_type: str,
    source_license: str,
    source_urls: list[str],
    systems: list[str] | None = None,
    severity: str = "unknown",
    confidence: str = "high",
    sample_available: bool = False,
    notes: str = "",
) -> dict:
    return {
        "incident_id": incident_id,
        "title": title,
        "ecosystem": ecosystem,
        "systems": systems or ([ecosystem] if ecosystem else []),
        "attack_type": attack_type,
        "summary": summary,
        "disclosure_date": disclosure,
        "observation_cutoff": cutoff,
        "cutoff_basis": cutoff_basis,
        "severity": severity,
        "source_urls": source_urls[:10],
        "source_types": [source_type],
        "source_licenses": [source_license],
        "confidence": confidence,
        "sample_available": sample_available,
        "priority": "high" if (disclosure or "") >= RECENT_FROM else "normal",
        "notes": notes,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
    }


def package_record(
    incident_id: str,
    system: str,
    package: str,
    versions: list[str] | None,
    label: str,
    source: str,
    source_url: str | None,
    confidence: str = "high",
    sample_available: bool = False,
    notes: str = "",
) -> dict:
    clean_versions = sorted({v for v in (versions or []) if v})
    return {
        "incident_id": incident_id,
        "system": system,
        "package": package,
        "affected_versions": clean_versions,
        "label": label,
        "label_confidence": confidence,
        "source": source,
        "source_urls": [source_url] if source_url else [],
        "sample_available": sample_available,
        "notes": notes,
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
    }


def build_osv(client: httpx.Client):
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    for ecosystem, url in OSV_ZIPS.items():
        try:
            response = client.get(url, timeout=300)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"osv {ecosystem}: {exc}", file=sys.stderr)
            continue
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        records = []
        for name in archive.namelist():
            if not name.endswith(".json") or "MAL-" not in name:
                continue
            try:
                doc = json.loads(archive.read(name))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            mal_id = str(doc.get("id", ""))
            if not mal_id.startswith("MAL-"):
                continue
            published = iso(doc.get("published") or doc.get("modified"))
            if not published:
                continue
            text = f"{doc.get('summary', '')} {doc.get('details', '')}"
            atype = infer_attack_type(text)
            for affected in doc.get("affected") or []:
                package = affected.get("package") or {}
                system = SYSTEM_MAP.get(package.get("ecosystem"))
                pkg_name = package.get("name")
                if not system or not pkg_name:
                    continue
                versions = list(affected.get("versions") or [])
                for range_ in affected.get("ranges") or []:
                    for event in range_.get("events") or []:
                        introduced = event.get("introduced")
                        if introduced and introduced != "0":
                            versions.append(introduced)
                records.append(
                    {
                        "id": mal_id,
                        "published": published,
                        "attack_type": atype,
                        "system": system,
                        "package": pkg_name,
                        "versions": versions,
                        "summary": doc.get("summary") or "",
                    }
                )
        recent = [r for r in records if r["published"] >= RECENT_FROM]
        older = [
            r for r in records
            if r["published"] < RECENT_FROM
            and int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 10 == 0
        ]
        selected = (recent + older)[: CAPS["osv"]]
        groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for record in selected:
            groups[(record["system"], record["published"][:7], record["attack_type"])].append(record)
        for (system, month, atype), rows in groups.items():
            incident_id = f"osv-{system}-{month}-{atype}"
            earliest = min(r["published"] for r in rows)
            incidents[incident_id] = incident_record(
                incident_id,
                f"OSV MAL reports: {system} {month} ({atype})",
                system,
                atype,
                f"{len(rows)} OpenSSF/OSV MAL reports grouped by month, ecosystem and attack type.",
                earliest,
                cutoff_before(earliest),
                "disclosure_minus_1d",
                "osv_mal",
                "Apache-2.0",
                [f"https://osv.dev/vulnerability/{r['id']}" for r in rows],
                confidence="high",
                notes="Synthetic incident grouping of OSV MAL records.",
            )
            for record in rows:
                packages.append(
                    package_record(
                        incident_id,
                        record["system"],
                        record["package"],
                        record["versions"],
                        record["attack_type"],
                        "osv",
                        f"https://osv.dev/vulnerability/{record['id']}",
                    )
                )
    print(f"osv: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_dependencywatch(client: httpx.Client):
    incidents_doc = http_json(client, "https://dependencywatch.io/api/v1/incidents")
    packages_doc = http_json(client, "https://dependencywatch.io/api/v1/packages")
    incidents: dict[str, dict] = {}
    for item in incidents_doc.get("incidents", []):
        published = iso(item.get("published"))
        text = " ".join(
            [item.get("kind", ""), item.get("summary", ""), " ".join(item.get("tags", []))]
        )
        atype = infer_attack_type(text)
        incidents[item["id"]] = incident_record(
            item["id"],
            item.get("title") or item["id"],
            (item.get("ecosystems") or ["other"])[0],
            atype,
            item.get("summary") or "",
            published,
            cutoff_before(published),
            "disclosure_minus_1d",
            "dependencywatch",
            "free reuse with attribution",
            [item.get("url")] if item.get("url") else [],
            systems=[SYSTEM_MAP.get(eco, eco) for eco in item.get("ecosystems") or []],
            severity=item.get("severity") or "unknown",
            confidence="high",
            notes="DependencyWatch incident metadata.",
        )
    packages: list[dict] = []
    for item in packages_doc.get("packages", []):
        system = SYSTEM_MAP.get(item.get("ecosystem"))
        if not system:
            continue
        for incident_id in item.get("incidents") or []:
            if incident_id not in incidents:
                continue
            atype = incidents[incident_id]["attack_type"]
            packages.append(
                package_record(
                    incident_id,
                    system,
                    item.get("name"),
                    item.get("compromisedVersions"),
                    atype,
                    "dependencywatch",
                    item.get("url"),
                )
            )
            if len(packages) >= CAPS["dependencywatch"]:
                break
        if len(packages) >= CAPS["dependencywatch"]:
            break
    print(f"dependencywatch: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_datadog(client: httpx.Client):
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    base = "https://raw.githubusercontent.com/DataDog/malicious-software-packages-dataset/main/samples"
    for ecosystem in ("npm", "pypi"):
        try:
            manifest = http_json(client, f"{base}/{ecosystem}/manifest.json")
        except httpx.HTTPError as exc:
            print(f"datadog {ecosystem}: {exc}", file=sys.stderr)
            continue
        items = sorted(
            manifest.items(),
            key=lambda item: hashlib.sha256(item[0].encode()).hexdigest(),
        )[: CAPS["datadog"] // 2]
        incident_id = f"datadog-{ecosystem}-snapshot-2026-11-13"
        incidents[incident_id] = incident_record(
            incident_id,
            f"Datadog malicious packages snapshot ({ecosystem})",
            ecosystem,
            "malicious_package",
            f"{len(items)} package entries from the DataDog manifest snapshot.",
            "2026-11-13",
            "2026-01-01T00:00:00Z",
            "snapshot",
            "vendor_dataset",
            "Apache-2.0",
            [f"https://github.com/DataDog/malicious-software-packages-dataset/tree/main/samples/{ecosystem}"],
            confidence="medium",
            sample_available=True,
            notes="Snapshot metadata; no per-package discovery date.",
        )
        for name, versions in items:
            packages.append(
                package_record(
                    incident_id,
                    SYSTEM_MAP.get(ecosystem, ecosystem),
                    name,
                    versions or [],
                    "malicious_package",
                    "datadog",
                    None,
                    confidence="medium",
                    sample_available=True,
                    notes="null versions means all versions are considered malicious.",
                )
            )
    print(f"datadog: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_tstromberg(client: httpx.Client):
    base = "https://raw.githubusercontent.com/tstromberg/upstream-supplychain-attacks/main"
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    try:
        summary_text = http_text(client, f"{base}/oss_summary.csv")
        artifacts_text = http_text(client, f"{base}/oss_artifacts.csv")
    except httpx.HTTPError as exc:
        print(f"tstromberg: {exc}", file=sys.stderr)
        return incidents, packages
    for row in csv.DictReader(io.StringIO(summary_text)):
        incident_id = f"tstromberg-{row.get('id')}"
        start = iso(row.get("start_date"))
        end = iso(row.get("end_date"))
        disclosure = end or start or (f"{row.get('year')}-01-01" if row.get("year") else "2026-11-13")
        if start or end or row.get("year"):
            cutoff = cutoff_before(start or disclosure)
            cutoff_basis = "start_date_minus_1d"
        else:
            cutoff = "2026-01-01T00:00:00Z"
            cutoff_basis = "snapshot"
        incidents[incident_id] = incident_record(
            incident_id,
            row.get("title") or incident_id,
            "other",
            infer_attack_type(" ".join([row.get("cause", ""), row.get("motive", ""), row.get("title", "")])),
            (row.get("synopsis") or "")[:1000],
            disclosure,
            cutoff,
            cutoff_basis,
            "incident_dataset",
            "Apache-2.0",
            [
                value for value in (
                    row.get("target_website"),
                    row.get("target_repo"),
                    row.get("references"),
                    f"https://github.com/tstromberg/upstream-supplychain-attacks/tree/main/oss/{row.get('id')}",
                ) if value
            ],
            confidence="medium",
            notes="Incident-level metadata from tstromberg/upstream-supplychain-attacks.",
        )
    for row in csv.DictReader(io.StringIO(artifacts_text)):
        system = SYSTEM_MAP.get(row.get("ecosystem"))
        package = row.get("package")
        if not system or not package:
            continue
        incident_id = f"tstromberg-{row.get('attack_id')}"
        if incident_id not in incidents:
            continue
        versions = [v.strip() for v in (row.get("versions") or "").split(",") if v.strip()]
        packages.append(
            package_record(
                incident_id,
                system,
                package,
                versions,
                incidents[incident_id]["attack_type"],
                "tstromberg",
                row.get("repo") or row.get("website"),
                confidence="medium",
            )
        )
        if len(packages) >= CAPS["tstromberg"]:
            break
    print(f"tstromberg: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_maloss(client: httpx.Client):
    base = "https://raw.githubusercontent.com/osssanitizer/maloss/master/malware"
    lists = {
        "npm": "npmjs-mal-pkgs.txt",
        "pypi": "pypi-mal-pkgs.txt",
        "rubygems": "rubygems-mal-pkgs.dec2020.txt",
        "maven": "maven-mal-pkgs.txt",
    }
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    for system, filename in lists.items():
        try:
            text = http_text(client, f"{base}/{filename}")
        except httpx.HTTPError as exc:
            print(f"maloss {filename}: {exc}", file=sys.stderr)
            continue
        names = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("package"):
                continue
            names.append(line.split()[0])
        names = sorted(set(names))[: CAPS["maloss"] // 2]
        incident_id = f"maloss-{system}-snapshot-2020-12-01"
        incidents[incident_id] = incident_record(
            incident_id,
            f"MalOSS malicious package list ({system})",
            system,
            "malicious_package",
            f"{len(names)} packages from the MalOSS list.",
            "2020-12-01",
            "2020-11-30T00:00:00Z",
            "snapshot",
            "academic_dataset",
            "MIT",
            [f"https://github.com/osssanitizer/maloss/blob/master/malware/{filename}"],
            confidence="medium",
            notes="List snapshot; no per-package release date.",
        )
        for name in names:
            packages.append(
                package_record(
                    incident_id,
                    system,
                    name,
                    [],
                    "malicious_package",
                    "maloss",
                    None,
                    confidence="medium",
                )
            )
    print(f"maloss: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_manual():
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    for item in MANUAL:
        incidents[item["id"]] = incident_record(
            item["id"],
            item["title"],
            item["system"],
            item["attack_type"],
            item["title"],
            item["disclosure"],
            cutoff_before(item["compromise"]),
            "manually_set",
            "manual",
            "public reports",
            [item["url"]],
            severity=item["severity"],
            confidence="high",
            notes="Curated incident dossier.",
        )
        packages.append(
            package_record(
                item["id"],
                item["system"],
                item["package"],
                item["versions"],
                item["attack_type"],
                "manual",
                item["url"],
            )
        )
    print(f"manual: {len(incidents)} incidents, {len(packages)} packages")
    return incidents, packages


def build_controls(positive_packages: list[dict], incidents: dict[str, dict]) -> list[dict]:
    if not DB.exists():
        print("controls: database missing, skipping", file=sys.stderr)
        return []
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT system, name, downloads_weekly, first_seen FROM packages"
    ).fetchall()
    conn.close()

    positives = {(p["system"], p["package"]) for p in positive_packages}
    recent = [i for i, inc in incidents.items() if inc.get("priority") == "high"]
    controls: list[dict] = []
    for system in ("npm", "pypi", "crates", "maven"):
        candidates = [
            row for row in rows
            if row["system"] == system and (row["system"], row["name"]) not in positives
        ]
        candidates.sort(key=lambda row: row["downloads_weekly"] or 0, reverse=True)
        for row in candidates[: CAPS["controls"]]:
            key = f"{system}-{row['name']}-2026-01-01"
            digest = hashlib.sha256(key.encode()).hexdigest()
            controls.append(
                {
                    "control_id": key,
                    "system": system,
                    "package": row["name"],
                    "as_of": "2026-01-01T00:00:00Z",
                    "label": "benign",
                    "matched_incident_id": recent[int(digest, 16) % len(recent)] if recent else None,
                    "match_features": {
                        "downloads_weekly": row["downloads_weekly"] or 0,
                        "first_seen": row["first_seen"],
                    },
                    "source": "maintainerwatch-db",
                    "exclusion_checks": {
                        "positive_package_set": True,
                        "osv_mal": True,
                    },
                    "split": "test" if int(digest, 16) % 5 == 0 else "train",
                    "schema_version": SCHEMA_VERSION,
                    "dataset_version": DATASET_VERSION,
                }
            )
    print(f"controls: {len(controls)}")
    return controls


def dedupe(incidents: dict[str, dict], packages: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for package in packages:
        key = (package["incident_id"], package["system"], package["package"])
        if key not in merged:
            merged[key] = package
            continue
        current = merged[key]
        current["affected_versions"] = sorted(
            set(current["affected_versions"]) | set(package["affected_versions"])
        )
        current["source_urls"] = sorted(
            set(current["source_urls"]) | set(package["source_urls"])
        )
        if current["label_confidence"] != "high" and package["label_confidence"] == "high":
            current["label_confidence"] = "high"
    return list(merged.values())


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    incidents: dict[str, dict] = {}
    packages: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": "MaintainerWatch/0.4.3"}) as client:
        for builder in (build_osv, build_dependencywatch, build_datadog, build_tstromberg, build_maloss):
            built_incidents, built_packages = builder(client)
            incidents.update(built_incidents)
            packages.extend(built_packages)
    manual_incidents, manual_packages = build_manual()
    incidents.update(manual_incidents)
    packages.extend(manual_packages)

    packages = dedupe(incidents, packages)
    controls = build_controls(packages, incidents)

    incidents_list = sorted(
        incidents.values(),
        key=lambda item: (item.get("disclosure_date") or "", item["incident_id"]),
        reverse=True,
    )
    packages_list = sorted(
        packages,
        key=lambda item: (item["system"], item["package"], item["incident_id"]),
    )

    write_jsonl(OUT / "incidents.jsonl", incidents_list)
    write_jsonl(OUT / "incident_packages.jsonl", packages_list)
    write_jsonl(OUT / "controls.jsonl", controls)

    def count_by(field: str, records: list[dict]) -> dict[str, int]:
        return dict(Counter(str(record.get(field)) for record in records).most_common())

    manifest = {
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "builder": "scripts/build_validation_dataset.py",
        "recent_from": RECENT_FROM,
        "counts": {
            "incidents": len(incidents_list),
            "incident_packages": len(packages_list),
            "controls": len(controls),
        },
        "incidents_by_year": count_by("disclosure_date", [
            {"disclosure_date": (item.get("disclosure_date") or "")[:4]} for item in incidents_list
        ]),
        "incidents_by_attack_type": count_by("attack_type", incidents_list),
        "incidents_by_priority": count_by("priority", incidents_list),
        "packages_by_system": count_by("system", packages_list),
        "packages_by_source": count_by("source", packages_list),
        "packages_by_confidence": count_by("label_confidence", packages_list),
        "controls_by_system": count_by("system", controls),
        "sources": SOURCES,
        "files": {
            "incidents.jsonl": sha256(OUT / "incidents.jsonl"),
            "incident_packages.jsonl": sha256(OUT / "incident_packages.jsonl"),
            "controls.jsonl": sha256(OUT / "controls.jsonl"),
        },
        "notes": (
            "Metadata only. Malicious samples are not included or redistributed. "
            "Some incidents are synthetic groupings of OSV MAL records; snapshot "
            "sources have no per-package discovery date. Controls are matched from "
            "the local MaintainerWatch database and are not guaranteed benign."
        ),
    }
    (OUT / "sources.yaml").write_text(yaml.safe_dump(SOURCES, sort_keys=True), encoding="utf-8")
    manifest["files"]["sources.yaml"] = sha256(OUT / "sources.yaml")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
