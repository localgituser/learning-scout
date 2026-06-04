import pytest
from datetime import date, datetime, timezone
from learning_scout.models import LearningItem, Digest, SeenItem
from learning_scout.formatter import (
    format_item_html,
    format_digest_intro,
    format_saved_list,
    category_emoji,
)


@pytest.fixture
def item_with_deadline():
    return LearningItem(
        title="Mind the Product Summit",
        url="https://example.com/mtp",
        description="Leadership summit for senior PMs.",
        category="in_person_events",
        cost_aud=1800.0,
        deadline=date(2026, 7, 15),
        event_date=date(2026, 10, 12),
        raw_score=8.5,
        final_score=9.5,
    )


@pytest.fixture
def item_no_cost():
    return LearningItem(
        title="Free Webinar",
        url="https://example.com/webinar",
        description="Free online event.",
        category="courses",
        raw_score=6.5,
        final_score=6.5,
    )


def test_format_item_html_contains_title(item_with_deadline):
    html = format_item_html(item_with_deadline, index=1)
    assert "Mind the Product Summit" in html


def test_format_item_html_contains_url(item_with_deadline):
    html = format_item_html(item_with_deadline, index=1)
    assert "https://example.com/mtp" in html


def test_format_item_html_shows_cost(item_with_deadline):
    html = format_item_html(item_with_deadline, index=1)
    assert "1800" in html or "AUD" in html


def test_format_item_html_shows_deadline(item_with_deadline):
    html = format_item_html(item_with_deadline, index=1)
    assert "2026-07-15" in html or "Jul" in html or "deadline" in html.lower() or "early bird" in html.lower()


def test_format_item_html_no_cost_shows_free_or_unknown(item_no_cost):
    html = format_item_html(item_no_cost, index=1)
    assert "free" in html.lower() or "unknown" in html.lower() or "cost" in html.lower() or "tba" in html.lower()


def test_format_digest_intro():
    intro = format_digest_intro(total=8)
    assert "8" in intro


def test_format_saved_list_empty():
    text = format_saved_list([])
    assert "nothing" in text.lower() or "empty" in text.lower() or "no saved" in text.lower()


def test_format_saved_list_with_items():
    items = [
        SeenItem(id="abc", title="Conf A", url="https://a.com", first_seen=date(2026, 6, 2), status="saved"),
        SeenItem(id="def", title="Course B", url="https://b.com", first_seen=date(2026, 6, 2), status="saved"),
    ]
    text = format_saved_list(items)
    assert "Conf A" in text
    assert "Course B" in text


def test_category_emoji_covers_all_categories():
    from learning_scout.models import ItemCategory
    categories: list[ItemCategory] = [
        "in_person_events", "online_events", "webinars", "meetups", "courses",
    ]
    for cat in categories:
        emoji = category_emoji(cat)
        assert isinstance(emoji, str) and len(emoji) > 0
        assert emoji != "📌", f"category '{cat}' is missing from _CATEGORY_EMOJI"
