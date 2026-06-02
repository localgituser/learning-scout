"""GitHub Actions entry point — runs the full weekly scout pipeline."""
from __future__ import annotations
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from anthropic import AsyncAnthropic

from learning_scout.config_loader import load_config, ConfigValidationError
from learning_scout.github_writer import GitHubWriterConfig, commit_seen_json
from learning_scout.memory import load_seen, save_seen, filter_unseen, filter_blocked, mark_seen
from learning_scout.scout import run_search
from learning_scout.scorer import build_digest
from learning_scout.telegram_bot import send_digest


async def _run(dry_run: bool = False) -> None:
    config = load_config(Path("config.yaml"))

    seen, blocked = load_seen()
    client = AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        default_headers={"anthropic-beta": "web-search-2025-03-05"},
        timeout=60.0,
    )

    raw_items = await run_search(config, client=client)
    unseen = filter_unseen(raw_items, seen)
    unblocked = filter_blocked(unseen, blocked)

    digest = build_digest(unblocked, config)

    if not digest.items:
        print("No new items to send this week.")
        return

    if dry_run:
        print(f"[dry-run] Would send {len(digest.items)} items:")
        for item in digest.items:
            print(f"  [{item.category}] {item.title} — score {item.final_score:.1f}")
        return

    try:
        await send_digest(digest, config)
    except Exception as exc:
        print(f"Failed to send digest: {exc}", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    for item in digest.items:
        seen = mark_seen(seen, item, "skipped", today)  # default to skipped; bot upgrades to saved
    save_seen(seen, blocked)

    gh = GitHubWriterConfig(
        token=os.environ["GITHUB_TOKEN"],
        repo=os.environ["GITHUB_REPO"],
    )
    await commit_seen_json(seen, blocked, gh, message="chore: update seen.json after digest [skip ci]")
    print(f"Sent {len(digest.items)} items and committed seen.json to GitHub.")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    try:
        asyncio.run(_run(dry_run=dry_run))
    except ConfigValidationError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyError as exc:
        print(f"Missing env var: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
