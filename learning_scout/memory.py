from __future__ import annotations
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from learning_scout.models import LearningItem, SeenItem, ItemStatus
from learning_scout.state_serde import deserialize_state, serialize_state

# SEEN_FILE env var allows each deployment context (Actions, Railway, local)
# to set an explicit absolute path; otherwise fall back to cwd/seen.json.
SEEN_PATH = Path(os.environ.get("SEEN_FILE", "seen.json"))


def compute_hash(title: str, url: str) -> str:
    """Delegate to the canonical implementation on LearningItem."""
    from learning_scout.models import _hash_key
    return _hash_key(title, url)


def load_seen(path: Path = SEEN_PATH) -> tuple[dict[str, SeenItem], list[str]]:
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}, []
    return deserialize_state(data)


def save_seen(seen: dict[str, SeenItem], blocked: list[str], path: Path = SEEN_PATH) -> None:
    payload = json.dumps(serialize_state(seen, blocked), indent=2, default=str)
    # Atomic write: unique tmp in same directory, then rename to avoid partial writes
    fd, tmp_str = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, payload.encode())
        os.close(fd)
        Path(tmp_str).replace(path)
    except Exception:
        os.close(fd)
        Path(tmp_str).unlink(missing_ok=True)
        raise


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
    import re
    patterns = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in blocked]
    return [
        i for i in items
        if not any(p.search(i.title) or p.search(i.description) for p in patterns)
    ]


def add_blocked_keyword(blocked: list[str], keyword: str) -> list[str]:
    kw = keyword.lower().strip()
    if kw not in blocked:
        return [*blocked, kw]
    return blocked
