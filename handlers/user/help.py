"""
help.py - Help and FAQ handler.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from keyboards.user_kb import back_kb
from utils.text_format import help_text

router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        help_text(),
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu_help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        help_text(),
        reply_markup=back_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
