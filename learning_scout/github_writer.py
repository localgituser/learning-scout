from __future__ import annotations
import base64
import json
from pydantic import BaseModel, SecretStr
import httpx
from learning_scout.models import SeenItem


class GitHubWriterConfig(BaseModel):
    token: SecretStr
    repo: str
    branch: str = "main"
    committer_name: str = "Learning Scout Bot"
    committer_email: str = "bot@learningscout.local"


class GitHubWriteError(Exception):
    pass


def _serialize_seen(seen: dict[str, SeenItem], blocked: list[str]) -> str:
    payload = {
        "items": [item.model_dump(mode="json") for item in seen.values()],
        "blocked_keywords": blocked,
    }
    return json.dumps(payload, indent=2, default=str)


async def fetch_seen_json(
    config: GitHubWriterConfig,
    path: str = "seen.json",
) -> str | None:
    """Fetch raw JSON content of path from GitHub. Returns None if not found."""
    api_url = f"https://api.github.com/repos/{config.repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {config.token.get_secret_value()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(api_url, headers=headers, params={"ref": config.branch})
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise GitHubWriteError(f"Failed to fetch {path}: HTTP {resp.status_code}")
    encoded = resp.json().get("content", "")
    return base64.b64decode(encoded).decode()


async def commit_seen_json(
    seen: dict[str, SeenItem],
    blocked: list[str],
    config: GitHubWriterConfig,
    path: str = "seen.json",
    message: str = "chore: update seen.json [skip ci]",
) -> None:
    api_url = f"https://api.github.com/repos/{config.repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {config.token.get_secret_value()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        get_resp = await client.get(api_url, headers=headers, params={"ref": config.branch})

        existing_sha: str | None = None
        if get_resp.status_code == 200:
            existing_sha = get_resp.json()["sha"]
        elif get_resp.status_code != 404:
            raise GitHubWriteError(f"Failed to fetch {path}: HTTP {get_resp.status_code}")

        content_b64 = base64.b64encode(_serialize_seen(seen, blocked).encode()).decode()
        body: dict = {
            "message": message,
            "content": content_b64,
            "branch": config.branch,
            "committer": {"name": config.committer_name, "email": config.committer_email},
        }
        if existing_sha:
            body["sha"] = existing_sha

        put_resp = await client.put(api_url, headers=headers, json=body)
        if put_resp.status_code not in (200, 201):
            raise GitHubWriteError(f"Failed to commit {path}: HTTP {put_resp.status_code}")
