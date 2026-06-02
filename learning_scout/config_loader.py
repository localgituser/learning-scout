from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError
from learning_scout.models import AppConfig


class ConfigValidationError(Exception):
    pass


def load_config(path: Path = Path("config.yaml")) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        raw: Any = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ConfigValidationError(f"Cannot read config file: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigValidationError("Config must be a YAML mapping")

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigValidationError(f"Config validation failed:\n{exc}") from exc
