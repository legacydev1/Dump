"""
rewards.py - Admin reward system management.
Configure point values for actions, view leaderboard, manually award points.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_reward_config, get_reward_action, update_reward_config,
    add_reward_action, award_points, get_reward_leaderboard,
    get_user, get_user_reward_history,
)
from keyboards.admin_kb import admin_rewards_kb, admin_reward_config_kb, confirm_kb
from states.states import AdminRewardStates
from utils.text_format import reward_config_text, leaderboard_text
from utils.helpers import escape_html, format_dt

logger = logging.getLogger(__name__)
router = Router(name="admin_rewards")


def _check(is_root_admin: bool, is_sub_admin: bool) -> bool:
    return is_root_admin or is_sub_admin


# ── List / Main ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_rewards")
async def cb_rewards_menu(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    configs = await get_reward_config()
    await callback.message.edit_text(
        reward_config_text(configs),
        reply_markup=admin_rewards_kb(configs),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Leaderboard ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reward_leaderboard")
async def cb_leaderboard(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    entries = await get_reward_leaderboard(limit=15)
    await callback.message.edit_text(
        leaderboard_text(entries),
        reply_markup=confirm_kb("admin_rewards", "admin_rewards"),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Config detail ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reward_config:"))
async def cb_reward_config(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    action_key = callback.data.split(":", 1)[1]
    cfg = await get_reward_action(action_key)
    if not cfg:
        # Also check inactive
        configs = await get_reward_config()
        cfg = next((c for c in configs if c["action_key"] == action_key), None)
    if not cfg:
        await callback.answer("⚠️ Action not found.", show_alert=True)
        return

    status = "✅ Active" if cfg.get("is_active") else "🔴 Inactive"
    text = (
        f"🎁 <b>Reward Action</b>\n\n"
        f"<b>Key:</b>         <code>{escape_html(cfg['action_key'])}</code>\n"
        f"<b>Description:</b> <b>{escape_html(cfg['description'])}</b>\n"
        f"<b>Points:</b>      <b>+{cfg['points']}</b>\n"
        f"<b>Status:</b>      <b>{status}</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_reward_config_kb(action_key),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Toggle action ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reward_toggle:"))
async def cb_reward_toggle(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    action_key = callback.data.split(":", 1)[1]
    configs = await get_reward_config()
    cfg = next((c for c in configs if c["action_key"] == action_key), None)
    if not cfg:
        await callback.answer("⚠️ Action not found.", show_alert=True)
        return

    new_state = not bool(cfg.get("is_active"))
    await update_reward_config(action_key, is_active=1 if new_state else 0)
    status = "✅ Enabled" if new_state else "🔴 Disabled"
    await callback.answer(status, show_alert=False)

    configs = await get_reward_config()
    await callback.message.edit_text(
        reward_config_text(configs),
        reply_markup=admin_rewards_kb(configs),
        parse_mode="HTML",
    )


# ── Edit action points ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reward_edit:"))
async def cb_reward_edit(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    action_key = callback.data.split(":", 1)[1]
    await state.set_state(AdminRewardStates.editing_value)
    await state.update_data(editing_action=action_key)
    await callback.message.edit_text(
        f"✏️ <b>Edit Reward Points</b>\n\n"
        f"<b>Action:</b> <code>{escape_html(action_key)}</code>\n\n"
        f"<b>Enter new point value (integer):</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminRewardStates.editing_value)
async def msg_reward_edit_value(message: Message, state: FSMContext) -> None:
    data       = await state.get_data()
    action_key = data["editing_action"]
    try:
        points = int((message.text or "").strip())
    except ValueError:
        await message.answer("⚠️ <b>Please enter a valid number.</b>", parse_mode="HTML")
        return

    await update_reward_config(action_key, points=points)
    await state.clear()
    await message.answer(
        f"✅ <b>Updated!</b> <code>{action_key}</code> → <b>+{points} pts</b>",
        parse_mode="HTML",
    )
    configs = await get_reward_config()
    await message.answer(
        reward_config_text(configs),
        reply_markup=admin_rewards_kb(configs),
        parse_mode="HTML",
    )


# ── Add new action ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reward_add")
async def cb_reward_add(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminRewardStates.waiting_for_action_key)
    await callback.message.edit_text(
        "🎁 <b>Add Reward Action</b>\n\n"
        "<b>Step 1/3:</b> Enter an <b>action key</b> (unique identifier).\n"
        "<i>e.g. daily_login, share_bot, first_search</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminRewardStates.waiting_for_action_key)
async def msg_reward_action_key(message: Message, state: FSMContext) -> None:
    key = (message.text or "").strip().lower().replace(" ", "_")
    if not key:
        await message.answer("⚠️ <b>Action key cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(new_action_key=key)
    await state.set_state(AdminRewardStates.waiting_for_description)
    await message.answer(
        "🎁 <b>Add Reward Action</b>\n\n"
        "<b>Step 2/3:</b> Enter a <b>description</b>.\n"
        "<i>e.g. User opens the bot daily</i>",
        parse_mode="HTML",
    )


@router.message(AdminRewardStates.waiting_for_description)
async def msg_reward_description(message: Message, state: FSMContext) -> None:
    desc = (message.text or "").strip()
    if not desc:
        await message.answer("⚠️ <b>Description cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(new_action_desc=desc)
    await state.set_state(AdminRewardStates.waiting_for_points)
    await message.answer(
        "🎁 <b>Add Reward Action</b>\n\n"
        "<b>Step 3/3:</b> Enter the <b>point value</b> (integer).\n"
        "<i>e.g. 10, 50, 100</i>",
        parse_mode="HTML",
    )


@router.message(AdminRewardStates.waiting_for_points)
async def msg_reward_points(message: Message, state: FSMContext) -> None:
    try:
        pts = int((message.text or "").strip())
    except ValueError:
        await message.answer("⚠️ <b>Please enter a valid number.</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    await state.clear()

    await add_reward_action(
        action_key=data["new_action_key"],
        description=data["new_action_desc"],
        points=pts,
    )
    await message.answer(
        f"✅ <b>Reward action added!</b>\n\n"
        f"<b>Key:</b>    <code>{data['new_action_key']}</code>\n"
        f"<b>Points:</b> <b>+{pts}</b>",
        parse_mode="HTML",
    )
    configs = await get_reward_config()
    await message.answer(
        reward_config_text(configs),
        reply_markup=admin_rewards_kb(configs),
        parse_mode="HTML",
    )


# ── Manual award ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "reward_award_manual")
async def cb_manual_award(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminRewardStates.waiting_for_user_id)
    await callback.message.edit_text(
        "🎁 <b>Manual Award Points</b>\n\n"
        "<b>Step 1/3:</b> Enter the <b>Telegram User ID</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminRewardStates.waiting_for_user_id)
async def msg_award_user_id(message: Message, state: FSMContext) -> None:
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("⚠️ <b>Invalid user ID.</b>", parse_mode="HTML")
        return

    user = await get_user(uid)
    if not user:
        await message.answer("⚠️ <b>User not found in database.</b>", parse_mode="HTML")
        return

    await state.update_data(award_user_id=uid)
    await state.set_state(AdminRewardStates.waiting_for_award_points)
    name = escape_html(user.get("first_name") or user.get("username") or str(uid))
    await message.answer(
        f"🎁 <b>Manual Award Points</b>\n\n"
        f"<b>User:</b> {name} (<code>{uid}</code>)\n\n"
        f"<b>Step 2/3:</b> Enter the <b>number of points</b> to award:",
        parse_mode="HTML",
    )


@router.message(AdminRewardStates.waiting_for_award_points)
async def msg_award_points(message: Message, state: FSMContext) -> None:
    try:
        pts = int((message.text or "").strip())
    except ValueError:
        await message.answer("⚠️ <b>Please enter a valid number.</b>", parse_mode="HTML")
        return

    await state.update_data(award_points_val=pts)
    await state.set_state(AdminRewardStates.waiting_for_award_note)
    await message.answer(
        "🎁 <b>Manual Award Points</b>\n\n"
        "<b>Step 3/3:</b> Enter a <b>note/reason</b>.\n"
        "Send <code>skip</code> to leave empty.",
        parse_mode="HTML",
    )


@router.message(AdminRewardStates.waiting_for_award_note)
async def msg_award_note(
    message: Message, state: FSMContext, is_root_admin: bool
) -> None:
    raw  = (message.text or "").strip()
    note = "" if raw.lower() == "skip" else raw

    data = await state.get_data()
    uid  = data["award_user_id"]
    pts  = data["award_points_val"]
    await state.clear()

    # Award via a manual admin action key
    from database.queries import db
    from datetime import datetime
    await db.execute(
        "INSERT INTO reward_transactions (user_id, action_key, points, note) VALUES (?, 'manual_award', ?, ?)",
        (uid, pts, note or "Admin award"),
    )
    await db.execute(
        "UPDATE users SET reward_points = reward_points + ? WHERE id = ?",
        (pts, uid),
    )
    await db.conn.commit()

    await message.answer(
        f"✅ <b>Points awarded!</b>\n\n"
        f"<b>User:</b>   <code>{uid}</code>\n"
        f"<b>Points:</b> <b>+{pts}</b>\n"
        f"<b>Note:</b>   {escape_html(note) if note else '<i>None</i>'}",
        parse_mode="HTML",
    )
    configs = await get_reward_config()
    await message.answer(
        reward_config_text(configs),
        reply_markup=admin_rewards_kb(configs),
        parse_mode="HTML",
    )
