"""Telegram bot: sends digests and handles Save/Skip callbacks and text commands."""
from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from learning_scout.formatter import (
    format_item_html,
    format_digest_intro,
    format_saved_list,
    format_blocked_list,
)
from learning_scout.github_writer import GitHubWriterConfig, commit_seen_json
from learning_scout.memory import load_seen, save_seen, mark_seen, add_blocked_keyword
from learning_scout.models import AppConfig, Digest


@dataclass
class TelegramCallbackData:
    action: str  # "save" | "skip"
    item_hash: str


_ALLOWED_ACTIONS = {"save", "skip"}
_HASH_LEN = 16  # first 16 hex chars; fits "save:aaabbbcccdddee" in 64 bytes


def build_callback_data(action: str, item_hash: str) -> str:
    return f"{action}:{item_hash[:_HASH_LEN]}"


def parse_callback_data(data: str) -> Optional[TelegramCallbackData]:
    if not data or ":" not in data:
        return None
    action, _, item_hash = data.partition(":")
    if action not in _ALLOWED_ACTIONS or not item_hash:
        return None
    return TelegramCallbackData(action=action, item_hash=item_hash)


def is_authorised(update: Update, allowed_chat_id: str) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return str(user.id) == str(allowed_chat_id)


def _github_config() -> GitHubWriterConfig:
    return GitHubWriterConfig(
        token=os.environ["GITHUB_TOKEN"],
        repo=os.environ["GITHUB_REPO"],
    )


async def send_digest(digest: Digest, config: AppConfig) -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = config.delivery.telegram_chat_id or os.environ["TELEGRAM_CHAT_ID"]

    app = Application.builder().token(bot_token).build()
    async with app:
        await app.bot.send_message(
            chat_id=chat_id,
            text=format_digest_intro(total=len(digest.items)),
            parse_mode=ParseMode.HTML,
        )
        for i, item in enumerate(digest.items, 1):
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("💾 Save", callback_data=build_callback_data("save", item.content_hash)),
                InlineKeyboardButton("⏭ Skip", callback_data=build_callback_data("skip", item.content_hash)),
            ]])
            await app.bot.send_message(
                chat_id=chat_id,
                text=format_item_html(item, i),
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not is_authorised(update, allowed_chat_id):
        return  # silent ignore — no info to unknown senders

    query = update.callback_query
    await query.answer()

    parsed = parse_callback_data(query.data or "")
    if parsed is None:
        return

    seen, blocked = load_seen()
    # Find matching item by exact-length prefix — require unique match to prevent mis-targeting
    candidates = [item for h, item in seen.items() if h.startswith(parsed.item_hash)]
    if len(candidates) != 1:
        await query.edit_message_text("⚠️ Item not found — it may have expired.")
        return
    matched = candidates[0]
    _ACTION_TO_STATUS = {"save": "saved", "skip": "skipped"}
    new_status = _ACTION_TO_STATUS[parsed.action]
    seen[matched.id] = matched.model_copy(update={"status": new_status})
    save_seen(seen, blocked)

    gh = _github_config()
    await commit_seen_json(seen, blocked, gh)

    label = "💾 Saved!" if parsed.action == "save" else "⏭ Skipped"
    await query.edit_message_reply_markup(reply_markup=None)
    await query.answer(label, show_alert=False)


async def _handle_saved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorised(update, os.environ.get("TELEGRAM_CHAT_ID", "")):
        return
    seen, _ = load_seen()
    text = format_saved_list(list(seen.values()))
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


_MAX_KEYWORD_LEN = 100


async def _handle_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorised(update, os.environ.get("TELEGRAM_CHAT_ID", "")):
        return
    keyword = " ".join(context.args or []).strip()[:_MAX_KEYWORD_LEN]
    if not keyword:
        await update.message.reply_text("Usage: /block <keyword>")
        return
    seen, blocked = load_seen()
    blocked = add_blocked_keyword(blocked, keyword)
    save_seen(seen, blocked)
    gh = _github_config()
    await commit_seen_json(seen, blocked, gh)
    await update.message.reply_text(f'🚫 Blocked: "{keyword}". It won\'t appear in future digests.')


async def _handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorised(update, os.environ.get("TELEGRAM_CHAT_ID", "")):
        return
    save_seen({}, [])
    gh = _github_config()
    await commit_seen_json({}, [], gh)
    await update.message.reply_text("♻️ History cleared. Next digest starts fresh.")


def build_application(bot_token: str) -> Application:
    app = Application.builder().token(bot_token).build()
    app.add_handler(CallbackQueryHandler(_handle_callback))
    app.add_handler(CommandHandler("saved", _handle_saved))
    app.add_handler(CommandHandler("block", _handle_block))
    app.add_handler(CommandHandler("reset", _handle_reset))
    return app
