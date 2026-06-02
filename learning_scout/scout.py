from __future__ import annotations
import asyncio
import json
from typing import Any
import anthropic
from anthropic import AsyncAnthropic
from learning_scout.models import AppConfig, LearningItem

SYSTEM_PROMPT = """\
You are a learning opportunity researcher. Given a search topic and a user profile,
find relevant learning and networking opportunities across ALL of these types:

- In-person conferences, summits, and workshops
- Online/virtual conferences and summits (e.g. Snowflake Summit virtual, dbt Coalesce, AWS re:Invent livestream)
- Live webinars and expert talks (vendor-run, community-run, or standalone — check upcoming schedules)
- Vendor-run events and community days (Salesforce, Google, Microsoft, Databricks, Snowflake, etc.)
- Meetup groups and local community events (Meetup.com groups, user groups, guild nights)
- Community Slack workspaces and Discord servers (dbt Slack, Locally Optimistic, Data Eng Discord, etc.)
- Self-paced online courses and video series (YouTube playlists, MOOCs, free tutorials)
- Cohort-based programs (Reforge, On Deck, Maven, etc.)
- Podcasts — specific recent episodes (published within the last 7 days) or evergreen series highly relevant to the topic
- High-quality articles, blog posts, or essay series published within the last 7 days
- Newsletters that consistently cover this topic at a senior/strategic level
- Open-source projects or GitHub repos worth contributing to or studying
- Books, reference guides, and frameworks

Search broadly — do not limit results to only large, well-known conferences.
Think creatively: a brilliant free webinar recording, a niche Slack community, a must-read article series,
or a practitioner podcast episode can be more valuable than an expensive conference.

IMPORTANT — recency rules for articles, blog posts, and podcast episodes:
- Articles, blog posts, and essay series MUST have been published within the last 7 days. Do not return older content.
- Podcast episodes MUST have been published within the last 7 days. You may include the parent podcast series as evergreen if directly relevant, but prefer the latest episode.
- For YouTube videos, prefer content published within the last 7 days; only include older videos if they are landmark/seminal content with no recent equivalent.
- Newsletters, courses, books, communities, and events are not subject to the 7-day rule — include them based on relevance.

IMPORTANT — quality bar for articles, blog posts, and podcasts:
- Only include content from reputable, well-known sources: established industry publications (Harvard Business Review, MIT Technology Review, ACM, IEEE, InfoQ, The Register, Wired), respected practitioner blogs (Martin Fowler, Lenny's Newsletter, Stratechery, dbt Blog, Databricks Blog, AWS Blog, Google Cloud Blog), or recognised domain experts with a clear professional track record.
- For podcasts: only well-established shows with a named host and consistent audience (e.g. Lenny's Podcast, Data Engineering Podcast, The TWIML AI Podcast, Acquired, Software Engineering Daily).
- Do NOT return: link aggregators (Hacker News, Reddit, Medium tag pages, Substack discovery pages), SEO-farm articles, listicles from unknown blogs, AI-generated content farms, or any page whose primary purpose is aggregating links rather than original content.
- If you are not confident the source is reputable, omit the item rather than including it.

IMPORTANT — cost_aud field rules:
- Free items (no cost at all): set cost_aud to 0 (not null)
- Items with a known cost: set cost_aud to the numeric AUD value
- Items where cost is genuinely unknown (TBA, not published yet): set cost_aud to null
- If the user's budget is AUD 0, ONLY return free items (cost_aud: 0). Do not return paid or unknown-cost items.

Return ONLY a JSON array (no markdown, no preamble) of objects with these fields:
- title (string, required)
- url (string, required)
- description (string, required)
- category (string, required: one of in_person_events | online_events | meetups | online_courses | cohort_programs | books_or_resources | wildcard)
  - in_person_events: physical conferences, workshops, summits
  - online_events: virtual conferences, webinar series, livestreamed summits, live webinars
  - meetups: Meetup.com groups, user groups, community guild nights, Slack/Discord communities
  - online_courses: self-paced courses, video series, YouTube playlists, tutorials
  - cohort_programs: structured cohort-based programs with a fixed schedule
  - books_or_resources: books, newsletters, articles, blog series, podcasts, reference guides
  - wildcard: anything high-value that doesn't fit above (open-source projects, frameworks, etc.)
- cost_aud (number or null — use 0 for free items, a number for known costs, null only if truly unknown)
- deadline (ISO date string or null — registration/early bird deadline)
- event_date (ISO date string or null — when event starts, or null for evergreen resources)
- raw_score (number 1–10 — relevance to the user profile)

Return an empty array [] if nothing relevant is found. Do not include markdown code blocks.\
"""


def _build_user_prompt(topic: str, config: AppConfig) -> str:
    from datetime import date
    today = date.today().isoformat()
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
) -> list[LearningItem]:
    print(f"  → searching: {topic}", flush=True)
    response = await client.messages.create(
        model=config.search.model,
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
    concurrency = config.search.max_concurrent_searches
    print(f"Searching {len(topics)} topics ({concurrency} concurrent)...", flush=True)
    sem = asyncio.Semaphore(concurrency)

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
