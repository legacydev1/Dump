"""
helpers.py - General utility functions used across the project.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generator, List, Optional, TypeVar

from config import settings

T = TypeVar("T")


def is_root_admin(user_id: int) -> bool:
    """Check if a Telegram user_id is a root admin."""
    return user_id in settings.ADMIN_IDS


def is_admin(data: dict) -> bool:
    """Check if handler data dict indicates any admin role (root or sub)."""
    return data.get("is_root_admin", False) or data.get("is_sub_admin", False)


def chunk_list(lst: List[T], size: int) -> Generator[List[T], None, None]:
    """Yield successive chunks of `size` from list."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_dt(dt_str: Optional[str], fmt: str = "%Y-%m-%d %H:%M UTC") -> str:
    """Format an ISO datetime string for display."""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except Exception:
        return dt_str


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis if it exceeds max_len."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "…"


def escape_html(text: str) -> str:
    """Escape special HTML characters for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


async def safe_edit(callback_or_message, text: str, **kwargs):
    """
    Safely edit a callback message's text.
    If the message has no editable text (e.g. it's a document, photo, or
    sticker), fall back to sending a new message instead.
    This prevents the common TelegramBadRequest:
      'there is no text in the message to edit'
    """
    from aiogram.types import CallbackQuery, Message
    from aiogram.exceptions import TelegramBadRequest

    if isinstance(callback_or_message, CallbackQuery):
        msg = callback_or_message.message
    else:
        msg = callback_or_message

    try:
        await msg.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "there is no text in the message" in str(e).lower() or \
           "message can't be edited" in str(e).lower() or \
           "message is not modified" in str(e).lower():
            # Can't edit — send a fresh message
            await msg.answer(text, **kwargs)
        else:
            raise
