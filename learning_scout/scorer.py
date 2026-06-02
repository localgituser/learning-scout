from __future__ import annotations
from datetime import date, datetime, timezone
from learning_scout.models import AppConfig, DigestConfig, LearningItem, Digest


def compute_timeliness_modifier(item: LearningItem, as_of: date | None = None) -> float:
    today = as_of or date.today()

    if item.deadline is not None:
        days = (item.deadline - today).days
        if days <= 14:
            return 2.0
        if days <= 30:
            return 1.0

    if item.event_date is not None:
        days_to_event = (item.event_date - today).days
        if days_to_event > 365:
            return -1.0

    return 0.0


def filter_by_min_score(items: list[LearningItem], min_score: float) -> list[LearningItem]:
    return [i for i in items if i.raw_score >= min_score]


def apply_scores(items: list[LearningItem], config: AppConfig) -> list[LearningItem]:
    scored = []
    for item in items:
        mod = compute_timeliness_modifier(item)
        scored.append(item.model_copy(update={
            "timeliness_modifier": mod,
            "final_score": item.raw_score + mod,
        }))
    return sorted(scored, key=lambda x: x.final_score, reverse=True)


def _filter_budget(items: list[LearningItem], budget_aud: float | None) -> list[LearningItem]:
    if budget_aud is None:
        return items
    return [i for i in items if i.cost_aud is None or i.cost_aud <= budget_aud]


def enforce_slots(items: list[LearningItem], digest_config: DigestConfig) -> list[LearningItem]:
    slots = digest_config.categories.as_dict()
    remaining = dict(slots)
    result: list[LearningItem] = []
    for item in items:
        cat = item.category
        if remaining.get(cat, 0) > 0:
            result.append(item)
            remaining[cat] -= 1
    return result


def build_digest(items: list[LearningItem], config: AppConfig) -> Digest:
    filtered = _filter_budget(items, config.budget_aud)
    filtered = filter_by_min_score(filtered, config.search.min_relevance_score)
    scored = apply_scores(filtered, config)

    if config.digest.enforce_category_mix:
        selected = enforce_slots(scored, config.digest)
    else:
        selected = scored[: config.search.digest_size]

    return Digest(generated_at=datetime.now(timezone.utc), items=selected)
