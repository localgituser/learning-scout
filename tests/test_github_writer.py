import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from learning_scout.github_writer import commit_seen_json, GitHubWriterConfig, GitHubWriteError
from learning_scout.models import SeenItem
from datetime import date


@pytest.fixture
def writer_config():
    return GitHubWriterConfig(
        token="ghp_test",
        repo="user/repo",
        branch="main",
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
async def test_commit_seen_json_creates_file_when_not_exists(writer_config, sample_seen):
    mock_client = AsyncMock()
    # GET returns 404 (file doesn't exist)
    mock_get = AsyncMock()
    mock_get.status_code = 404
    mock_client.get = AsyncMock(return_value=mock_get)

    # PUT returns 201
    mock_put = AsyncMock()
    mock_put.status_code = 201
    mock_put.json = MagicMock(return_value={"commit": {"sha": "abc"}})
    mock_client.put = AsyncMock(return_value=mock_put)

    with patch("learning_scout.github_writer.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await commit_seen_json(sample_seen, [], writer_config)

    mock_client.put.assert_called_once()
    call_kwargs = mock_client.put.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["json"]
    assert "content" in body
    assert "sha" not in body  # no sha for new file


@pytest.mark.asyncio
async def test_commit_seen_json_updates_existing_file(writer_config, sample_seen):
    mock_client = AsyncMock()
    existing_sha = "existingsha123"
    mock_get = AsyncMock()
    mock_get.status_code = 200
    mock_get.json = MagicMock(return_value={"sha": existing_sha, "content": base64.b64encode(b"{}").decode()})
    mock_client.get = AsyncMock(return_value=mock_get)

    mock_put = AsyncMock()
    mock_put.status_code = 200
    mock_put.json = MagicMock(return_value={"commit": {"sha": "newsha"}})
    mock_client.put = AsyncMock(return_value=mock_put)

    with patch("learning_scout.github_writer.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await commit_seen_json(sample_seen, [], writer_config)

    call_kwargs = mock_client.put.call_args
    body = call_kwargs.kwargs.get("json") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["json"])
    assert body.get("sha") == existing_sha


@pytest.mark.asyncio
async def test_commit_seen_json_raises_on_error(writer_config, sample_seen):
    mock_client = AsyncMock()
    mock_get = AsyncMock()
    mock_get.status_code = 404
    mock_client.get = AsyncMock(return_value=mock_get)

    mock_put = AsyncMock()
    mock_put.status_code = 422
    mock_put.text = "Unprocessable Entity"
    mock_client.put = AsyncMock(return_value=mock_put)

    with patch("learning_scout.github_writer.httpx.AsyncClient") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(GitHubWriteError):
            await commit_seen_json(sample_seen, [], writer_config)
