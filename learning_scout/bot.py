"""Railway entry point — runs the Telegram polling loop."""
import os
from learning_scout.telegram_bot import build_application


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
