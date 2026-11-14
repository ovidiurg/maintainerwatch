from __future__ import annotations

from mw.ingest.depsdev import fetch_dependents
from mw.risk import impact_tier


class FakeClient:
    def get_json(self, url: str):
        assert 'express' in url
        return {
            "dependentCount": 975,
            "directDependentCount": 434,
            "indirectDependentCount": 558,
        }


def test_fetch_dependents():
    result = fetch_dependents(FakeClient(), "npm", "express", "4.21.2")
    assert result == {
        "dependent_count": 975,
        "direct_dependent_count": 434,
        "indirect_dependent_count": 558,
    }


def test_impact_tiers():
    assert impact_tier(1000) == "critical"
    assert impact_tier(100) == "high"
    assert impact_tier(10) == "medium"
    assert impact_tier(1) == "low"
    assert impact_tier(None) == "unknown"
