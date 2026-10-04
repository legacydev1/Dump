"""
throttling.py - Per-user rate limiting middleware using an in-memory cache.

Limits are plan-aware:
  - Root admins: no limit
  - Regular users: respect plan cooldown_seconds between searches
  - General spam protection: max N messages per time window

The throttle state lives in-process (a dict). For multi-process deployments,
replace with Redis. For this single-process bot, it is sufficient.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from config import settings

logger = logging.getLogger(__name__)

# General anti-spam: max 30 messages per 60 seconds per user
_GENERAL_RATE_LIMIT = 30
_GENERAL_WINDOW_SEC = 60

# Per-user message timestamps for general rate limiting
_user_message_times: Dict[int, list] = defaultdict(list)

# Per-user last search timestamps (for plan cooldown enforcement)
_user_last_search: Dict[int, float] = {}

_lock = asyncio.Lock()


class ThrottlingMiddleware(BaseMiddleware):
    """
    Outer middleware for general message rate limiting.
    Search-specific cooldown is enforced in the search handler using
    set_last_search / check_search_cooldown helpers below.
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if event.message:
            user = event.message.from_user
        elif event.callback_query:
            user = event.callback_query.from_user

        if user is None:
            return await handler(event, data)

        user_id = user.id

        # Root admins bypass all throttling
        if user_id in settings.ADMIN_IDS:
            return await handler(event, data)

        now = time.monotonic()

        async with _lock:
            times = _user_message_times[user_id]
            # Drop entries outside the window
            cutoff = now - _GENERAL_WINDOW_SEC
            _user_message_times[user_id] = [t for t in times if t > cutoff]
            _user_message_times[user_id].append(now)

            if len(_user_message_times[user_id]) > _GENERAL_RATE_LIMIT:
                try:
                    if event.message:
                        await event.message.answer(
                            "⏳ You're sending messages too fast. Please slow down."
                        )
                    elif event.callback_query:
                        await event.callback_query.answer(
                            "⏳ Too many requests. Please slow down.", show_alert=True
                        )
                except Exception:
                    pass
                return  # Block update

        return await handler(event, data)


# ── Search-specific cooldown helpers (used by search handler) ─────────────────

def set_last_search(user_id: int) -> None:
    """Record the current time as the user's last search timestamp."""
    _user_last_search[user_id] = time.monotonic()


def get_search_cooldown_remaining(user_id: int, cooldown_seconds: int) -> float:
    """
    Return seconds remaining in the cooldown, or 0 if the user can search now.
    """
    if cooldown_seconds <= 0:
        return 0.0
    last = _user_last_search.get(user_id)
    if last is None:
        return 0.0
    elapsed = time.monotonic() - last
    remaining = cooldown_seconds - elapsed
    return max(0.0, remaining)
