"""
rewards.py - User-facing reward system: view points, history, leaderboard.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.queries import (
    get_user_reward_history, get_reward_leaderboard,
)
from keyboards.user_kb import rewards_kb, rewards_history_kb, back_kb
from utils.text_format import rewards_text, rewards_history_text, leaderboard_text

logger = logging.getLogger(__name__)
router = Router(name="rewards")

_PER_PAGE = 10


@router.callback_query(F.data == "menu_rewards")
async def cb_rewards(callback: CallbackQuery, db_user: dict) -> None:
    await callback.message.edit_text(
        rewards_text(db_user),
        reply_markup=rewards_kb(db_user.get("reward_points", 0)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "rewards_history")
async def cb_rewards_history(callback: CallbackQuery, db_user: dict) -> None:
    uid     = db_user["id"]
    history = await get_user_reward_history(uid, limit=_PER_PAGE)
    await callback.message.edit_text(
        rewards_history_text(history, offset=0),
        reply_markup=rewards_history_kb(0, len(history), _PER_PAGE),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rewards_hist_page:"))
async def cb_rewards_hist_page(callback: CallbackQuery, db_user: dict) -> None:
    offset  = int(callback.data.split(":")[1])
    uid     = db_user["id"]
    history = await get_user_reward_history(uid, limit=_PER_PAGE)
    await callback.message.edit_text(
        rewards_history_text(history, offset=offset),
        reply_markup=rewards_history_kb(offset, len(history), _PER_PAGE),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "rewards_leaderboard")
async def cb_leaderboard(callback: CallbackQuery) -> None:
    entries = await get_reward_leaderboard(limit=10)
    await callback.message.edit_text(
        leaderboard_text(entries),
        reply_markup=back_kb("menu_rewards"),
        parse_mode="HTML",
    )
    await callback.answer()
