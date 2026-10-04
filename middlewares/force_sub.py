"""
force_sub.py - Dynamic mandatory channel/group membership middleware.

Channels are stored in the `force_sub_channels` DB table and managed
entirely from the admin panel — no bot restart needed when adding/removing.

Flow on every update:
  1. Load active channels from DB (cached in-process for 60 s)
  2. Skip check for root admins
  3. For each channel: call get_chat_member to verify membership
  4. If any channel not joined → send join prompt with inline buttons
  5. "✅ Check Again" button re-verifies and lets user through

Admin can:
  - Add channel by @username or numeric ID
  - Toggle channel on/off without deleting it
  - Delete channel permanently
  - See join count statistics per channel
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)

from config import settings

logger = logging.getLogger(__name__)

# Member statuses that count as "joined"
_MEMBER_STATUSES = {"member", "administrator", "creator"}

# In-process cache: (channels_list, loaded_at_monotonic)
_cache: Optional[tuple] = None
_CACHE_TTL = 60.0   # seconds — refresh DB read every 60 s


async def _load_active_channels() -> List[Dict]:
    """
    Load active force-sub channels from DB with a short TTL cache
    so we don't hit SQLite on every single Telegram update.
    """
    global _cache
    now = time.monotonic()
    if _cache is not None:
        channels, loaded_at = _cache
        if now - loaded_at < _CACHE_TTL:
            return channels

    try:
        from database.queries import get_force_sub_channels
        channels = await get_force_sub_channels(active_only=True)
    except Exception as e:
        logger.error("Could not load force-sub channels from DB: %s", e)
        channels = []

    _cache = (channels, now)
    return channels


def invalidate_cache() -> None:
    """Call this after any admin add/remove/toggle so next check re-reads DB."""
    global _cache
    _cache = None


async def _check_membership(bot: Bot, user_id: int, chat_id: str) -> bool:
    """Return True if user is an active member of chat_id."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in _MEMBER_STATUSES
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.warning("Membership check skipped for %s in %s: %s", user_id, chat_id, e)
        return True   # can't check → let through to avoid false lockout
    except Exception as e:
        logger.error("Unexpected error checking membership: %s", e)
        return True


async def _build_join_keyboard(
    bot: Bot,
    channels: List[Dict],
    not_joined_ids: List[str],
) -> InlineKeyboardMarkup:
    """
    Build keyboard with a join button for every unjoined channel
    plus a "Check Again" button at the bottom.
    """
    buttons: List[List[InlineKeyboardButton]] = []

    for ch in channels:
        if ch["chat_id"] not in not_joined_ids:
            continue

        # Prefer stored invite_link, then try fetching from Telegram
        link: Optional[str] = ch.get("invite_link") or None
        title: str = ch.get("title") or ch["chat_id"]

        if not link:
            try:
                chat = await bot.get_chat(ch["chat_id"])
                link  = chat.invite_link or (
                    f"https://t.me/{chat.username}" if chat.username else None
                )
                title = chat.title or title
            except Exception:
                pass

        if link:
            buttons.append([
                InlineKeyboardButton(text=f"➡️ Join {title}", url=link)
            ])
        else:
            # No link available — show channel id
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔔 {title}",
                    callback_data="noop",
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ I've Joined — Verify Now",
            callback_data="force_sub_check",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


class ForceSubscribeMiddleware(BaseMiddleware):
    """
    Outer middleware — runs on every incoming Update.
    Checks DB-driven channel list, blocks non-members.
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:

        # ── Extract user ──────────────────────────────────────────────────────
        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user
        elif event.inline_query:
            user = event.inline_query.from_user

        if user is None:
            return await handler(event, data)

        user_id = user.id
        bot: Bot = data["bot"]

        # ── Root admins always bypass ─────────────────────────────────────────
        if user_id in settings.ADMIN_IDS:
            return await handler(event, data)

        # ── Load active channels ──────────────────────────────────────────────
        channels = await _load_active_channels()
        if not channels:
            return await handler(event, data)   # no channels configured → open access

        # ── Handle "Check Again" callback specifically ─────────────────────────
        if (
            event.callback_query
            and event.callback_query.data == "force_sub_check"
        ):
            not_joined = [
                ch["chat_id"]
                for ch in channels
                if not await _check_membership(bot, user_id, ch["chat_id"])
            ]
            if not not_joined:
                await event.callback_query.answer(
                    "✅ Verified! Welcome — you can now use the bot.", show_alert=False
                )
                # Edit the join-prompt message to a welcome notice
                try:
                    await event.callback_query.message.edit_text(
                        "✅ <b>Membership verified!</b>\n\nSend /start to begin.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                return await handler(event, data)
            else:
                await event.callback_query.answer(
                    "❌ You still haven't joined all required channels.",
                    show_alert=True,
                )
                return   # block — show nothing new, keyboard already visible

        # ── Check all active channels ─────────────────────────────────────────
        not_joined: List[str] = []
        for ch in channels:
            if not await _check_membership(bot, user_id, ch["chat_id"]):
                not_joined.append(ch["chat_id"])

        if not not_joined:
            return await handler(event, data)   # all good

        # ── Build & send join prompt ──────────────────────────────────────────
        keyboard = await _build_join_keyboard(bot, channels, not_joined)

        count = len(not_joined)
        ch_word = "channel" if count == 1 else "channels"
        text = (
            "🔒 <b>Access Restricted</b>\n\n"
            f"You must join <b>{count}</b> required {ch_word} to use this bot.\n\n"
            "👇 Tap the button(s) below to join, then press <b>✅ Verify</b>."
        )

        try:
            if event.message:
                await event.message.answer(
                    text, reply_markup=keyboard, parse_mode="HTML"
                )
            elif event.callback_query:
                await event.callback_query.message.answer(
                    text, reply_markup=keyboard, parse_mode="HTML"
                )
                await event.callback_query.answer()
        except Exception as e:
            logger.error("Error sending force-sub message: %s", e)

        return   # block the original update
