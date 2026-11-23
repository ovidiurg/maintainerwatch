from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from . import __version__, db, providers
from .config import Config

PRIORITY = [
    "system", "name", "version", "score", "band", "model_version",
    "inputs_hash", "computed_at", "downloads_weekly", "osv_count",
    "repo_url", "license", "license_classifier", "license_repo",
    "dependencies_count", "fan_in", "fan_in_transitive",
]

OSV_ECOSYSTEM = {
    "npm": "npm",
    "pypi": "PyPI",
    "crates": "crates.io",
    "maven": "Maven",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _records(cfg: Config, *, include_provider_context: bool = False) -> list[dict]:
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = conn.execute(
        """SELECT s.system, s.name, s.score, s.band, s.model_version,
                  s.inputs_hash, s.computed_at,
                  p.downloads_weekly, p.osv_count, p.repo_url, p.license,
                  p.license_classifier, p.dependencies_count, p.fan_in,
                  p.fan_in_transitive, r.license AS license_repo,
                  (SELECT v.version FROM versions v
                   WHERE v.system = s.system AND v.name = s.name
                   ORDER BY v.published_at DESC LIMIT 1) AS version
           FROM scores s
           LEFT JOIN packages p ON p.system = s.system AND p.name = s.name
           LEFT JOIN repo_stats r ON r.system = s.system AND r.name = s.name
           WHERE s.model_version = ?
           ORDER BY s.score DESC, s.name ASC""",
        (cfg.model_version,),
    ).fetchall()
    signal_rows = conn.execute(
        "SELECT system, name, signal_type, value FROM signals WHERE model_version=?",
        (cfg.model_version,),
    ).fetchall()

    signal_map: dict[tuple[str, str], dict[str, float]] = {}
    for r in signal_rows:
        signal_map.setdefault((r["system"], r["name"]), {})[r["signal_type"]] = r["value"]

    records = []
    for r in rows:
        rec = {k: r[k] for k in r.keys()}
        for sig_name, value in signal_map.get((r["system"], r["name"]), {}).items():
            rec[f"sig_{sig_name}"] = value
        records.append(rec)

    if include_provider_context:
        keys = [(r["system"], r["name"]) for r in records]
        versions = {
            (r["system"], r["name"]): r.get("version") for r in records
        }
        contexts = providers.bulk_context(conn, keys, versions)
        for rec in records:
            rec["provider_context"] = contexts.get((rec["system"], rec["name"]))

    conn.close()
    return records


def _purl(record: dict) -> str:
    system = record["system"]
    name = record["name"]
    version = record.get("version")

    if system == "npm":
        if name.startswith("@") and "/" in name:
            scope, package = name.split("/", 1)
            base = f"pkg:npm/{quote(scope, safe='')}/{quote(package, safe='')}"
        else:
            base = f"pkg:npm/{quote(name, safe='')}"
    elif system == "pypi":
        base = f"pkg:pypi/{quote(name.lower(), safe='-._')}"
    elif system == "crates":
        base = f"pkg:cargo/{quote(name, safe='-._')}"
    elif system == "maven" and ":" in name:
        group, artifact = name.split(":", 1)
        base = f"pkg:maven/{quote(group, safe='.')}/{quote(artifact, safe='-._')}"
    elif system == "github":
        base = f"pkg:github/{name}"
    else:
        base = f"pkg:generic/{quote(name, safe='')}"

    return f"{base}@{version}" if version else base


def _spdx_id(record: dict) -> str:
    raw = f"{record['system']}-{record['name']}"
    return "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]+", "-", raw)


def _spdx_document(records: list[dict], tool_version: str) -> dict:
    created = _now()
    namespace = f"https://maintainerwatch.example/spdx/{uuid.uuid4()}"
    packages = []
    relationships = []

    for record in records:
        spdx_id = _spdx_id(record)
        license_name = record.get("license") or "NOASSERTION"
        package = {
            "SPDXID": spdx_id,
            "name": record["name"],
            "versionInfo": record.get("version") or "NOASSERTION",
            "downloadLocation": record.get("repo_url") or "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": license_name,
            "licenseDeclared": license_name,
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": _purl(record),
                }
            ],
            "annotations": [
                {
                    "annotationType": "OTHER",
                    "annotator": "Tool: MaintainerWatch",
                    "annotationDate": created,
                    "comment": (
                        f"risk score {record['score']} ({record['band']}); "
                        f"model {record['model_version']}"
                    ),
                }
            ],
        }
        packages.append(package)
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": spdx_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "MaintainerWatch dataset",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": created,
            "creators": [f"Tool: MaintainerWatch-{tool_version}"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def _license_entry(license_name: str | None) -> list[dict]:
    if not license_name:
        return []
    if re.fullmatch(r"[A-Za-z0-9.+\-]+", license_name):
        return [{"license": {"id": license_name}}]
    return [{"license": {"name": license_name}}]


def _cyclonedx_document(records: list[dict], tool_version: str) -> dict:
    components = []
    for record in records:
        purl = _purl(record)
        component = {
            "type": "library",
            "bom-ref": purl,
            "name": record["name"],
            "version": record.get("version") or "NOASSERTION",
            "purl": purl,
            "licenses": _license_entry(record.get("license")),
            "properties": [
                {"name": "maintainerwatch:score", "value": str(record["score"])},
                {"name": "maintainerwatch:band", "value": record["band"]},
                {"name": "maintainerwatch:fan_in", "value": str(record.get("fan_in") or 0)},
                {
                    "name": "maintainerwatch:fan_in_transitive",
                    "value": str(record.get("fan_in_transitive") or 0),
                },
                {
                    "name": "maintainerwatch:osv_count",
                    "value": str(record.get("osv_count") or 0),
                },
            ],
        }
        if record.get("repo_url"):
            component["externalReferences"] = [
                {"type": "vcs", "url": record["repo_url"]}
            ]
        components.append(component)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": _now(),
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "maintainerwatch",
                        "version": tool_version,
                    }
                ]
            },
            "component": {
                "type": "application",
                "bom-ref": "pkg:generic/maintainerwatch",
                "name": "MaintainerWatch",
                "version": tool_version,
            },
        },
        "components": components,
    }


def _osv_document(rows: list[dict]) -> dict:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        ecosystem = OSV_ECOSYSTEM.get(row["system"])
        if ecosystem is None:
            continue
        vuln = {"id": row["vuln_id"]}
        if row.get("severity"):
            vuln["severity"] = [{"type": "CVSS_V3", "score": row["severity"]}]
        if row.get("published_at"):
            vuln["published"] = row["published_at"]
        grouped.setdefault((ecosystem, row["name"]), []).append(vuln)

    results = [
        {
            "package": {"ecosystem": ecosystem, "name": name},
            "vulns": sorted(vulns, key=lambda item: item["id"]),
        }
        for (ecosystem, name), vulns in sorted(grouped.items())
    ]
    return {"results": results}


def export_dataset(cfg: Config, fmt: str = "parquet") -> tuple[Path, int]:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    if fmt == "osv":
        conn = db.connect(cfg.db_path)
        db.init_db(conn)
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT system, name, vuln_id, severity, published_at FROM osv"
            )
        ]
        conn.close()
        document = _osv_document(rows)
        path = cfg.data_dir / f"maintainerwatch-{stamp}-osv.json"
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path, len(document["results"])

    records = _records(cfg, include_provider_context=(fmt == "json"))

    if fmt == "parquet":
        import polars as pl

        path = cfg.data_dir / f"maintainerwatch-{stamp}.parquet"
        pl.DataFrame(records, infer_schema_length=None).write_parquet(path)
        return path, len(records)

    if fmt == "csv":
        path = cfg.data_dir / f"maintainerwatch-{stamp}.csv"
        keys: list[str] = list(PRIORITY)
        for rec in records:
            for k in rec:
                if k not in keys:
                    keys.append(k)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return path, len(records)

    if fmt == "json":
        path = cfg.data_dir / f"maintainerwatch-{stamp}.json"
        path.write_text(
            json.dumps(records, indent=2, default=str), encoding="utf-8"
        )
        return path, len(records)

    if fmt == "spdx":
        path = cfg.data_dir / f"maintainerwatch-{stamp}.spdx.json"
        document = _spdx_document(records, __version__)
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path, len(records)

    if fmt == "cyclonedx":
        path = cfg.data_dir / f"maintainerwatch-{stamp}.cdx.json"
        document = _cyclonedx_document(records, __version__)
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path, len(records)

    raise ValueError(f"unsupported export format: {fmt}")


def export_json(cfg: Config) -> str:
    return json.dumps(
        _records(cfg, include_provider_context=True), indent=2, default=str
    )
