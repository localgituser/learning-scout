"""Cloudflare KV state client — read/write seen state via the Worker's /state API."""
from __future__ import annotations
import json
from dataclasses import dataclass

import httpx

from learning_scout.models import SeenItem
from learning_scout.state_serde import deserialize_state, serialize_state


@dataclass
class CFStateConfig:
    worker_url: str   # e.g. https://learning-scout-bot.username.workers.dev
    api_secret: str


class CFStateError(Exception):
    pass


def _serialize(seen: dict[str, SeenItem], blocked: list[str]) -> str:
    return json.dumps(serialize_state(seen, blocked), default=str)


def _deserialize(raw: str) -> tuple[dict[str, SeenItem], list[str]]:
    return deserialize_state(json.loads(raw))


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
