from __future__ import annotations

import json

from mw.scan_diff import (
    PackageChange, diff_maps, findings_for, lookup, load_index,
    parse_manifest, sarif, summary,
)


def test_parse_npm_lockfile():
    text = json.dumps({
        "packages": {
            "": {"name": "root"},
            "node_modules/a": {"version": "1.0.0"},
            "node_modules/@scope/b": {"version": "2.0.0"},
        }
    })
    assert parse_manifest("package-lock.json", text) == {
        "a": "1.0.0", "@scope/b": "2.0.0",
    }


def test_parse_pypi_requirements():
    text = "requests==2.31.0\n# comment\nflask[async]>=3\n"
    parsed = parse_manifest("requirements.txt", text)
    assert parsed["requests"] == "2.31.0"
    assert "flask" in parsed


def test_parse_pyproject_and_poetry_lock():
    pyproject = '''
[project]
dependencies = ["requests==2.31.0", "click>=8"]
'''
    assert parse_manifest("pyproject.toml", pyproject)["requests"] == "2.31.0"
    poetry = '''
[[package]]
name = "Werkzeug"
version = "3.0.0"
'''
    assert parse_manifest("poetry.lock", poetry)["werkzeug"] == "3.0.0"


def test_diff_maps_added_and_upgraded():
    assert diff_maps({"a": "1.0.0", "b": "1"}, {"a": "2.0.0", "b": "1", "c": "3"}) == [
        ("a", "2.0.0", "1.0.0"), ("c", "3", None),
    ]


def test_findings_lookup_and_sarif():
    index = {
        "model_version": "0.5.3",
        "packages": {
            "npm:pkg": {
                "system": "npm", "name": "pkg", "score": 62.0,
                "band": "high", "confidence": "high", "coverage": 0.3,
                "risk_type": "Maintainer takeover",
            }
        },
    }
    assert lookup(index, "npm", "pkg")["score"] == 62.0
    findings = findings_for(
        [PackageChange("npm", "pkg", "2.0.0", "1.0.0", "package-lock.json")],
        index,
    )
    assert findings[0]["old_version"] == "1.0.0"
    assert summary(findings, 1)["bands"] == {"high": 1}
    doc = sarif(findings, "0.5.3")
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"][0]["level"] == "error"
    assert doc["runs"][0]["results"][0]["properties"]["name"] == "pkg"
