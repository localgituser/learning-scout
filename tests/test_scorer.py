import pytest
from datetime import date
from freezegun import freeze_time
from learning_scout.models import LearningItem, AppConfig, CategorySlots
from learning_scout.scorer import (
    compute_timeliness_modifier,
    apply_scores,
    enforce_slots,
    build_digest,
    filter_by_min_score,
)


def make_item(
    title="Conference",
    url="https://example.com",
    category="in_person_events",
    raw_score=7.0,
    deadline=None,
    event_date=None,
    cost_aud=None,
) -> LearningItem:
    return LearningItem(
        title=title,
        url=url,
        description="desc",
        category=category,
        raw_score=raw_score,
        deadline=deadline,
        event_date=event_date,
        cost_aud=cost_aud,
    )


# --- timeliness modifier ---

@freeze_time("2026-06-02")
def test_early_bird_within_14_days():
    item = make_item(deadline=date(2026, 6, 12))
    assert compute_timeliness_modifier(item) == 2.0


@freeze_time("2026-06-02")
def test_early_bird_within_30_days():
    item = make_item(deadline=date(2026, 6, 25))
    assert compute_timeliness_modifier(item) == 1.0


@freeze_time("2026-06-02")
def test_no_modifier_for_distant_deadline():
    item = make_item(deadline=date(2026, 8, 1))
    assert compute_timeliness_modifier(item) == 0.0


@freeze_time("2026-06-02")
def test_negative_modifier_for_far_future_event():
    item = make_item(event_date=date(2027, 9, 1))
    assert compute_timeliness_modifier(item) == -1.0


@freeze_time("2026-06-02")
def test_no_modifier_for_no_dates():
    item = make_item()
    assert compute_timeliness_modifier(item) == 0.0


# --- apply_scores ---

def test_apply_scores_computes_final(sample_config):
    item = make_item(raw_score=7.0)
    results = apply_scores([item], sample_config)
    assert results[0].final_score == pytest.approx(7.0 + results[0].timeliness_modifier)


def test_apply_scores_sorted_descending(sample_config):
    items = [make_item(raw_score=5.0), make_item(title="B", url="https://b.com", raw_score=9.0)]
    results = apply_scores(items, sample_config)
    assert results[0].raw_score == 9.0


# --- filter_by_min_score ---

def test_filter_drops_below_threshold(sample_config):
    items = [make_item(raw_score=5.0), make_item(title="B", url="https://b.com", raw_score=7.0)]
    # sample_config has min_relevance_score=6
    result = filter_by_min_score(items, sample_config.search.min_relevance_score)
    assert len(result) == 1
    assert result[0].raw_score == 7.0


# --- enforce_slots ---

def test_enforce_slots_limits_per_category(sample_config):
    # sample_config CategorySlots: in_person=1, online=1, cohort=1, books=0, wildcard=1
    items = [
        make_item(title=f"Conf {i}", url=f"https://c{i}.com", category="in_person_events", raw_score=float(10 - i))
        for i in range(3)
    ]
    result = enforce_slots(items, sample_config.digest)
    in_person = [x for x in result if x.category == "in_person_events"]
    assert len(in_person) == 1  # slot limit for sample_config


def test_enforce_slots_fills_wildcard(sample_config):
    items = [
        make_item(title="Course 1", url="https://c1.com", category="online_courses", raw_score=9.0),
        make_item(title="Course 2", url="https://c2.com", category="online_courses", raw_score=8.0),
        make_item(title="Wildcard", url="https://w.com", category="wildcard", raw_score=7.0),
    ]
    result = enforce_slots(items, sample_config.digest)
    categories = {x.category for x in result}
    assert "wildcard" in categories


def test_enforce_slots_respects_digest_size(sample_config):
    items = [
        make_item(title=f"Item {i}", url=f"https://i{i}.com", category="in_person_events", raw_score=float(10 - i))
        for i in range(10)
    ]
    result = enforce_slots(items, sample_config.digest)
    assert len(result) <= sample_config.search.digest_size


# --- build_digest ---

def test_build_digest_returns_digest(sample_config):
    items = [make_item(raw_score=8.0)]
    digest = build_digest(items, sample_config)
    assert len(digest.items) >= 0
    assert digest.generated_at is not None


def test_build_digest_budget_filter(sample_config):
    # sample_config budget_aud=3000
    cheap = make_item(title="Cheap", url="https://cheap.com", cost_aud=500.0, raw_score=8.0)
    expensive = make_item(title="Expensive", url="https://exp.com", cost_aud=5000.0, raw_score=9.0)
    digest = build_digest([cheap, expensive], sample_config)
    titles = [i.title for i in digest.items]
    assert "Expensive" not in titles
    assert "Cheap" in titles


def test_build_digest_unknown_cost_passes(sample_config):
    item = make_item(title="Unknown Cost", url="https://unk.com", cost_aud=None, raw_score=8.0)
    digest = build_digest([item], sample_config)
    assert any(i.title == "Unknown Cost" for i in digest.items)
