"""
reading.py - User reading history: view, paginate, clear.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.queries import (
    get_user_reading_history, count_user_reads, delete_user_reading_history,
)
from keyboards.user_kb import reading_history_kb, back_kb
from utils.text_format import reading_history_text

logger = logging.getLogger(__name__)
router = Router(name="reading")

_PER_PAGE = 10


@router.callback_query(F.data == "menu_reading")
async def cb_reading(callback: CallbackQuery, db_user: dict) -> None:
    uid     = db_user["id"]
    total   = await count_user_reads(uid)
    records = await get_user_reading_history(uid, limit=_PER_PAGE, offset=0)

    await callback.message.edit_text(
        reading_history_text(records, offset=0),
        reply_markup=reading_history_kb(0, total, _PER_PAGE),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("read_hist_page:"))
async def cb_reading_page(callback: CallbackQuery, db_user: dict) -> None:
    offset  = int(callback.data.split(":")[1])
    uid     = db_user["id"]
    total   = await count_user_reads(uid)
    records = await get_user_reading_history(uid, limit=_PER_PAGE, offset=offset)

    await callback.message.edit_text(
        reading_history_text(records, offset=offset),
        reply_markup=reading_history_kb(offset, total, _PER_PAGE),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "reading_clear")
async def cb_reading_clear(callback: CallbackQuery, db_user: dict) -> None:
    uid     = db_user["id"]
    deleted = await delete_user_reading_history(uid)
    await callback.answer(f"🗑 Cleared {deleted} records.", show_alert=False)
    await callback.message.edit_text(
        "📖 <b>Reading History</b>\n\n<b>Your history has been cleared.</b>",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )
