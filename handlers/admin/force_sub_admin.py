"""
force_sub_admin.py - Admin panel: full control over force-subscribe channels.

Features:
  • View all configured channels with status (active / disabled)
  • Add a channel by @username or numeric ID
  • Toggle a channel on/off without deleting it
  • Refresh cached title & invite link from Telegram
  • Delete a channel permanently (with confirmation)
  • Inline stats: member count shown on each channel
  • Every change invalidates the middleware cache immediately
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    add_force_sub_channel,
    delete_force_sub_channel,
    get_force_sub_channel,
    get_force_sub_channels,
    toggle_force_sub_channel,
    update_force_sub_channel_info,
)
from keyboards.admin_kb import (
    admin_force_sub_delete_kb,
    admin_force_sub_detail_kb,
    admin_force_sub_main_kb,
    admin_main_kb,
    confirm_kb,
)
from middlewares.force_sub import invalidate_cache
from states.states import AdminForceSub

logger = logging.getLogger(__name__)
router = Router(name="admin_force_sub")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_channel_info(bot: Bot, chat_id: str) -> tuple[str, str]:
    """
    Fetch live title and invite link for a channel/group.
    Returns (title, invite_link). Falls back to chat_id on error.
    """
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or chat.username or chat_id
        link  = chat.invite_link or (
            f"https://t.me/{chat.username}" if chat.username else ""
        )
        return title, link
    except Exception as e:
        logger.warning("Could not fetch chat info for %s: %s", chat_id, e)
        return chat_id, ""


async def _channel_list_text(channels: list) -> str:
    total   = len(channels)
    active  = sum(1 for c in channels if c.get("is_active"))
    disabled = total - active
    lines = [
        "📡 <b>Force-Subscribe Channels</b>\n",
        f"Total: <b>{total}</b>  |  Active: <b>{active}</b>  |  Off: <b>{disabled}</b>\n",
        "─" * 32,
    ]
    if not channels:
        lines.append("\n⚠️ No channels configured.\nTap ➕ Add Channel to get started.")
    else:
        for ch in channels:
            status = "✅ ON " if ch.get("is_active") else "🔴 OFF"
            title  = ch.get("title") or ch["chat_id"]
            lines.append(f"\n{status}  <code>{ch['chat_id']}</code>  —  {title}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main force-sub list screen
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_force_sub")
async def cb_force_sub_list(
    callback: CallbackQuery,
    state: FSMContext,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.clear()
    channels = await get_force_sub_channels(active_only=False)
    text = await _channel_list_text(channels)

    await callback.message.edit_text(
        text,
        reply_markup=admin_force_sub_main_kb(channels),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Channel detail
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fsub_detail:"))
async def cb_force_sub_detail(
    callback: CallbackQuery,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    ch = await get_force_sub_channel(ch_id)
    if not ch:
        await callback.answer("Channel not found.", show_alert=True)
        return

    status     = "✅ Active" if ch.get("is_active") else "🔴 Disabled"
    title      = ch.get("title") or ch["chat_id"]
    invite     = ch.get("invite_link") or "—"
    added_by   = ch.get("added_by") or "system"
    created_at = ch.get("created_at", "")[:10]

    text = (
        f"📡 <b>Channel Details</b>\n\n"
        f"ID/Username: <code>{ch['chat_id']}</code>\n"
        f"Title:       <b>{title}</b>\n"
        f"Status:      {status}\n"
        f"Invite Link: {invite}\n"
        f"Added by:    <code>{added_by}</code>\n"
        f"Added on:    {created_at}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_force_sub_detail_kb(ch_id, bool(ch.get("is_active"))),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Add channel — step 1: prompt
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fsub_add")
async def cb_force_sub_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminForceSub.waiting_for_channel_id)
    await callback.message.edit_text(
        "➕ <b>Add Force-Subscribe Channel</b>\n\n"
        "Send the channel <b>@username</b> or numeric <b>ID</b>.\n\n"
        "Examples:\n"
        "  <code>@MyChannel</code>\n"
        "  <code>-1001234567890</code>\n\n"
        "⚠️ Make sure the bot is an <b>admin</b> of the channel "
        "(so it can fetch the invite link).",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_force_sub", "admin_force_sub"),
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Add channel — step 2: receive input, fetch info, save
# ─────────────────────────────────────────────────────────────────────────────

@router.message(AdminForceSub.waiting_for_channel_id)
async def msg_force_sub_channel_id(
    message: Message,
    state: FSMContext,
    bot: Bot,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        return

    raw = (message.text or "").strip()
    if not raw:
        await message.answer("⚠️ Please send a valid @username or numeric ID.")
        return

    # Normalise: if numeric without @, keep as-is; else ensure @ prefix
    chat_id = raw if raw.lstrip("-").isdigit() else (
        raw if raw.startswith("@") else f"@{raw}"
    )

    status_msg = await message.answer(
        f"🔍 Fetching info for <code>{chat_id}</code>…", parse_mode="HTML"
    )

    title, invite_link = await _fetch_channel_info(bot, chat_id)

    row_id = await add_force_sub_channel(
        chat_id=chat_id,
        title=title,
        invite_link=invite_link,
        added_by=message.from_user.id,
    )

    # Invalidate the middleware cache so the new channel takes effect immediately
    invalidate_cache()
    await state.clear()

    await status_msg.edit_text(
        f"✅ <b>Channel Added</b>\n\n"
        f"ID:    <code>{chat_id}</code>\n"
        f"Title: <b>{title}</b>\n"
        f"Link:  {invite_link or '—'}\n\n"
        "Force-subscribe is now active for this channel.",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Toggle active / disabled
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fsub_toggle:"))
async def cb_force_sub_toggle(
    callback: CallbackQuery,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    ch = await get_force_sub_channel(ch_id)
    if not ch:
        await callback.answer("Channel not found.", show_alert=True)
        return

    new_state = not bool(ch.get("is_active"))
    await toggle_force_sub_channel(ch_id, new_state)
    invalidate_cache()

    label = "✅ Enabled" if new_state else "🔴 Disabled"
    await callback.answer(f"{label}: {ch.get('title') or ch['chat_id']}")

    # Refresh the list view
    channels = await get_force_sub_channels(active_only=False)
    text = await _channel_list_text(channels)
    await callback.message.edit_text(
        text,
        reply_markup=admin_force_sub_main_kb(channels),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Refresh single channel info from Telegram
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fsub_refresh:"))
async def cb_force_sub_refresh(
    callback: CallbackQuery,
    bot: Bot,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    ch = await get_force_sub_channel(ch_id)
    if not ch:
        await callback.answer("Channel not found.", show_alert=True)
        return

    title, invite_link = await _fetch_channel_info(bot, ch["chat_id"])
    await update_force_sub_channel_info(ch_id, title, invite_link)
    invalidate_cache()
    await callback.answer(f"✅ Refreshed: {title}")

    # Re-show detail
    callback.data = f"fsub_detail:{ch_id}"
    await cb_force_sub_detail(callback, is_root_admin, is_sub_admin)


# ─────────────────────────────────────────────────────────────────────────────
# Refresh ALL channels
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fsub_refresh_all")
async def cb_force_sub_refresh_all(
    callback: CallbackQuery,
    bot: Bot,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await callback.answer("🔄 Refreshing all channels…")
    channels = await get_force_sub_channels(active_only=False)
    updated = 0
    for ch in channels:
        try:
            title, link = await _fetch_channel_info(bot, ch["chat_id"])
            await update_force_sub_channel_info(ch["id"], title, link)
            updated += 1
        except Exception as e:
            logger.warning("Refresh failed for %s: %s", ch["chat_id"], e)

    invalidate_cache()
    channels = await get_force_sub_channels(active_only=False)
    text = await _channel_list_text(channels)
    await callback.message.edit_text(
        text + f"\n\n✅ Refreshed <b>{updated}</b> channel(s).",
        reply_markup=admin_force_sub_main_kb(channels),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Delete channel — confirmation prompt
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fsub_delete_prompt:"))
async def cb_force_sub_delete_prompt(
    callback: CallbackQuery,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    ch = await get_force_sub_channel(ch_id)
    if not ch:
        await callback.answer("Channel not found.", show_alert=True)
        return

    title = ch.get("title") or ch["chat_id"]
    await callback.message.edit_text(
        f"🗑 <b>Delete Channel?</b>\n\n"
        f"<code>{ch['chat_id']}</code>  —  {title}\n\n"
        "This will permanently remove it from the force-subscribe list.\n"
        "Users will no longer need to join this channel.",
        reply_markup=admin_force_sub_delete_kb(ch_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Delete channel — confirmed
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fsub_delete:"))
async def cb_force_sub_delete(
    callback: CallbackQuery,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    ch = await get_force_sub_channel(ch_id)
    title = (ch.get("title") or ch["chat_id"]) if ch else str(ch_id)

    await delete_force_sub_channel(ch_id)
    invalidate_cache()
    await callback.answer(f"✅ Deleted: {title}")

    # Return to list
    channels = await get_force_sub_channels(active_only=False)
    text = await _channel_list_text(channels)
    await callback.message.edit_text(
        text,
        reply_markup=admin_force_sub_main_kb(channels),
        parse_mode="HTML",
    )
