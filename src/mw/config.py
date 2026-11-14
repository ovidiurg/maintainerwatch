from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _default_config_path() -> Path:
    repo = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    if repo.exists():
        return repo
    packaged = Path(__file__).resolve().parent / "data" / "default.yaml"
    return packaged if packaged.exists() else repo


DEFAULT_CONFIG_PATH = _default_config_path()
DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "maintainerwatch.sqlite"


class HttpConfig(BaseModel):
    timeout_s: float = 20.0
    cache_ttl_h: int = 24
    rate_limit_qps: float = 5.0
    user_agent: str = "MaintainerWatch/0.1"


class OsintConfig(BaseModel):
    keybase: bool = True
    github_email: bool = True
    pypi_provenance: bool = True
    gpg: bool = True


class AlertRule(BaseModel):
    name: str
    min_score: float = 40.0
    signal: str | None = None
    min_signal: float = 0.5
    limit: int = 100
    webhook: str | None = None
    email: str | None = None


class SmtpConfig(BaseModel):
    host: str | None = None
    port: int = 587
    username: str | None = None
    password_env: str = "SMTP_PASSWORD"
    sender: str | None = None
    use_tls: bool = True


class AlertsConfig(BaseModel):
    rules: list[AlertRule] = Field(default_factory=list)
    webhook: str | None = None
    webhook_format: str = "generic"
    email: str | None = None
    timeout_s: float = 10.0
    smtp: SmtpConfig = Field(default_factory=SmtpConfig)


class ApiConfig(BaseModel):
    api_key_env: str = "MAINTAINERWATCH_API_KEY"
    rate_limit_rpm: int = 0


class Config(BaseModel):
    ecosystems: list[str] = Field(default_factory=lambda: ["npm", "pypi"])
    top_n: int = 2000
    github_token_env: str = "GITHUB_TOKEN"
    gitlab_token_env: str = "GITLAB_TOKEN"
    http: HttpConfig = Field(default_factory=HttpConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    weights: dict[str, int] = Field(
        default_factory=lambda: {
            "publisher_change": 30,
            "bus_factor": 20,
            "account_age": 15,
            "release_anomaly": 15,
            "signing_gap": 10,
            "typosquat": 10,
            "license_inconsistency": 5,
            "commit_anomaly": 15,
            "scorecard": 10,
            "dependency_risk": 15,
            "maintainer_continuity": 10,
            "install_script": 15,
            "osv_risk": 10,
            "depsdev_findings": 10,
            "package_age": 10,
        }
    )
    min_identity_confidence: str = "medium"
    model_version: str = "0.4.9"
    automation_identities: list[str] = Field(
        default_factory=lambda: [
            "npm-oidc-no-reply@github.com",
            "storybookbot@gmail.com",
        ]
    )
    automation_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\+oss-bot@",
            r"\[bot\]",
            r"^github-actions",
            r"no-reply@github\.com$",
        ]
    )
    osint: OsintConfig = Field(default_factory=OsintConfig)
    data_dir: Path = DEFAULT_DATA_DIR
    db_path: Path = DEFAULT_DB_PATH

    @property
    def github_token(self) -> str | None:
        return os.environ.get(self.github_token_env) or _gh_cli_token()

    @property
    def gitlab_token(self) -> str | None:
        return os.environ.get(self.gitlab_token_env) or None


@lru_cache(maxsize=1)
def _gh_cli_token() -> str | None:
    """Fall back to the GitHub CLI session so `gh auth login` is enough."""
    exe = shutil.which("gh")
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = Config(**raw)
    cfg.data_dir = Path(raw.get("data_dir", DEFAULT_DATA_DIR))
    cfg.db_path = Path(raw.get("db_path", cfg.data_dir / "maintainerwatch.sqlite"))
    return cfg
