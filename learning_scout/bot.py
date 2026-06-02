"""Railway entry point — runs the Telegram polling loop."""
import logging
import os

from learning_scout.telegram_bot import build_application


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    # Fail fast: TELEGRAM_CHAT_ID is required to authorise callbacks
    _ = os.environ["TELEGRAM_CHAT_ID"]
    app = build_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
