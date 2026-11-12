from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx


class CachedClient:
    """Small JSON client with an on-disk cache and a simple rate limiter."""

    def __init__(
        self,
        cache_dir: Path,
        timeout_s: float = 20.0,
        ttl_h: int = 24,
        rate_limit_qps: float = 5.0,
        user_agent: str = "MaintainerWatch/0.1",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_s = ttl_h * 3600
        self.min_interval = 1.0 / rate_limit_qps if rate_limit_qps > 0 else 0.0
        self._last = 0.0
        self._client = httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent, **(headers or {})},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CachedClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, key: str) -> Any | None:
        p = self._cache_path(key)
        if not p.exists() or (time.time() - p.stat().st_mtime) > self.ttl_s:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, key: str, value: Any) -> None:
        p = self._cache_path(key)
        try:
            p.write_text(json.dumps(value), encoding="utf-8")
        except OSError:
            pass

    def _throttle(self) -> None:
        if self.min_interval:
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.time()

    def get_json(self, url: str, *, headers: dict[str, str] | None = None,
                 use_cache: bool = True) -> Any | None:
        cache_key = url + "|" + json.dumps(headers or {}, sort_keys=True)
        if use_cache:
            cached = self._read_cache(cache_key)
            if cached is not None:
                return cached
        for attempt in range(4):
            self._throttle()
            try:
                r = self._client.get(url, headers=headers)
            except httpx.HTTPError:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                try:
                    data = r.json()
                except ValueError:
                    return None
                if use_cache:
                    self._write_cache(cache_key, data)
                return data
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        return None

    def get_text(self, url: str, *, headers: dict[str, str] | None = None,
                 use_cache: bool = True) -> str | None:
        cache_key = "text:" + url + "|" + json.dumps(headers or {}, sort_keys=True)
        if use_cache:
            cached = self._read_cache(cache_key)
            if isinstance(cached, str):
                return cached
        for attempt in range(4):
            self._throttle()
            try:
                r = self._client.get(url, headers=headers)
            except httpx.HTTPError:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                if use_cache:
                    self._write_cache(cache_key, r.text)
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        return None

    def post_json(self, url: str, payload: Any, *, headers: dict[str, str] | None = None) -> Any | None:
        for attempt in range(4):
            self._throttle()
            try:
                r = self._client.post(url, json=payload, headers=headers)
            except httpx.HTTPError:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    return None
            if r.status_code in (403, 429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        return None
