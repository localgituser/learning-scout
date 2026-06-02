from __future__ import annotations
import hashlib
import json
from datetime import date
from pathlib import Path
from learning_scout.models import LearningItem, SeenItem, ItemStatus

SEEN_PATH = Path("seen.json")


def compute_hash(title: str, url: str) -> str:
    key = f"{title.lower().strip()}|{url.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()


def load_seen(path: Path = SEEN_PATH) -> tuple[dict[str, SeenItem], list[str]]:
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}, []

    items: dict[str, SeenItem] = {}
    for raw in data.get("items", []):
        item = SeenItem.model_validate(raw)
        items[item.id] = item

    blocked: list[str] = [kw.lower() for kw in data.get("blocked_keywords", [])]
    return items, blocked


def save_seen(seen: dict[str, SeenItem], blocked: list[str], path: Path = SEEN_PATH) -> None:
    payload = {
        "items": [item.model_dump(mode="json") for item in seen.values()],
        "blocked_keywords": blocked,
    }
    # Atomic write: tmp file then rename to avoid partial writes
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


def is_seen(item_hash: str, seen: dict[str, SeenItem]) -> bool:
    return item_hash in seen


def mark_seen(
    seen: dict[str, SeenItem],
    item: LearningItem,
    status: ItemStatus,
    digest_date: date,
) -> dict[str, SeenItem]:
    h = compute_hash(item.title, item.url)
    seen[h] = SeenItem(
        id=h,
        title=item.title,
        url=item.url,
        first_seen=digest_date,
        status=status,
    )
    return seen


def filter_unseen(items: list[LearningItem], seen: dict[str, SeenItem]) -> list[LearningItem]:
    return [i for i in items if not is_seen(compute_hash(i.title, i.url), seen)]


def filter_blocked(items: list[LearningItem], blocked: list[str]) -> list[LearningItem]:
    if not blocked:
        return items
    return [
        i for i in items
        if not any(kw in i.title.lower() or kw in i.description.lower() for kw in blocked)
    ]


def get_blocked_keywords(blocked: list[str]) -> list[str]:
    return [kw.lower() for kw in blocked]


def add_blocked_keyword(blocked: list[str], keyword: str) -> list[str]:
    kw = keyword.lower().strip()
    if kw not in blocked:
        return [*blocked, kw]
    return blocked
