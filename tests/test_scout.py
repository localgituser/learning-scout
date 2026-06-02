import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from learning_scout.models import AppConfig, LearningItem
from learning_scout.scout import search_topic, run_search, parse_items_from_response


MOCK_RESPONSE_TEXT = """
[
  {
    "title": "Mind the Product Leadership Summit",
    "url": "https://example.com/mtp",
    "description": "Leadership summit for senior PMs in London.",
    "category": "in_person_events",
    "cost_aud": 1800.0,
    "deadline": "2026-07-15",
    "event_date": "2026-10-12",
    "raw_score": 8.5
  },
  {
    "title": "Reforge: Product Strategy",
    "url": "https://reforge.com/product-strategy",
    "description": "Cohort program on strategic thinking.",
    "category": "cohort_programs",
    "cost_aud": 2500.0,
    "raw_score": 7.0
  }
]
"""

MOCK_RESPONSE_GARBAGE = "Here are some results: blah blah not JSON"

MOCK_RESPONSE_PARTIAL = """
Some text before
[
  {
    "title": "Good Item",
    "url": "https://good.com",
    "description": "Great course",
    "category": "online_courses",
    "raw_score": 7.0
  }
]
Some text after
"""


def test_parse_items_from_response_valid():
    items = parse_items_from_response(MOCK_RESPONSE_TEXT)
    assert len(items) == 2
    assert items[0].title == "Mind the Product Leadership Summit"
    assert items[0].category == "in_person_events"
    assert items[1].raw_score == 7.0


def test_parse_items_from_response_with_surrounding_text():
    items = parse_items_from_response(MOCK_RESPONSE_PARTIAL)
    assert len(items) == 1
    assert items[0].title == "Good Item"


def test_parse_items_from_response_garbage_returns_empty():
    items = parse_items_from_response(MOCK_RESPONSE_GARBAGE)
    assert items == []


def test_parse_items_skips_invalid_items():
    text = '[{"title": "OK", "url": "https://ok.com", "description": "d", "category": "wildcard", "raw_score": 6.0}, {"bad": "item"}]'
    items = parse_items_from_response(text)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_search_topic_returns_items(sample_config):
    mock_client = AsyncMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text=MOCK_RESPONSE_TEXT)]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    items = await search_topic("product strategy conferences", sample_config, mock_client)
    assert len(items) == 2
    assert all(isinstance(i, LearningItem) for i in items)


@pytest.mark.asyncio
async def test_search_topic_handles_empty_response(sample_config):
    mock_client = AsyncMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text="[]")]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    items = await search_topic("obscure topic", sample_config, mock_client)
    assert items == []


@pytest.mark.asyncio
async def test_run_search_aggregates_topics(sample_config):
    mock_client = AsyncMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text=MOCK_RESPONSE_TEXT)]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    # sample_config has 2 topics
    with patch("learning_scout.scout.AsyncAnthropic", return_value=mock_client):
        items = await run_search(sample_config, client=mock_client)

    # 2 topics × 2 items each = 4 total (deduped if same)
    assert len(items) >= 2
    assert all(isinstance(i, LearningItem) for i in items)


@pytest.mark.asyncio
async def test_run_search_deduplicates_by_url(sample_config):
    mock_client = AsyncMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text=MOCK_RESPONSE_TEXT)]
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    items = await run_search(sample_config, client=mock_client)
    urls = [i.url for i in items]
    assert len(urls) == len(set(urls))
