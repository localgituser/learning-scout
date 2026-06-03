"""Shared helpers for serializing/deserializing the seen-state JSON structure."""
from __future__ import annotations
from learning_scout.models import SeenItem


def serialize_state(seen: dict[str, SeenItem], blocked: list[str]) -> dict:
    return {
        "items": [item.model_dump(mode="json") for item in seen.values()],
        "blocked_keywords": blocked,
    }


def deserialize_state(data: dict) -> tuple[dict[str, SeenItem], list[str]]:
    items: dict[str, SeenItem] = {}
    for entry in data.get("items", []):
        item = SeenItem.model_validate(entry)
        items[item.id] = item
    blocked: list[str] = [kw.lower() for kw in data.get("blocked_keywords", [])]
    return items, blocked
