"""
emojis.py - Premium Emoji management handler.
Admin can add, edit, toggle, delete custom Telegram premium emojis.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_all_emojis, get_emoji, add_emoji,
    update_emoji, toggle_emoji, delete_emoji,
)
from keyboards.admin_kb import (
    admin_emojis_kb, admin_emoji_detail_kb,
    admin_emoji_edit_kb, confirm_kb,
)
from states.states import AdminEmojiStates
from utils.text_format import emoji_list_text, emoji_detail_text

logger = logging.getLogger(__name__)
router = Router(name="admin_emojis")

EMOJI_CATEGORIES = ["general", "status", "reward", "ui"]


def _check(is_root_admin: bool, is_sub_admin: bool) -> bool:
    return is_root_admin or is_sub_admin


# ── List ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_emojis")
async def cb_emoji_list(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    emojis = await get_all_emojis(active_only=False)
    await callback.message.edit_text(
        emoji_list_text(emojis),
        reply_markup=admin_emojis_kb(emojis),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Detail ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emoji_detail:"))
async def cb_emoji_detail(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    emoji_id = int(callback.data.split(":")[1])
    em = await get_emoji(emoji_id)
    if not em:
        await callback.answer("⚠️ Emoji not found.", show_alert=True)
        return

    await callback.message.edit_text(
        emoji_detail_text(em),
        reply_markup=admin_emoji_detail_kb(emoji_id, bool(em.get("is_active"))),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Toggle ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emoji_toggle:"))
async def cb_emoji_toggle(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    emoji_id = int(callback.data.split(":")[1])
    em = await get_emoji(emoji_id)
    if not em:
        await callback.answer("⚠️ Emoji not found.", show_alert=True)
        return

    new_state = not bool(em.get("is_active"))
    await toggle_emoji(emoji_id, new_state)
    status = "✅ Enabled" if new_state else "🔴 Disabled"
    await callback.answer(f"{status}", show_alert=False)

    # Refresh detail view
    em = await get_emoji(emoji_id)
    await callback.message.edit_text(
        emoji_detail_text(em),
        reply_markup=admin_emoji_detail_kb(emoji_id, new_state),
        parse_mode="HTML",
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emoji_delete:"))
async def cb_emoji_delete(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    emoji_id = int(callback.data.split(":")[1])
    em = await get_emoji(emoji_id)
    if not em:
        await callback.answer("⚠️ Emoji not found.", show_alert=True)
        return

    await delete_emoji(emoji_id)
    await callback.answer("🗑 Emoji deleted.", show_alert=False)

    emojis = await get_all_emojis(active_only=False)
    await callback.message.edit_text(
        emoji_list_text(emojis),
        reply_markup=admin_emojis_kb(emojis),
        parse_mode="HTML",
    )


# ── Add: Step 1 ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "emoji_add")
async def cb_emoji_add(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminEmojiStates.waiting_for_name)
    await callback.message.edit_text(
        "✨ <b>Add Premium Emoji</b>\n\n"
        "<b>Step 1/4:</b> Enter a <b>name</b> for this emoji.\n"
        "<i>e.g. fire, crown, check_green</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminEmojiStates.waiting_for_name)
async def msg_emoji_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("⚠️ <b>Name cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(emoji_name=name)
    await state.set_state(AdminEmojiStates.waiting_for_emoji_char)
    await message.answer(
        "✨ <b>Add Premium Emoji</b>\n\n"
        "<b>Step 2/4:</b> Send the <b>standard emoji character</b>.\n"
        "<i>e.g. 🔥 ✅ 💎</i>",
        parse_mode="HTML",
    )


@router.message(AdminEmojiStates.waiting_for_emoji_char)
async def msg_emoji_char(message: Message, state: FSMContext) -> None:
    char = (message.text or "").strip()
    if not char:
        await message.answer("⚠️ <b>Emoji character cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(emoji_char=char)
    await state.set_state(AdminEmojiStates.waiting_for_custom_emoji_id)
    await message.answer(
        "✨ <b>Add Premium Emoji</b>\n\n"
        "<b>Step 3/4:</b> Enter the <b>custom_emoji_id</b>.\n"
        "<i>e.g. 5382178536872223059</i>\n\n"
        "Send <code>skip</code> to leave empty.",
        parse_mode="HTML",
    )


@router.message(AdminEmojiStates.waiting_for_custom_emoji_id)
async def msg_emoji_custom_id(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    custom_id = "" if raw.lower() == "skip" else raw
    await state.update_data(custom_emoji_id=custom_id)
    await state.set_state(AdminEmojiStates.waiting_for_category)
    cats = " | ".join(f"<code>{c}</code>" for c in EMOJI_CATEGORIES)
    await message.answer(
        "✨ <b>Add Premium Emoji</b>\n\n"
        f"<b>Step 4/4:</b> Choose a <b>category</b>:\n{cats}",
        parse_mode="HTML",
    )


@router.message(AdminEmojiStates.waiting_for_category)
async def msg_emoji_category(
    message: Message, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    cat = (message.text or "").strip().lower()
    if cat not in EMOJI_CATEGORIES:
        cat = "general"

    data = await state.get_data()
    await state.clear()

    new_id = await add_emoji(
        name=data["emoji_name"],
        emoji_char=data["emoji_char"],
        custom_emoji_id=data.get("custom_emoji_id", ""),
        category=cat,
        added_by=message.from_user.id,
    )

    await message.answer(
        f"✅ <b>Emoji added!</b>\n\n"
        f"<b>Name:</b> {data['emoji_name']}\n"
        f"<b>Char:</b> {data['emoji_char']}\n"
        f"<b>Category:</b> {cat}\n"
        f"<b>ID:</b> #{new_id}",
        parse_mode="HTML",
    )
    emojis = await get_all_emojis(active_only=False)
    await message.answer(
        emoji_list_text(emojis),
        reply_markup=admin_emojis_kb(emojis),
        parse_mode="HTML",
    )


# ── Edit: field selection ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emoji_edit:"))
async def cb_emoji_edit(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    emoji_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "✨ <b>Edit Emoji</b>\n\n<b>Select a field to edit:</b>",
        reply_markup=admin_emoji_edit_kb(emoji_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("emoji_edit_field:"))
async def cb_emoji_edit_field(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    parts    = callback.data.split(":")
    emoji_id = int(parts[1])
    field    = parts[2]
    await state.set_state(AdminEmojiStates.editing_value)
    await state.update_data(editing_emoji_id=emoji_id, editing_field=field)

    await callback.message.edit_text(
        f"✏️ <b>Edit Emoji</b>\n\n"
        f"<b>Field:</b> <code>{field}</code>\n\n"
        f"<b>Send the new value:</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminEmojiStates.editing_value)
async def msg_emoji_edit_value(message: Message, state: FSMContext) -> None:
    data     = await state.get_data()
    emoji_id = data["editing_emoji_id"]
    field    = data["editing_field"]
    value    = (message.text or "").strip()

    if field == "sort_order":
        try:
            value = int(value)
        except ValueError:
            await message.answer("⚠️ <b>Sort order must be a number.</b>", parse_mode="HTML")
            return
    elif field == "is_active":
        value = 1 if value.lower() in ("1", "true", "yes", "on") else 0

    await update_emoji(emoji_id, **{field: value})
    await state.clear()

    em = await get_emoji(emoji_id)
    await message.answer(
        f"✅ <b>Updated!</b> <code>{field}</code> → <code>{value}</code>",
        parse_mode="HTML",
    )
    if em:
        await message.answer(
            emoji_detail_text(em),
            reply_markup=admin_emoji_detail_kb(emoji_id, bool(em.get("is_active"))),
            parse_mode="HTML",
        )
