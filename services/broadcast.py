"""
broadcast.py - Rate-limited broadcast service.

Supports sending:
  - Text messages
  - Photos with caption
  - Videos with caption
  - Documents with caption

Returns (sent_count, failed_count)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)

_SEND_DELAY: float = 0.05   # 50ms between sends ≈ 20 msgs/sec
_MAX_RETRIES: int  = 3


async def _send_one(
    bot: Bot,
    user_id: int,
    text: str,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
    retries: int = 0,
) -> bool:
    """
    Send one message to user_id.
    media_type: None (text only) | "photo" | "video" | "document"
    """
    try:
        if media_type == "photo" and media_file_id:
            await bot.send_photo(
                user_id,
                photo=media_file_id,
                caption=text or None,
                parse_mode="HTML",
            )
        elif media_type == "video" and media_file_id:
            await bot.send_video(
                user_id,
                video=media_file_id,
                caption=text or None,
                parse_mode="HTML",
            )
        elif media_type == "document" and media_file_id:
            await bot.send_document(
                user_id,
                document=media_file_id,
                caption=text or None,
                parse_mode="HTML",
            )
        else:
            # Plain text broadcast
            await bot.send_message(user_id, text, parse_mode="HTML")
        return True

    except TelegramRetryAfter as e:
        if retries >= _MAX_RETRIES:
            logger.warning("Flood limit exceeded for user %s after %d retries.", user_id, retries)
            return False
        wait = e.retry_after + 1
        logger.info("Flood wait %ds, retrying user %s…", wait, user_id)
        await asyncio.sleep(wait)
        return await _send_one(bot, user_id, text, media_type, media_file_id, retries + 1)

    except TelegramForbiddenError:
        logger.debug("User %s has blocked the bot.", user_id)
        return False

    except TelegramBadRequest as e:
        logger.warning("Bad request sending to user %s: %s", user_id, e)
        return False

    except Exception as e:
        logger.warning("Unexpected error sending to user %s: %s", user_id, e)
        return False


async def send_broadcast(
    bot: Bot,
    users: List[Dict],
    text: str,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Send a broadcast to all users.

    Args:
        bot:           Aiogram Bot instance.
        users:         List of dicts with at least {'id': int}.
        text:          HTML-formatted message text (caption for media).
        media_type:    None | "photo" | "video" | "document"
        media_file_id: Telegram file_id for the media.

    Returns:
        (sent_count, failed_count)
    """
    sent   = 0
    failed = 0

    for user in users:
        user_id: int = user["id"]
        success = await _send_one(bot, user_id, text, media_type, media_file_id)
        if success:
            sent += 1
        else:
            failed += 1
        await asyncio.sleep(_SEND_DELAY)

    logger.info(
        "Broadcast complete: %d sent, %d failed out of %d total.",
        sent, failed, len(users),
    )
    return sent, failed
