"""
reading.py - Admin reading system management.
View reading stats, browse all reading logs, look up user-specific reading history.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_reading_stats, get_all_reading_logs_paginated,
    get_user_reading_history, count_user_reads, get_user, count_users,
)
from keyboards.admin_kb import admin_reading_kb, admin_reading_nav_kb, confirm_kb
from states.states import AdminReadingStates
from utils.text_format import reading_stats_text
from utils.helpers import escape_html, format_dt, truncate

logger = logging.getLogger(__name__)
router = Router(name="admin_reading")

_PER_PAGE = 10


def _check(is_root_admin: bool, is_sub_admin: bool) -> bool:
    return is_root_admin or is_sub_admin


# ── Main Menu ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_reading")
async def cb_reading_menu(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await callback.message.edit_text(
        "📖 <b>Reading System Management</b>\n\n"
        "<b>Track which records users have viewed.</b>",
        reply_markup=admin_reading_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reading_stats")
async def cb_reading_stats(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    stats = await get_reading_stats()
    user_count = await count_users()
    await callback.message.edit_text(
        reading_stats_text(stats, user_count),
        reply_markup=confirm_kb("admin_reading", "admin_reading"),
        parse_mode="HTML",
    )
    await callback.answer()


# ── All reading logs (paginated) ──────────────────────────────────────────────

@router.callback_query(F.data == "reading_all_logs")
async def cb_reading_all_logs(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await _show_reading_page(callback, offset=0)


@router.callback_query(F.data.startswith("reading_page:"))
async def cb_reading_page(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    offset = int(callback.data.split(":")[1])
    await _show_reading_page(callback, offset=offset)


async def _show_reading_page(callback: CallbackQuery, offset: int) -> None:
    records = await get_all_reading_logs_paginated(offset=offset, limit=_PER_PAGE)
    stats   = await get_reading_stats()
    total   = stats.get("total_reads", 0)

    if not records:
        await callback.message.edit_text(
            "📖 <b>Reading Logs</b>\n\n<b>No reading records yet.</b>",
            reply_markup=admin_reading_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = [
        f"📖 <b>Reading Logs</b> (showing {offset+1}–{offset+len(records)} of <b>{total}</b>)\n",
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>",
    ]
    for r in records:
        username = escape_html(r.get("username") or r.get("first_name") or str(r["user_id"]))
        query    = escape_html(r.get("query") or "")
        text     = escape_html(truncate(r.get("record_text") or "", 60))
        dt       = format_dt(r.get("read_at"), "%d %b %H:%M")
        lines.append(
            f"👤 <b>{username}</b> — 🔍 <code>{query}</code>\n"
            f"   <code>{text}</code>\n"
            f"   📅 <i>{dt}</i>\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_reading_nav_kb(offset, total, _PER_PAGE),
        parse_mode="HTML",
    )
    await callback.answer()


# ── User reading history lookup ───────────────────────────────────────────────

@router.callback_query(F.data == "reading_user_lookup")
async def cb_reading_user_lookup(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminReadingStates.viewing_user_history)
    await callback.message.edit_text(
        "📖 <b>User Reading History</b>\n\n"
        "<b>Enter the Telegram User ID:</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminReadingStates.viewing_user_history)
async def msg_reading_user_id(
    message: Message, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    await state.clear()
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("⚠️ <b>Invalid user ID.</b>", parse_mode="HTML")
        return

    user = await get_user(uid)
    if not user:
        await message.answer("⚠️ <b>User not found.</b>", parse_mode="HTML")
        return

    history = await get_user_reading_history(uid, limit=15)
    total   = await count_user_reads(uid)
    name    = escape_html(user.get("first_name") or user.get("username") or str(uid))

    if not history:
        await message.answer(
            f"📖 <b>{name}</b> has no reading history.",
            parse_mode="HTML",
        )
        return

    lines = [
        f"📖 <b>Reading History: {name}</b>\n"
        f"<b>Total reads: {total}</b>\n",
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>",
    ]
    for i, r in enumerate(history, 1):
        query = escape_html(r.get("query") or "")
        text  = escape_html(truncate(r.get("record_text") or "", 70))
        dt    = format_dt(r.get("read_at"), "%d %b %Y %H:%M")
        lines.append(
            f"<b>{i}.</b> 🔍 <code>{query}</code>\n"
            f"   <code>{text}</code>\n"
            f"   📅 <i>{dt}</i>\n"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")
