"""Cloudflare KV state client — read/write seen state via the Worker's /state API."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import date

import httpx

from learning_scout.models import SeenItem


@dataclass
class CFStateConfig:
    worker_url: str   # e.g. https://learning-scout-bot.username.workers.dev
    api_secret: str


class CFStateError(Exception):
    pass


def _serialize(seen: dict[str, SeenItem], blocked: list[str]) -> str:
    payload = {
        "items": [item.model_dump(mode="json") for item in seen.values()],
        "blocked_keywords": blocked,
    }
    return json.dumps(payload, default=str)


def _deserialize(raw: str) -> tuple[dict[str, SeenItem], list[str]]:
    data = json.loads(raw)
    items: dict[str, SeenItem] = {}
    for entry in data.get("items", []):
        item = SeenItem.model_validate(entry)
        items[item.id] = item
    blocked: list[str] = [kw.lower() for kw in data.get("blocked_keywords", [])]
    return items, blocked


async def fetch_state(config: CFStateConfig) -> tuple[dict[str, SeenItem], list[str]]:
    url = config.worker_url.rstrip("/") + "/state"
    headers = {"X-API-Secret": config.api_secret}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 200:
        return _deserialize(resp.text)
    if resp.status_code == 404:
        return {}, []
    raise CFStateError(f"Failed to fetch state: HTTP {resp.status_code}")


async def push_state(
    seen: dict[str, SeenItem],
    blocked: list[str],
    config: CFStateConfig,
) -> None:
    url = config.worker_url.rstrip("/") + "/state"
    headers = {
        "X-API-Secret": config.api_secret,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, content=_serialize(seen, blocked))
    if resp.status_code not in (200, 201):
        raise CFStateError(f"Failed to push state: HTTP {resp.status_code}")
