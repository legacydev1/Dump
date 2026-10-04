"""
auth.py - Role-based authorization middleware.

Injects role info into handler data dict so handlers can inspect:
    data["is_root_admin"]   -> bool
    data["is_sub_admin"]    -> bool
    data["is_banned"]       -> bool
    data["db_user"]         -> dict | None
    data["user_role"]       -> "root" | "admin" | "user"

Also registers/updates the user in the database on every interaction.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from config import settings
from database.queries import (
    get_admin,
    get_user_with_plan,
    upsert_user,
    ensure_default_plan,
)

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Inner middleware — runs after routing, injects role data.
    Register on router or dispatcher as inner middleware.
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
        elif event.inline_query:
            user = event.inline_query.from_user

        if user is None:
            data["is_root_admin"] = False
            data["is_sub_admin"] = False
            data["is_banned"] = False
            data["db_user"] = None
            data["user_role"] = "anonymous"
            return await handler(event, data)

        user_id = user.id
        is_root = user_id in settings.ADMIN_IDS

        try:
            # Ensure user exists in DB
            await upsert_user(user_id, user.username or "", user.first_name or "")
            await ensure_default_plan(user_id, settings.DEFAULT_PLAN_ID)

            db_user = await get_user_with_plan(user_id)
            admin_record = await get_admin(user_id)

            is_banned = bool(db_user.get("is_banned")) if db_user else False
            is_sub_admin = admin_record is not None and not is_root

            if is_root:
                role = "root"
            elif is_sub_admin:
                role = "admin"
            else:
                role = "user"

        except Exception as e:
            logger.error("AuthMiddleware DB error for user %s: %s", user_id, e)
            db_user = None
            is_banned = False
            is_sub_admin = False
            role = "root" if is_root else "user"
            admin_record = None

        data["is_root_admin"] = is_root
        data["is_sub_admin"] = is_sub_admin
        data["is_banned"] = is_banned
        data["db_user"] = db_user
        data["admin_record"] = admin_record
        data["user_role"] = role

        # Block banned users (admins are never blocked)
        if is_banned and not is_root:
            try:
                if event.message:
                    await event.message.answer(
                        "🚫 Your account has been banned. Contact support."
                    )
                elif event.callback_query:
                    await event.callback_query.answer(
                        "🚫 Your account has been banned.", show_alert=True
                    )
            except Exception:
                pass
            return  # Block update

        return await handler(event, data)
