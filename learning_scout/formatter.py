from __future__ import annotations
from learning_scout.models import ItemCategory, LearningItem, SeenItem

_CATEGORY_EMOJI: dict[str, str] = {
    "in_person_events": "🎯",
    "online_courses": "📚",
    "cohort_programs": "🤝",
    "books_or_resources": "📖",
    "wildcard": "⭐",
}


def category_emoji(category: ItemCategory | str) -> str:
    return _CATEGORY_EMOJI.get(category, "📌")


def _cost_text(item: LearningItem) -> str:
    if item.cost_aud is None:
        return "Cost: TBA"
    if item.cost_aud == 0:
        return "Free"
    return f"~${item.cost_aud:,.0f} AUD"


def _deadline_text(item: LearningItem) -> str:
    if item.deadline:
        return f"⚠️ Early bird deadline: {item.deadline}"
    return ""


def format_item_html(item: LearningItem, index: int) -> str:
    emoji = category_emoji(item.category)
    lines = [
        f"{emoji} <b>{item.title}</b>",
        f"{item.description}",
        f"{_cost_text(item)}",
    ]
    if item.event_date:
        lines.append(f"📅 {item.event_date}")
    deadline = _deadline_text(item)
    if deadline:
        lines.append(deadline)
    lines.append(f'<a href="{item.url}">More info</a>')
    return "\n".join(lines)


def format_digest_intro(total: int) -> str:
    return f"🔍 <b>Your weekly learning digest</b> — {total} opportunities this week."


def format_saved_list(items: list[SeenItem]) -> str:
    saved = [i for i in items if i.status == "saved"]
    if not saved:
        return "You have no saved items yet. Tap 💾 Save on any digest item to save it."
    lines = ["<b>💾 Your saved items:</b>", ""]
    for i, item in enumerate(saved[-20:], 1):  # cap at 20 to avoid message limit
        lines.append(f"{i}. <a href=\"{item.url}\">{item.title}</a> ({item.first_seen})")
    return "\n".join(lines)


def format_blocked_list(blocked: list[str]) -> str:
    if not blocked:
        return "No blocked keywords."
    return "🚫 Blocked keywords:\n" + ", ".join(blocked)
