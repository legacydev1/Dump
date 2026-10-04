"""
groups.py - Whitelist/blacklist Telegram groups where the bot is allowed to respond.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import add_group, get_allowed_groups, remove_group
from keyboards.admin_kb import admin_groups_kb, admin_main_kb, confirm_kb
from states.states import AdminGroupStates

logger = logging.getLogger(__name__)
router = Router(name="admin_groups")


@router.callback_query(F.data == "admin_groups")
async def cb_groups_list(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    groups = await get_allowed_groups()
    await callback.message.edit_text(
        f"💬 <b>Allowed Groups</b> ({len(groups)} active)\n\n"
        "The bot only responds in whitelisted groups.\n"
        "Add or remove groups below:",
        reply_markup=admin_groups_kb(groups),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_group_add")
async def cb_add_group_start(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminGroupStates.waiting_for_chat_id)
    await callback.message.edit_text(
        "➕ <b>Add Allowed Group</b>\n\n"
        "Send the group's numeric chat ID (e.g. <code>-1001234567890</code>).\n\n"
        "Tip: Forward any message from the group to @userinfobot to get its ID.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminGroupStates.waiting_for_chat_id)
async def msg_add_group(
    message: Message, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        return

    raw = message.text.strip() if message.text else ""
    try:
        chat_id = int(raw)
    except ValueError:
        await message.answer("⚠️ Invalid chat ID. Please enter a numeric ID.")
        return

    # Try to get chat info for the title
    title = str(chat_id)
    try:
        chat = await message.bot.get_chat(chat_id)
        title = chat.title or title
    except Exception as e:
        logger.warning("Could not fetch chat info for %s: %s", chat_id, e)

    await state.clear()
    await add_group(chat_id, title, message.from_user.id)
    await message.answer(
        f"✅ Group <b>{title}</b> (<code>{chat_id}</code>) added to whitelist.",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data.startswith("admin_remove_group:"))
async def cb_remove_group(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    chat_id = int(callback.data.split(":")[1])
    await remove_group(chat_id)
    await callback.answer(f"✅ Group {chat_id} removed from whitelist.")

    # Refresh the list
    groups = await get_allowed_groups()
    await callback.message.edit_text(
        f"💬 <b>Allowed Groups</b> ({len(groups)} active)",
        reply_markup=admin_groups_kb(groups),
        parse_mode="HTML",
    )
