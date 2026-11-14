from __future__ import annotations

import json
import os
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="MaintainerWatch dynamic worker")


class ScanRequest(BaseModel):
    system: str
    name: str
    version: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "sandbox_configured": bool(os.environ.get("DYNAMIC_SANDBOX_COMMAND")),
    }


@app.post("/scan")
def scan(request: ScanRequest):
    command = os.environ.get("DYNAMIC_SANDBOX_COMMAND")
    if not command:
        raise HTTPException(
            status_code=503,
            detail=(
                "no isolated sandbox configured; set DYNAMIC_SANDBOX_COMMAND "
                "to a gVisor/Docker runner"
            ),
        )
    try:
        completed = subprocess.run(
            [command],
            input=request.model_dump_json(),
            text=True,
            capture_output=True,
            timeout=float(os.environ.get("DYNAMIC_SANDBOX_TIMEOUT", "600")),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if completed.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=(completed.stderr or "sandbox failed")[-500:],
        )
    try:
        payload = json.loads(completed.stdout)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="sandbox returned invalid JSON") from exc
    return JSONResponse(payload)
