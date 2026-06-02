"""Railway entry point — runs the Telegram polling loop."""
import logging
import os

from learning_scout.telegram_bot import build_application

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
