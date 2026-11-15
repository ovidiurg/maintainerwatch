from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "intake_osv_labels", ROOT / "scripts/intake_osv_labels.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extract_malicious_candidates_only():
    package = {
        "system": "npm",
        "name": "bad-pkg",
        "version": "1.0.0",
        "cutoff": "2025-01-01T00:00:00Z",
    }
    response = {
        "vulns": [
            {"id": "MAL-2025-1", "aliases": ["GHSA-1234"], "summary": "malicious"},
            {"id": "GHSA-normal", "summary": "normal advisory"},
        ]
    }
    rows = MODULE.extract_candidates(package, response)
    assert len(rows) == 1
    assert rows[0]["advisory_id"] == "MAL-2025-1"
    assert rows[0]["status"] == "candidate"
    assert rows[0]["reviewed"] is False
    assert rows[0]["url"].startswith("https://osv.dev/vulnerability/MAL-2025-1")


def test_extract_no_malicious_candidates():
    package = {"system": "pypi", "name": "safe-pkg"}
    assert MODULE.extract_candidates(package, {"vulns": [{"id": "CVE-2025-1"}]}) == []
