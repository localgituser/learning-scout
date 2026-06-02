from __future__ import annotations
import asyncio
import json
import re
from typing import Any
import anthropic
from anthropic import AsyncAnthropic
from learning_scout.models import AppConfig, LearningItem

SYSTEM_PROMPT = """\
You are a learning opportunity researcher. Given a search topic and a user profile,
find relevant learning and networking opportunities across ALL of these types:

- In-person conferences, summits, and workshops
- Online/virtual conferences and summits (e.g. Snowflake Summit virtual, dbt Coalesce, AWS re:Invent livestream)
- Vendor-run events and community days (Salesforce, Google, Microsoft, Databricks, Snowflake, etc.)
- Meetup groups and local community events (Meetup.com groups, user groups, guild nights)
- Self-paced online courses and video series
- Cohort-based programs (Reforge, On Deck, Maven, etc.)
- Books, newsletters, and reference resources

Search broadly — do not limit results to only large, well-known conferences.
Include regional meetup groups, online-only events, and vendor community events.

Return ONLY a JSON array (no markdown, no preamble) of objects with these fields:
- title (string, required)
- url (string, required)
- description (string, required)
- category (string, required: one of in_person_events | online_events | meetups | online_courses | cohort_programs | books_or_resources | wildcard)
  - in_person_events: physical conferences, workshops, summits
  - online_events: virtual conferences, webinar series, livestreamed summits
  - meetups: Meetup.com groups, user groups, community guild nights (recurring or one-off)
  - online_courses: self-paced courses, video series, tutorials
  - cohort_programs: structured cohort-based programs with a fixed schedule
  - books_or_resources: books, newsletters, reference guides
  - wildcard: anything high-value that doesn't fit above
- cost_aud (number or null)
- deadline (ISO date string or null — registration/early bird deadline)
- event_date (ISO date string or null — when event starts)
- raw_score (number 1–10 — relevance to the user profile)

Return an empty array [] if nothing relevant is found. Do not include markdown code blocks.\
"""


def _build_user_prompt(topic: str, config: AppConfig) -> str:
    p = config.profile
    return (
        f"Search topic: {topic}\n\n"
        f"User profile:\n"
        f"- Current role: {p.current_role}\n"
        f"- Target role: {p.target_role}\n"
        f"- Career stage: {p.career_stage}\n"
        f"- Years experience: {p.years_experience}\n"
        f"- Topics of interest: {', '.join(p.topics_of_interest)}\n"
        f"- Budget: AUD {config.budget_aud or 'not specified'}\n"
        f"- Format preference: {', '.join(config.format_preference)}\n"
        f"- Regions: {', '.join(config.regions)}\n"
        f"- Commitment: {', '.join(config.commitment)}\n\n"
        f"Find up to {config.search.results_per_topic} relevant opportunities. "
        f"Only return items with a raw_score >= {config.search.min_relevance_score}."
    )


def parse_items_from_response(text: str) -> list[LearningItem]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        raw_list: list[Any] = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    items: list[LearningItem] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(LearningItem.model_validate(raw))
        except Exception:
            continue
    return items


async def search_topic(
    topic: str,
    config: AppConfig,
    client: AsyncAnthropic,
) -> list[LearningItem]:
    print(f"  → searching: {topic}", flush=True)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(topic, config)}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
    )

    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    combined = "\n".join(text_parts)
    items = parse_items_from_response(combined)
    print(f"  ✓ done: {topic} ({len(items)} items)", flush=True)
    return items


async def run_search(
    config: AppConfig,
    client: AsyncAnthropic | None = None,
) -> list[LearningItem]:
    if client is None:
        client = AsyncAnthropic()

    topics = config.profile.topics_of_interest[: config.search.topics_per_run]
    print(f"Searching {len(topics)} topics (3 concurrent)...", flush=True)
    sem = asyncio.Semaphore(3)

    async def _bounded(topic: str) -> list[LearningItem]:
        async with sem:
            return await search_topic(topic, config, client)

    tasks = [_bounded(t) for t in topics]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    all_items: list[LearningItem] = []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                all_items.append(item)

    return all_items
