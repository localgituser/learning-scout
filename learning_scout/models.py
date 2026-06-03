from __future__ import annotations
import hashlib
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


def _hash_key(title: str, url: str) -> str:
    # URL is the canonical identity; title varies across LLM runs for the same resource
    key = url.lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()


CareerStage = Literal["early", "mid", "mid-senior", "senior", "exec"]
ItemStatus = Literal["saved", "skipped", "blocked"]
ItemCategory = Literal["in_person_events", "online_events", "meetups", "courses"]
DeadlineType = Literal["early_bird", "cfp", "scholarship", "enrolment", "certification", "mentorship", "registration"]


class UserProfile(BaseModel):
    current_role: str
    target_role: str
    career_stage: CareerStage
    years_experience: int
    topics_of_interest: list[str] = Field(default_factory=list)


class SearchConfig(BaseModel):
    topics_per_run: int = 8
    results_per_topic: int = 5
    min_relevance_score: float = 6.0
    digest_size: int = 8
    max_concurrent_searches: int = 3
    model: str = "claude-sonnet-4-6"


class CategorySlots(BaseModel):
    in_person_events: int = 1
    online_events: int = 1
    meetups: int = 1
    courses: int = 3

    def as_dict(self) -> dict[str, int]:
        return self.model_dump()


class DigestConfig(BaseModel):
    enforce_category_mix: bool = True
    categories: CategorySlots = Field(default_factory=CategorySlots)


class DeliveryConfig(BaseModel):
    channel: Literal["telegram"] = "telegram"
    send_day: str = "monday"
    send_time: str = "08:00"
    timezone: str = "Australia/Melbourne"
    telegram_chat_id: Optional[str] = None  # falls back to TELEGRAM_CHAT_ID env var if unset


class AppConfig(BaseModel):
    profile: UserProfile
    search: SearchConfig = Field(default_factory=SearchConfig)
    digest: DigestConfig = Field(default_factory=DigestConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    budget_aud: Optional[float] = None
    format_preference: list[str] = Field(default_factory=lambda: ["online", "in-person"])
    regions: list[str] = Field(default_factory=lambda: ["online"])
    commitment: list[str] = Field(default_factory=lambda: ["short", "medium"])


class LearningItem(BaseModel):
    title: str
    url: str
    description: str
    category: ItemCategory
    deadline: Optional[date] = None
    deadline_type: Optional[DeadlineType] = None
    event_date: Optional[date] = None
    cost_aud: Optional[float] = None
    source: str = ""
    raw_score: float = 0.0
    timeliness_modifier: float = 0.0
    final_score: float = 0.0

    @property
    def content_hash(self) -> str:
        return _hash_key(self.title, self.url)


class SeenItem(BaseModel):
    id: str
    title: str
    url: str
    first_seen: date
    status: ItemStatus
    saved_at: Optional[datetime] = None


class Digest(BaseModel):
    generated_at: datetime
    items: list[LearningItem]
