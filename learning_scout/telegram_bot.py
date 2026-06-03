"""Telegram delivery — sends digest messages with Save/Skip inline buttons."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application

from learning_scout.formatter import format_item_html, format_digest_intro
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
