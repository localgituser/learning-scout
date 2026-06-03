import json
import pytest
from datetime import date
from pathlib import Path
from learning_scout.memory import (
    compute_hash,
    load_seen,
    save_seen,
    is_seen,
    mark_seen,
    filter_unseen,
    add_blocked_keyword,
)
from learning_scout.models import LearningItem, SeenItem


@pytest.fixture
def item():
    return LearningItem(
        title="Reforge: Product Strategy",
        url="https://reforge.com/product-strategy",
        description="Cohort program",
        category="courses",
    )


@pytest.fixture
def seen_path(tmp_path):
    return tmp_path / "seen.json"


def test_compute_hash_is_deterministic(item):
    h1 = compute_hash(item.title, item.url)
    h2 = compute_hash(item.title, item.url)
    assert h1 == h2


def test_compute_hash_differs_for_different_inputs(item):
    h1 = compute_hash(item.title, item.url)
    h2 = compute_hash(item.title, "https://other.com")
    assert h1 != h2


def test_compute_hash_normalises_case(item):
    h1 = compute_hash("Reforge: Product Strategy", item.url)
    h2 = compute_hash("reforge: product strategy", item.url)
    assert h1 == h2


def test_load_seen_empty_file_returns_empty_dict(seen_path):
    seen_path.write_text(json.dumps({"items": [], "blocked_keywords": []}))
    seen, blocked = load_seen(seen_path)
    assert seen == {}
    assert blocked == []


def test_load_seen_missing_file_returns_empty(seen_path):
    seen, blocked = load_seen(seen_path)
    assert seen == {}
    assert blocked == []


def test_save_and_reload(seen_path, item):
    seen, blocked = load_seen(seen_path)
    seen = mark_seen(seen, item, "saved", date(2026, 6, 2))
    save_seen(seen, blocked, seen_path)
    reloaded, _ = load_seen(seen_path)
    h = compute_hash(item.title, item.url)
    assert h in reloaded
    assert reloaded[h].status == "saved"


def test_is_seen_false_for_new_item(item):
    h = compute_hash(item.title, item.url)
    assert not is_seen(h, {})


def test_is_seen_true_after_mark(item):
    seen, _ = load_seen(Path("/nonexistent"))
    seen = mark_seen(seen, item, "skipped", date(2026, 6, 2))
    h = compute_hash(item.title, item.url)
    assert is_seen(h, seen)


def test_filter_unseen_removes_seen_items(item):
    seen = mark_seen({}, item, "skipped", date(2026, 6, 2))
    new_item = LearningItem(
        title="New Conference", url="https://new.com", description="Fresh", category="in_person_events"
    )
    result = filter_unseen([item, new_item], seen)
    assert len(result) == 1
    assert result[0].title == "New Conference"


def test_blocked_keywords_roundtrip(seen_path):
    seen, blocked = load_seen(seen_path)
    blocked = add_blocked_keyword(blocked, "MBA")
    save_seen(seen, blocked, seen_path)
    _, reloaded = load_seen(seen_path)
    assert "mba" in reloaded


