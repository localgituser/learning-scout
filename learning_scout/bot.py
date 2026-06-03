"""Railway entry point — runs the Telegram polling loop."""
import logging
import os

from learning_scout.telegram_bot import build_application


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    # Fail fast: all required env vars must be present before the polling loop starts
    _ = os.environ["TELEGRAM_CHAT_ID"]
    _ = os.environ["GH_PAT"]
    _ = os.environ.get("GITHUB_STATE_REPO") or os.environ["GITHUB_REPO"]
    app = build_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
