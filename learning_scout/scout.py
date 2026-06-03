from __future__ import annotations
import asyncio
import json
from typing import Any
import anthropic
from anthropic import AsyncAnthropic
from learning_scout.models import AppConfig, LearningItem

SYSTEM_PROMPT = """\
You are a learning opportunity researcher. Given a search topic and a user profile,
find relevant learning and networking opportunities across these types:

- In-person conferences, summits, and workshops
- Online/virtual conferences, webinars, and livestreamed events (e.g. Snowflake Summit virtual, dbt Coalesce, AWS re:Invent livestream)
- Meetup groups, community events, Slack workspaces, and Discord servers (Meetup.com groups, user groups, dbt Slack, Locally Optimistic, etc.)
- Self-paced courses, video series, and tutorials (MOOCs, YouTube playlists, free tutorials)
- Cohort-based programs and structured learning (Reforge, On Deck, Maven, etc.)
- Professional certifications with open enrolment or upcoming exam windows

Do NOT include: articles, blog posts, newsletters, podcasts, books, open-source projects, or GitHub repos.

IMPORTANT — actionable dates: For every item, check whether any of the following time-sensitive windows exist and are still open (i.e. the date has not yet passed). If found, populate the deadline and deadline_type fields:
- early_bird: discounted pricing window closes soon
- cfp: call for papers / speaker proposals deadline
- scholarship: scholarship or fee-waiver application deadline
- enrolment: cohort enrolment or waitlist closes
- certification: certification exam registration or testing window closes
- mentorship: mentorship program application deadline
- registration: general registration or ticket-sale deadline

Only set deadline/deadline_type if the date is in the future relative to today's date. Do not surface expired deadlines.

IMPORTANT — cost_aud field rules:
- Free items (no cost at all): set cost_aud to 0 (not null). Only set 0 when the item is EXPLICITLY advertised as free.
- Items with a known cost: set cost_aud to the numeric AUD value
- Items where cost is genuinely unknown (TBA, not published yet): set cost_aud to null
- If the user's budget is AUD 0, ONLY return items you have VERIFIED are genuinely free. Do NOT set cost_aud to 0 to make a paid or unknown-cost item pass this filter. If pricing is TBA, not yet published, or you are unsure whether it is free, EXCLUDE the item entirely.

IMPORTANT — url field rules:
- The url must be an actual URL you found via web search. Do NOT construct or guess URLs.
- If you cannot find a verified direct URL for an item, exclude it.

Return ONLY a JSON array (no markdown, no preamble) of objects with these fields:
- title (string, required)
- url (string, required)
- description (string, required)
- category (string, required: one of in_person_events | online_events | meetups | courses)
  - in_person_events: physical conferences, workshops, summits
  - online_events: virtual conferences, webinar series, livestreamed summits, live webinars
  - meetups: Meetup.com groups, user groups, community guild nights, Slack/Discord communities
  - courses: self-paced courses, cohort programs, certifications, structured learning
- cost_aud (number or null — use 0 for free items, a number for known costs, null only if truly unknown)
- deadline (ISO date string or null — only if a future actionable deadline exists)
- deadline_type (string or null — one of early_bird | cfp | scholarship | enrolment | certification | mentorship | registration; required if deadline is set)
- event_date (ISO date string or null — when event starts, or null for evergreen resources)
- raw_score (number 1–10 — relevance to the user profile)

Return an empty array [] if nothing relevant is found. Do not include markdown code blocks.\
"""


def _build_user_prompt(topic: str, config: AppConfig, as_of: "date | None" = None) -> str:
    from datetime import date as _date
    today = (as_of or _date.today()).isoformat()
    p = config.profile
    return (
        f"Today's date: {today}\n"
        f"Search topic: {topic}\n\n"
        f"User profile:\n"
        f"- Current role: {p.current_role}\n"
        f"- Target role: {p.target_role}\n"
        f"- Career stage: {p.career_stage}\n"
        f"- Years experience: {p.years_experience}\n"
        f"- Topics of interest: {', '.join(p.topics_of_interest)}\n"
        f"- Budget: {'AUD 0 — FREE ITEMS ONLY, do not return paid or unknown-cost items' if config.budget_aud == 0 else f'AUD {config.budget_aud}' if config.budget_aud is not None else 'not specified'}\n"
        f"- Format preference: {', '.join(config.format_preference)}\n"
        f"- Regions: {', '.join(config.regions)}\n"
        f"- Commitment: {', '.join(config.commitment)}\n\n"
        f"Find up to {config.search.results_per_topic} relevant opportunities. "
        f"Only return items with a raw_score >= {config.search.min_relevance_score}."
    )


def parse_items_from_response(text: str) -> list[LearningItem]:
    # Try the full text first (model obeyed instructions perfectly)
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            raw_list: list[Any] = json.loads(stripped)
            return _validate_items(raw_list)
        except (json.JSONDecodeError, ValueError):
            pass

    # Fall back: walk through every top-level [...] block and return the first
    # that parses as a JSON array — stray [note] style text won't corrupt this.
    pos = 0
    while True:
        start = text.find("[", pos)
        if start == -1:
            return []
        depth = 0
        end = start
        for i, ch in enumerate(text[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        candidate = text[start : end + 1]
        try:
            raw_list = json.loads(candidate)
            items = _validate_items(raw_list)
            if items:
                return items
        except (json.JSONDecodeError, ValueError):
            pass
        pos = end + 1


def _validate_items(raw_list: Any) -> list[LearningItem]:
    if not isinstance(raw_list, list):
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
    as_of: "date | None" = None,
) -> list[LearningItem]:
    print(f"  → searching: {topic}", flush=True)
    response = await client.messages.create(
        model=config.search.model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(topic, config, as_of=as_of)}],
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
    as_of: "date | None" = None,
) -> list[LearningItem]:
    if client is None:
        client = AsyncAnthropic(
            default_headers={"anthropic-beta": "web-search-2025-03-05"},
        )

    topics = config.profile.topics_of_interest[: config.search.topics_per_run]
    concurrency = config.search.max_concurrent_searches
    print(f"Searching {len(topics)} topics ({concurrency} concurrent)...", flush=True)
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(topic: str) -> list[LearningItem]:
        async with sem:
            return await search_topic(topic, config, client, as_of=as_of)

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
