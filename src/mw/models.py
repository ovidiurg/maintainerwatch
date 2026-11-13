from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Package(BaseModel):
    system: str
    name: str
    normalized: str | None = None
    downloads_weekly: int = 0
    osv_count: int = 0
    repo_url: str | None = None
    license: str | None = None
    license_classifier: str | None = None
    first_seen: str | None = None
    dependencies_count: int = 0
    fan_in: int = 0


class Version(BaseModel):
    system: str
    name: str
    version: str
    published_at: str | None = None
    publisher_name: str | None = None
    publisher_email: str | None = None
    publisher_key_id: str | None = None
    has_sig: bool = False
    has_provenance: bool = False
    is_yanked: bool = False


class Maintainer(BaseModel):
    system: str
    name: str
    identity: str
    role: str = "maintainer"
    source: str = "registry"
    account_created_at: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None


class RepoStats(BaseModel):
    system: str
    name: str
    repo_url: str | None = None
    owner: str | None = None
    owner_created_at: str | None = None
    contributors_12m: int = 0
    top_author_share: float = 0.0
    last_commit_at: str | None = None
    scorecard_score: float | None = None
    license: str | None = None


class IdentityLink(BaseModel):
    system: str
    name: str
    id_a: str
    id_b: str
    link_type: str
    confidence: str
    evidence_url: str | None = None
    observed_at: str | None = None


class SignalEvidence(BaseModel):
    value: float
    applicable: bool = True
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    system: str
    name: str
    score: float
    band: str
    signals: dict[str, SignalEvidence]
    model_version: str
    inputs_hash: str
    computed_at: datetime
