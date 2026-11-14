from __future__ import annotations

import os

import httpx

from .config import Config


class DynamicWorkerError(RuntimeError):
    pass


def scan_remote(cfg: Config, system: str, name: str, version: str) -> dict:
    if not cfg.dynamic.worker_url:
        raise DynamicWorkerError("dynamic worker is not configured")
    url = cfg.dynamic.worker_url.rstrip("/") + "/scan"
    token = os.environ.get(cfg.dynamic.token_env)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.post(
            url,
            json={"system": system, "name": name, "version": version},
            headers=headers,
            timeout=cfg.dynamic.timeout_s,
        )
    except httpx.HTTPError as exc:
        raise DynamicWorkerError(f"worker request failed: {exc}") from exc
    if response.status_code != 200:
        raise DynamicWorkerError(
            f"worker returned {response.status_code}: {response.text[:200]}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise DynamicWorkerError("worker returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise DynamicWorkerError("worker returned an invalid payload")
    return payload
