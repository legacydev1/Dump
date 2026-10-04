"""
users.py - User management: paginated list, ban/unban, plan assignment, sub-admins.
"""

from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    add_admin,
    assign_plan,
    ban_user,
    get_active_plans,
    get_all_admins,
    get_all_users_paginated,
    get_plan,
    get_user_with_plan,
    count_users,
    remove_admin,
)
from keyboards.admin_kb import (
    admin_main_kb,
    admin_subadmins_kb,
    admin_user_detail_kb,
    admin_users_kb,
    admin_assign_plan_kb,
    confirm_kb,
)
from states.states import AdminUserStates, AdminSubAdminStates

logger = logging.getLogger(__name__)
router = Router(name="admin_users")

_PER_PAGE = 20


# ── User list ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
async def cb_users_list(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return
    await _show_users_page(callback, offset=0)


@router.callback_query(F.data.startswith("admin_users_page:"))
async def cb_users_page(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return
    offset = int(callback.data.split(":")[1])
    await _show_users_page(callback, offset=offset)


async def _show_users_page(callback: CallbackQuery, offset: int) -> None:
    total = await count_users()
    users = await get_all_users_paginated(offset=offset, limit=_PER_PAGE)
    await callback.message.edit_text(
        f"👥 <b>Users</b> (total: {total})\n\nPage {offset // _PER_PAGE + 1}:",
        reply_markup=admin_users_kb(users, offset, total),
        parse_mode="HTML",
    )
    await callback.answer()


# ── User detail ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_user_detail:"))
async def cb_user_detail(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    user = await get_user_with_plan(user_id)
    if not user:
        await callback.answer("User not found.", show_alert=True)
        return

    name = user.get("username") or user.get("first_name") or str(user_id)
    plan_name = user.get("plan_name") or "None"
    expires = user.get("plan_expires_at") or "N/A"
    banned = "🚫 Banned" if user.get("is_banned") else "✅ Active"

    text = (
        f"👤 <b>User: @{name}</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Status: {banned}\n"
        f"Plan: <b>{plan_name}</b>\n"
        f"Expires: {expires}\n"
        f"Daily Searches: {user.get('daily_searches', 0)}\n"
        f"Registered: {user.get('created_at', 'N/A')}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_user_detail_kb(user_id, bool(user.get("is_banned"))),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Ban / Unban ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_ban:"))
async def cb_ban_user(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    await ban_user(user_id, banned=True)
    await callback.answer("✅ User banned.")
    # Refresh detail view
    callback.data = f"admin_user_detail:{user_id}"
    await cb_user_detail(callback, is_root_admin, is_sub_admin)


@router.callback_query(F.data.startswith("admin_unban:"))
async def cb_unban_user(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    await ban_user(user_id, banned=False)
    await callback.answer("✅ User unbanned.")
    callback.data = f"admin_user_detail:{user_id}"
    await cb_user_detail(callback, is_root_admin, is_sub_admin)


# ── Assign plan ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_assign_plan:"))
async def cb_assign_plan_menu(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    plans = await get_active_plans()
    await callback.message.edit_text(
        f"💳 Choose a plan to assign to user <code>{user_id}</code>:",
        reply_markup=admin_assign_plan_kb(plans, user_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_do_assign:"))
async def cb_do_assign_plan(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    _, user_id_str, plan_id_str = callback.data.split(":")
    user_id = int(user_id_str)
    plan_id = int(plan_id_str)
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("Plan not found.", show_alert=True)
        return

    await assign_plan(user_id, plan_id, plan["duration_days"])
    await callback.answer(f"✅ Plan '{plan['name']}' assigned.")

    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 Your plan has been updated to <b>{plan['name']}</b>!",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Could not notify user %s of plan assignment: %s", user_id, e)

    await callback.message.edit_text(
        f"✅ Plan <b>{plan['name']}</b> assigned to user <code>{user_id}</code>.",
        reply_markup=confirm_kb(f"admin_user_detail:{user_id}", "admin_users"),
        parse_mode="HTML",
    )


# ── Sub-Admin management ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_subadmins")
async def cb_subadmins(callback: CallbackQuery, is_root_admin: bool) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    admins = await get_all_admins()
    await callback.message.edit_text(
        f"👮 <b>Sub-Admins</b> ({len(admins)} total)\n\nManage sub-admin access:",
        reply_markup=admin_subadmins_kb(admins),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_subadmin")
async def cb_add_subadmin_start(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    await state.set_state(AdminSubAdminStates.waiting_for_user_id)
    await callback.message.edit_text(
        "👮 <b>Add Sub-Admin</b>\n\nEnter the Telegram <b>user ID</b> to promote:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminSubAdminStates.waiting_for_user_id)
async def msg_subadmin_user_id(message: Message, state: FSMContext) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Invalid user ID. Please enter a number.")
        return

    await state.update_data(sub_admin_id=uid)
    await state.set_state(AdminSubAdminStates.waiting_for_privileges)
    await message.answer(
        "Enter privileges as a comma-separated list, or <code>all</code> for full access.\n\n"
        "Available: <code>ingest, plans, users, groups, broadcast, payments</code>",
        parse_mode="HTML",
    )


@router.message(AdminSubAdminStates.waiting_for_privileges)
async def msg_subadmin_privileges(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw.lower() == "all":
        privs = ["all"]
    else:
        privs = [p.strip() for p in raw.split(",") if p.strip()]

    data = await state.get_data()
    uid: int = data["sub_admin_id"]
    await state.clear()

    await add_admin(uid, privs, message.from_user.id)
    await message.answer(
        f"✅ User <code>{uid}</code> added as sub-admin with privileges: <code>{privs}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data.startswith("admin_remove_subadmin:"))
async def cb_remove_subadmin(callback: CallbackQuery, is_root_admin: bool) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    uid = int(callback.data.split(":")[1])
    await remove_admin(uid)
    await callback.answer(f"✅ Sub-admin {uid} removed.")
    # Refresh
    admins = await get_all_admins()
    await callback.message.edit_text(
        f"👮 <b>Sub-Admins</b> ({len(admins)} total)",
        reply_markup=admin_subadmins_kb(admins),
        parse_mode="HTML",
    )
