"""
plan.py - User active plan info.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards.user_kb import back_kb
from utils.text_format import plan_info_text

router = Router(name="plan")


@router.callback_query(F.data == "menu_plan")
async def cb_plan_info(callback: CallbackQuery, db_user: dict) -> None:
    await callback.message.edit_text(
        plan_info_text(db_user),
        reply_markup=back_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
