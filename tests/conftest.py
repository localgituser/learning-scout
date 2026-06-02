import pytest
from pathlib import Path
from learning_scout.models import (
    UserProfile,
    SearchConfig,
    DigestConfig,
    DeliveryConfig,
    AppConfig,
    LearningItem,
    CategorySlots,
)


@pytest.fixture
def sample_config(tmp_path) -> AppConfig:
    return AppConfig(
        profile=UserProfile(
            current_role="Senior Product Manager",
            target_role="Head of Product",
            career_stage="mid-senior",
            years_experience=10,
            topics_of_interest=["product strategy", "AI/ML product management"],
        ),
        search=SearchConfig(
            topics_per_run=4,
            results_per_topic=3,
            min_relevance_score=6,
            digest_size=4,
        ),
        digest=DigestConfig(
            enforce_category_mix=True,
            categories=CategorySlots(
                in_person_events=1,
                online_courses=1,
                cohort_programs=1,
                books_or_resources=0,
                wildcard=1,
            ),
        ),
        delivery=DeliveryConfig(
            channel="telegram",
            send_day="monday",
            send_time="08:00",
            timezone="Australia/Melbourne",
        ),
        budget_aud=3000,
        format_preference=["online", "in-person"],
        regions=["australia", "online"],
        commitment=["short", "medium"],
    )


@pytest.fixture
def sample_item() -> LearningItem:
    return LearningItem(
        title="Mind the Product Leadership Summit",
        url="https://example.com/mtp",
        description="Leadership summit for senior PMs",
        category="in_person_events",
        cost_aud=1800.0,
    )
