from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app

BODY = {"user_id": "u-test", "session_id": "s-test", "feature": "qa", "message": "Explain logs"}


def _post(headers: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json=BODY, headers=headers or {})
    return asyncio.run(send())


def test_generates_correlation_id_and_response_time(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    response = _post()
    cid = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", cid)
    assert float(response.headers["x-response-time-ms"]) >= 0
    assert response.json()["correlation_id"] == cid


def test_propagates_incoming_id_and_enriches_logs(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    response = _post({"x-request-id": "req-abcd1234"})
    assert response.headers["x-request-id"] == "req-abcd1234"

    api_logs = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()]
    api_logs = [r for r in api_logs if r.get("service") == "api"]
    assert api_logs
    for rec in api_logs:
        assert rec["correlation_id"] == "req-abcd1234"
        assert {"user_id_hash", "session_id", "feature", "model", "env"} <= rec.keys()