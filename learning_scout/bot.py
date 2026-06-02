"""Railway entry point — runs the Telegram polling loop."""
import logging
import os
import sys

from telegram.error import Conflict

from learning_scout.telegram_bot import build_application

logger = logging.getLogger(__name__)


async def _error_handler(update: object, context: object) -> None:
    if isinstance(context.error, Conflict):
        logger.error("Conflict: another bot instance is polling. Exiting so Railway can restart cleanly.")
        sys.exit(1)
    logger.error("Unhandled error: %s", context.error)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build_application(token)
    app.add_error_handler(_error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
