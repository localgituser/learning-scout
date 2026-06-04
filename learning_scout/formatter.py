from __future__ import annotations
import html
import re
from datetime import date
from learning_scout.models import ItemCategory, LearningItem, SeenItem

_CATEGORY_EMOJI: dict[str, str] = {
    "in_person_events": "🎯",
    "online_events": "🖥️",
    "webinars": "📡",
    "meetups": "👥",
    "courses": "📚",
}

_DEADLINE_LABEL: dict[str, str] = {
    "early_bird": "⏰ Early bird closes",
    "cfp": "📝 CFP closes",
    "scholarship": "🎓 Scholarship deadline",
    "enrolment": "📋 Enrolment closes",
    "certification": "🏆 Certification window closes",
    "mentorship": "🤝 Mentorship application closes",
    "registration": "⚠️ Registration closes",
}

_SAFE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def category_emoji(category: ItemCategory | str) -> str:
    return _CATEGORY_EMOJI.get(category, "📌")


def _safe_url(url: str) -> str:
    """Return url if it's http(s), otherwise a placeholder to prevent href injection."""
    return url if _SAFE_URL_RE.match(url) else "#"


def _cost_text(item: LearningItem) -> str:
    if item.cost_aud is None:
        return "Cost: TBA"
    if item.cost_aud == 0:
        return "Free"
    return f"~${item.cost_aud:,.0f} AUD"


def _deadline_text(item: LearningItem, today: date | None = None) -> str:
    if not item.deadline:
        return ""
    today = today or date.today()
    if item.deadline < today:
        return ""
    label = _DEADLINE_LABEL.get(item.deadline_type or "", "⚠️ Deadline")
    return f"{label}: {item.deadline}"


def format_item_html(item: LearningItem, index: int) -> str:
    emoji = category_emoji(item.category)
    title = html.escape(item.title)
    description = html.escape(item.description)
    url = html.escape(_safe_url(item.url))
    lines = [
        f"{emoji} <b>{title}</b>",
        description,
        _cost_text(item),
    ]
    if item.event_date:
        lines.append(f"📅 {item.event_date}")
    deadline = _deadline_text(item)
    if deadline:
        lines.append(deadline)
    lines.append(f'<a href="{url}">More info</a>')
    return "\n".join(lines)


def format_digest_intro(total: int) -> str:
    return f"🔍 <b>Your weekly learning digest</b> — {total} opportunities this week."


def format_saved_list(items: list[SeenItem]) -> str:
    saved = [i for i in items if i.status == "saved"]
    if not saved:
        return "You have no saved items yet. Tap 💾 Save on any digest item to save it."
    lines = ["<b>💾 Your saved items:</b>", ""]
    for i, item in enumerate(saved[-20:], 1):  # cap at 20 to stay under Telegram's 4096-char limit
        url = html.escape(_safe_url(item.url))
        title = html.escape(item.title)
        lines.append(f'{i}. <a href="{url}">{title}</a> ({item.first_seen})')
    return "\n".join(lines)


def format_blocked_list(blocked: list[str]) -> str:
    if not blocked:
        return "No blocked keywords."
    return "🚫 Blocked keywords:\n" + ", ".join(html.escape(kw) for kw in blocked)
