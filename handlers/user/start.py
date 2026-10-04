"""
start.py - /start command, main menu, force-sub verification.
Works in both private chats and groups.
"""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from database.queries import award_points
from keyboards.user_kb import main_menu_kb
from utils.text_format import welcome_text, DIV, DIV2, E_SNOWFLAKE, E_FIRE
from utils.unicode_style import Bu

logger = logging.getLogger(__name__)
router = Router(name="start")

_MEMBER_STATUSES = {"member", "administrator", "creator"}


async def _safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "no text in the message" in err or \
           "message can't be edited" in err or \
           "message is not modified" in err:
            await callback.message.answer(text, **kwargs)
        else:
            raise


async def _get_not_joined(bot: Bot, user_id: int) -> tuple[list, list]:
    try:
        from database.queries import get_force_sub_channels
        channels = await get_force_sub_channels(active_only=True)
    except Exception as e:
        logger.error("Could not load force-sub channels: %s", e)
        return [], []

    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["chat_id"], user_id)
            if member.status not in _MEMBER_STATUSES:
                not_joined.append(ch)
        except Exception:
            pass

    return channels, not_joined


async def _build_join_kb(
    bot: Bot, channels: list, not_joined: list
) -> InlineKeyboardMarkup:
    buttons: list = []
    not_joined_ids = {ch["chat_id"] for ch in not_joined}

    for ch in channels:
        if ch["chat_id"] not in not_joined_ids:
            continue
        link: Optional[str] = ch.get("invite_link") or None
        title: str = ch.get("title") or ch["chat_id"]
        if not link:
            try:
                chat  = await bot.get_chat(ch["chat_id"])
                link  = chat.invite_link or (
                    f"https://t.me/{chat.username}" if chat.username else None
                )
                title = chat.title or title
            except Exception:
                pass
        if link:
            buttons.append([InlineKeyboardButton(text=f"➡️ Join {title}", url=link)])

    buttons.append([
        InlineKeyboardButton(
            text="✅ I've Joined — Verify Now",
            callback_data="force_sub_check",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _join_prompt_text(not_joined: list) -> str:
    count   = len(not_joined)
    ch_word = Bu("CHANNEL") if count == 1 else Bu("CHANNELS")
    ch_list = "\n".join(
        f"  • <b>{Bu((ch.get('title') or ch['chat_id']).upper())}</b>"
        for ch in not_joined
    )
    return (
        f"🔒 <b>{Bu('JOIN REQUIRED')}</b>\n\n"
        f"{DIV2}\n"
        f"<b>{Bu('YOU MUST JOIN')} {count} {ch_word} {Bu('TO USE THIS BOT:')}</b>\n\n"
        f"{ch_list}\n"
        f"{DIV2}\n\n"
        f"<b>👇 {Bu('TAP THE BUTTON(S) TO JOIN, THEN TAP')} ✅ {Bu('VERIFY.')}</b>"
    )


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(message: Message, db_user: dict, state: FSMContext) -> None:
    await state.clear()

    if not db_user:
        await message.answer(
            f"⚠️ <b>{Bu('COULD NOT LOAD YOUR PROFILE. PLEASE TRY AGAIN.')}</b>",
            parse_mode="HTML",
        )
        return

    from config import settings
    user_id = message.from_user.id

    # Award daily login reward
    await award_points(user_id, "daily_login")

    # Root admins skip force-sub
    if user_id in settings.ADMIN_IDS:
        await message.answer(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    # In group/supergroup — skip force-sub check to avoid spam
    if message.chat.type in ("group", "supergroup"):
        await message.answer(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    # Check membership for private chats
    channels, not_joined = await _get_not_joined(message.bot, user_id)

    if not_joined:
        keyboard = await _build_join_kb(message.bot, channels, not_joined)
        await message.answer(
            _join_prompt_text(not_joined),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    await message.answer(
        welcome_text(db_user),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


router.message.register(cmd_start, CommandStart())


# ── Verify button ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "force_sub_check")
async def cb_verify_membership(
    callback: CallbackQuery, db_user: dict, state: FSMContext
) -> None:
    from config import settings
    user_id = callback.from_user.id

    if user_id in settings.ADMIN_IDS:
        await _safe_edit(
            callback,
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer("✅ Admin access granted!")
        return

    channels, not_joined = await _get_not_joined(callback.bot, user_id)

    if not_joined:
        names = ", ".join(ch.get("title") or ch["chat_id"] for ch in not_joined)
        await callback.answer(
            f"❌ Still not joined: {names}",
            show_alert=True,
        )
        return

    await callback.answer("✅ Verified! Welcome.")
    try:
        await callback.message.edit_text(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )


# ── Back to menu ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_back")
async def cb_back_to_menu(
    callback: CallbackQuery, db_user: dict, state: FSMContext
) -> None:
    await state.clear()
    if not db_user:
        await callback.answer("Could not load your profile.")
        return

    try:
        await callback.message.edit_text(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        await callback.message.answer(
            welcome_text(db_user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    await callback.answer()


# ── No-op ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
