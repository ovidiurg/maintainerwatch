from __future__ import annotations

from mw.export import _cyclonedx_document, _osv_document, _purl, _spdx_document

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
