from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
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


class Config(BaseModel):
    ecosystems: list[str] = Field(default_factory=lambda: ["npm", "pypi"])
    top_n: int = 2000
    github_token_env: str = "GITHUB_TOKEN"
    http: HttpConfig = Field(default_factory=HttpConfig)
    weights: dict[str, int] = Field(
        default_factory=lambda: {
            "publisher_change": 30,
            "bus_factor": 20,
            "account_age": 15,
            "release_anomaly": 15,
            "signing_gap": 10,
            "typosquat": 10,
        }
    )
    min_identity_confidence: str = "medium"
    model_version: str = "0.1.0"
    osint: OsintConfig = Field(default_factory=OsintConfig)
    data_dir: Path = DEFAULT_DATA_DIR
    db_path: Path = DEFAULT_DB_PATH

    @property
    def github_token(self) -> str | None:
        return os.environ.get(self.github_token_env) or _gh_cli_token()


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
