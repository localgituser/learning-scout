import pytest
from pathlib import Path
import yaml
from learning_scout.config_loader import load_config, ConfigValidationError


VALID_CONFIG = {
    "profile": {
        "current_role": "Senior PM",
        "target_role": "Head of Product",
        "career_stage": "mid-senior",
        "years_experience": 8,
        "topics_of_interest": ["product strategy", "data"],
    },
    "search": {
        "topics_per_run": 8,
        "results_per_topic": 5,
        "min_relevance_score": 6,
        "digest_size": 8,
    },
    "digest": {
        "enforce_category_mix": True,
        "categories": {
            "in_person_events": 2,
            "online_events": 1,
            "meetups": 1,
            "courses": 2,
        },
    },
    "delivery": {
        "channel": "telegram",
        "send_day": "monday",
        "send_time": "08:00",
        "timezone": "Australia/Melbourne",
    },
    "budget_aud": 3000,
    "format_preference": ["online", "in-person"],
    "regions": ["australia", "online"],
    "commitment": ["short", "medium"],
}


def write_config(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    return p


def test_load_valid_config(tmp_path):
    path = write_config(tmp_path, VALID_CONFIG)
    config = load_config(path)
    assert config.profile.current_role == "Senior PM"
    assert config.profile.years_experience == 8
    assert config.search.topics_per_run == 8
    assert config.budget_aud == 3000
    assert config.digest.categories.in_person_events == 2
    assert config.delivery.timezone == "Australia/Melbourne"


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_load_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("profile: [invalid: yaml: {")
    with pytest.raises(ConfigValidationError):
        load_config(bad)


def test_load_missing_required_field_raises(tmp_path):
    data = {k: v for k, v in VALID_CONFIG.items() if k != "profile"}
    path = write_config(tmp_path, data)
    with pytest.raises(ConfigValidationError):
        load_config(path)


def test_invalid_career_stage_raises(tmp_path):
    data = dict(VALID_CONFIG)
    data["profile"] = dict(VALID_CONFIG["profile"])
    data["profile"]["career_stage"] = "wizard"
    path = write_config(tmp_path, data)
    with pytest.raises(ConfigValidationError):
        load_config(path)


def test_budget_defaults_to_none(tmp_path):
    data = {k: v for k, v in VALID_CONFIG.items() if k != "budget_aud"}
    path = write_config(tmp_path, data)
    config = load_config(path)
    assert config.budget_aud is None


def test_format_preference_defaults(tmp_path):
    data = {k: v for k, v in VALID_CONFIG.items() if k != "format_preference"}
    path = write_config(tmp_path, data)
    config = load_config(path)
    assert isinstance(config.format_preference, list)
