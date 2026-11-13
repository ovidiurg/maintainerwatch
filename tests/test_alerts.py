from __future__ import annotations

from mw.config import AlertRule
from mw.pipeline import _webhook_payload


def test_generic_webhook_payload():
    rule = AlertRule(name="high", min_score=40)
    alerts = [
        {"system": "npm", "name": "a", "score": 60.0, "band": "high"},
    ]
    payload = _webhook_payload(rule, alerts, "generic")
    assert payload["rule"] == "high"
    assert payload["count"] == 1
    assert payload["alerts"] == alerts
    assert "matched 1" in payload["text"]


def test_slack_webhook_payload():
    rule = AlertRule(name="high", min_score=40)
    alerts = [{"system": "npm", "name": "a", "score": 60.0, "band": "high"}]
    payload = _webhook_payload(rule, alerts, "slack")
    assert "npm/a" in payload["text"]


def test_discord_webhook_payload():
    rule = AlertRule(name="high", min_score=40)
    alerts = [{"system": "npm", "name": "a", "score": 60.0, "band": "high"}]
    payload = _webhook_payload(rule, alerts, "discord")
    assert "npm/a" in payload["content"]
