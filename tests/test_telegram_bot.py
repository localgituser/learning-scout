import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from learning_scout.telegram_bot import (
    parse_callback_data,
    build_callback_data,
    is_authorised,
    TelegramCallbackData,
)


def test_build_and_parse_callback_data():
    data = build_callback_data("save", "abc123def456")
    parsed = parse_callback_data(data)
    assert parsed.action == "save"
    assert parsed.item_hash == "abc123def456"


def test_parse_callback_data_invalid_returns_none():
    assert parse_callback_data("garbage") is None
    assert parse_callback_data("") is None
    assert parse_callback_data("save") is None


def test_parse_callback_data_wrong_action_returns_none():
    data = "delete:abc123"
    assert parse_callback_data(data) is None


def test_build_callback_data_truncates_hash():
    long_hash = "a" * 64  # full SHA-256 hex
    data = build_callback_data("skip", long_hash)
    # callback_data must fit in 64 bytes
    assert len(data.encode()) <= 64


def test_is_authorised_matching_id():
    update = MagicMock()
    update.effective_user.id = 12345
    assert is_authorised(update, "12345") is True


def test_is_authorised_non_matching_id():
    update = MagicMock()
    update.effective_user.id = 99999
    assert is_authorised(update, "12345") is False


def test_is_authorised_no_user():
    update = MagicMock()
    update.effective_user = None
    assert is_authorised(update, "12345") is False
