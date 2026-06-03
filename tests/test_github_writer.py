import json
import pytest
from unittest.mock import AsyncMock, patch
from learning_scout.cf_state_client import CFStateConfig, fetch_state, push_state, CFStateError
from learning_scout.models import SeenItem
from datetime import date


@pytest.fixture
def cf_config():
    return CFStateConfig(
        worker_url="https://learning-scout-bot.example.workers.dev",
        api_secret="test-secret",
    )


@pytest.fixture
def sample_seen():
    return {
        "abc123": SeenItem(
            id="abc123",
            title="Test Item",
            url="https://example.com",
            first_seen=date(2026, 6, 2),
            status="saved",
        )
    }


@pytest.mark.asyncio
async def test_fetch_state_returns_items(cf_config, sample_seen):
    payload = {
        "items": [item.model_dump(mode="json") for item in sample_seen.values()],
        "blocked_keywords": ["mba"],
    }
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(payload, default=str)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("learning_scout.cf_state_client.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        seen, blocked = await fetch_state(cf_config)

    assert "abc123" in seen
    assert blocked == ["mba"]
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    assert call_kwargs.kwargs["headers"]["X-API-Secret"] == "test-secret"


@pytest.mark.asyncio
async def test_fetch_state_returns_empty_on_404(cf_config):
    mock_resp = AsyncMock()
    mock_resp.status_code = 404
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("learning_scout.cf_state_client.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        seen, blocked = await fetch_state(cf_config)

    assert seen == {}
    assert blocked == []


@pytest.mark.asyncio
async def test_fetch_state_raises_on_error(cf_config):
    mock_resp = AsyncMock()
    mock_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("learning_scout.cf_state_client.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(CFStateError):
            await fetch_state(cf_config)


@pytest.mark.asyncio
async def test_push_state_sends_correct_payload(cf_config, sample_seen):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_resp)

    with patch("learning_scout.cf_state_client.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await push_state(sample_seen, ["mba"], cf_config)

    mock_client.put.assert_called_once()
    call_kwargs = mock_client.put.call_args
    assert call_kwargs.kwargs["headers"]["X-API-Secret"] == "test-secret"
    body = json.loads(call_kwargs.kwargs["content"])
    assert len(body["items"]) == 1
    assert body["blocked_keywords"] == ["mba"]


@pytest.mark.asyncio
async def test_push_state_raises_on_error(cf_config, sample_seen):
    mock_resp = AsyncMock()
    mock_resp.status_code = 401
    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_resp)

    with patch("learning_scout.cf_state_client.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(CFStateError):
            await push_state(sample_seen, [], cf_config)
