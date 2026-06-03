"""GitHub Actions entry point — runs the full weekly scout pipeline."""
from __future__ import annotations
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from anthropic import AsyncAnthropic

from learning_scout.cf_state_client import CFStateConfig, fetch_state, push_state
from learning_scout.config_loader import load_config, ConfigValidationError
from learning_scout.memory import filter_unseen, filter_blocked, mark_seen
from learning_scout.scout import run_search
from learning_scout.scorer import build_digest
from learning_scout.telegram_bot import send_digest


def _cf_config() -> CFStateConfig:
    return CFStateConfig(
        worker_url=os.environ["CF_WORKER_URL"],
        api_secret=os.environ["CF_API_SECRET"],
    )


async def _run(dry_run: bool = False) -> None:
    config = load_config(Path("config.yaml"))

    today = date.today()
    seen, blocked = await fetch_state(_cf_config())
    client = AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        default_headers={"anthropic-beta": "web-search-2025-03-05"},
        timeout=60.0,
    )

    raw_items = await run_search(config, client=client, as_of=today)
    unseen = filter_unseen(raw_items, seen)
    unblocked = filter_blocked(unseen, blocked)

    digest = build_digest(unblocked, config, as_of=today)

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

    for item in digest.items:
        seen = mark_seen(seen, item, "skipped", today)  # default; Worker upgrades to saved

    # Re-fetch before writing to merge any user interactions (saves, blocks) that
    # occurred during the 2-3 minute search window.
    fresh_seen, fresh_blocked = await fetch_state(_cf_config())
    for item_id, item in seen.items():
        if item_id not in fresh_seen:
            fresh_seen[item_id] = item
    merged_blocked = list(fresh_blocked)
    for kw in blocked:
        if kw not in merged_blocked:
            merged_blocked.append(kw)

    await push_state(fresh_seen, merged_blocked, _cf_config())
    print(f"Sent {len(digest.items)} items and pushed state to Cloudflare KV.")


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
