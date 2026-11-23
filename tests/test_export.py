from __future__ import annotations

import json

from mw import db
from mw.config import load_config
from mw.export import (
    _cyclonedx_document, _osv_document, _purl, _spdx_document,
    _records, export_dataset, export_json,
)
from mw.models import Package, Version

RECORD = {
    "system": "npm",
    "name": "@scope/pkg",
    "version": "1.2.3",
    "score": 42.0,
    "band": "medium",
    "model_version": "0.3.0",
    "license": "MIT",
    "repo_url": "https://github.com/o/r",
    "fan_in": 2,
    "fan_in_transitive": 5,
    "osv_count": 1,
}


def test_purl():
    assert _purl({**RECORD, "name": "lodash", "version": "4.17.21"}) == (
        "pkg:npm/lodash@4.17.21"
    )
    assert _purl(RECORD) == "pkg:npm/%40scope/pkg@1.2.3"
    assert _purl({"system": "pypi", "name": "requests", "version": "2.31.0"}) == (
        "pkg:pypi/requests@2.31.0"
    )
    assert _purl(
        {"system": "maven", "name": "com.google.guava:guava", "version": "33.0"}
    ) == "pkg:maven/com.google.guava/guava@33.0"


def test_spdx_document():
    document = _spdx_document([RECORD], "0.3.0")
    assert document["spdxVersion"] == "SPDX-2.3"
    assert document["dataLicense"] == "CC0-1.0"
    package = document["packages"][0]
    assert package["licenseDeclared"] == "MIT"
    assert package["externalRefs"][0]["referenceLocator"].startswith("pkg:npm/")


def test_cyclonedx_document():
    document = _cyclonedx_document([RECORD], "0.3.0")
    assert document["bomFormat"] == "CycloneDX"
    assert document["specVersion"] == "1.5"
    component = document["components"][0]
    assert component["purl"].startswith("pkg:npm/")
    assert any(
        prop["name"] == "maintainerwatch:score" for prop in component["properties"]
    )


def test_osv_document():
    rows = [
        {
            "system": "npm",
            "name": "lodash",
            "vuln_id": "GHSA-1",
            "severity": "7.5",
            "published_at": "2024-01-01T00:00:00Z",
        }
    ]
    document = _osv_document(rows)
    assert document["results"][0]["package"] == {"ecosystem": "npm", "name": "lodash"}
    vuln = document["results"][0]["vulns"][0]
    assert vuln["id"] == "GHSA-1"
    assert vuln["severity"][0]["score"] == "7.5"


def _export_setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "export.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg", downloads_weekly=5)])
    db.upsert_versions(conn, [
        Version(system="npm", name="pkg", version="1.0.0", published_at="2024-01-01"),
    ])
    db.record_score(conn, "npm", "pkg", 60.0, "high", cfg.model_version, "hash", "2026-01-01")
    db.record_signal(
        conn, "npm", "pkg", "publisher_change", 1.0, "high", "{}",
        cfg.model_version, "2026-01-01",
    )
    db.upsert_osv(conn, [
        ("npm", "pkg", "GHSA-test", "7.5", "2024-01-01", None, None, None),
    ])
    conn.commit()
    conn.close()
    return cfg


def test_records_and_export_formats(tmp_path):
    cfg = _export_setup(tmp_path)
    records = _records(cfg)
    assert records[0]["system"] == "npm"
    assert records[0]["sig_publisher_change"] == 1.0
    assert "\"npm\"" in export_json(cfg)

    for fmt in ("json", "csv", "spdx", "cyclonedx", "osv", "parquet"):
        path, count = export_dataset(cfg, fmt)
        assert path.exists()
        assert count >= 1
        if fmt == "json":
            records = json.loads(path.read_text(encoding="utf-8"))
            assert "provider_context" in records[0]


def test_export_unsupported_format(tmp_path):
    cfg = _export_setup(tmp_path)
    try:
        export_dataset(cfg, "unknown")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parquet_handles_schema_after_inference_window(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "parquet.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    for index in range(150):
        license_value = None if index < 120 else "Apache Software License"
        db.upsert_packages(conn, [
            Package(system="npm", name=f"pkg-{index}", license=license_value)
        ])
        db.record_score(
            conn, "npm", f"pkg-{index}", 10.0 + index, "low",
            cfg.model_version, f"hash-{index}", "2026-01-01",
        )
    conn.commit()
    conn.close()

    path, count = export_dataset(cfg, "parquet")
    assert count == 150
    import polars as pl
    frame = pl.read_parquet(path)
    assert frame.height == 150
    assert "Apache Software License" in frame["license"].to_list()
