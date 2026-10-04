"""
group_support.py - Group chat support middleware.

Allows the bot to function in allowed groups.
In groups:
  - /start, /help, /search commands work
  - Regular users interact normally
  - Admin commands still require admin privileges
  - Force-sub is skipped in groups (checked per user in private)
  - Unallowed groups: bot ignores all messages (silent)
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from config import settings

logger = logging.getLogger(__name__)


class GroupSupportMiddleware(BaseMiddleware):
    """
    Outer middleware — handles group message filtering.
    
    Rules:
    1. Private chats → always pass through (existing behavior)
    2. Groups/supergroups:
       - If allowed_groups is configured: only allowed groups pass through
       - If no allowed_groups configured: all groups are allowed
    3. Channels → ignored
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Determine chat type
        chat = None
        if event.message:
            chat = event.message.chat
        elif event.callback_query and event.callback_query.message:
            chat = event.callback_query.message.chat

        if chat is None:
            return await handler(event, data)

        chat_type = chat.type

        # Private chats → always pass through
        if chat_type == "private":
            return await handler(event, data)

        # Channel posts → ignore
        if chat_type == "channel":
            return

        # Groups and supergroups
        if chat_type in ("group", "supergroup"):
            chat_id = chat.id

            # Root admins always bypass group restrictions
            user = None
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

            if user and user.id in settings.ADMIN_IDS:
                return await handler(event, data)

            # Check if group is in allowed list
            try:
                from database.queries import is_group_allowed, get_allowed_groups
                allowed_groups = await get_allowed_groups()

                if allowed_groups:
                    # Allowed groups list is configured — enforce it
                    if not await is_group_allowed(chat_id):
                        # Bot is in an unallowed group — silently ignore
                        logger.debug(
                            "Ignoring message from unallowed group %s (%s)",
                            chat_id, chat.title or "",
                        )
                        return
                # else: no groups configured → allow all groups
            except Exception as e:
                logger.error("GroupSupportMiddleware DB error: %s", e)
                # On error, allow through to avoid blocking users

            return await handler(event, data)

        # Unknown chat type → pass through
        return await handler(event, data)
