"""
plans.py - Full plan CRUD: create, view, edit, delete.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    create_plan,
    delete_plan,
    get_all_plans,
    get_plan,
    update_plan,
)
from keyboards.admin_kb import (
    admin_main_kb,
    admin_plan_detail_kb,
    admin_plans_kb,
    confirm_kb,
    plan_edit_field_kb,
)
from states.states import AdminPlanStates

logger = logging.getLogger(__name__)
router = Router(name="admin_plans")


# ── Plan list ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_plans")
async def cb_plans_list(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    plans = await get_all_plans()
    await callback.message.edit_text(
        "📋 <b>Subscription Plans</b>\n\nSelect a plan to manage:",
        reply_markup=admin_plans_kb(plans),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Plan detail ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_plan_detail:"))
async def cb_plan_detail(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    plan_id = int(callback.data.split(":")[1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("Plan not found.", show_alert=True)
        return

    status = "✅ Active" if plan.get("is_active") else "❌ Inactive"
    text = (
        f"📦 <b>{plan['name']}</b>\n\n"
        f"Status: {status}\n"
        f"Daily Limit: <b>{plan['daily_search_limit']}</b> searches\n"
        f"Cooldown: <b>{plan['cooldown_seconds']}s</b>\n"
        f"Price: <b>${plan['price']:.2f}</b>\n"
        f"Duration: <b>{plan['duration_days']} days</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_plan_detail_kb(plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Create new plan ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_plan_new")
async def cb_new_plan_start(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    await state.set_state(AdminPlanStates.waiting_for_name)
    await callback.message.edit_text(
        "➕ <b>Create New Plan</b>\n\nEnter the plan <b>name</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminPlanStates.waiting_for_name)
async def msg_plan_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminPlanStates.waiting_for_limit)
    await message.answer("Enter <b>daily search limit</b> (integer):", parse_mode="HTML")


@router.message(AdminPlanStates.waiting_for_limit)
async def msg_plan_limit(message: Message, state: FSMContext) -> None:
    try:
        limit = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please enter a valid integer.")
        return
    await state.update_data(daily_search_limit=limit)
    await state.set_state(AdminPlanStates.waiting_for_cooldown)
    await message.answer("Enter <b>cooldown in seconds</b> (0 = no cooldown):", parse_mode="HTML")


@router.message(AdminPlanStates.waiting_for_cooldown)
async def msg_plan_cooldown(message: Message, state: FSMContext) -> None:
    try:
        cooldown = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please enter a valid integer.")
        return
    await state.update_data(cooldown_seconds=cooldown)
    await state.set_state(AdminPlanStates.waiting_for_price)
    await message.answer("Enter <b>price</b> (e.g. 9.99, use 0 for free):", parse_mode="HTML")


@router.message(AdminPlanStates.waiting_for_price)
async def msg_plan_price(message: Message, state: FSMContext) -> None:
    try:
        price = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please enter a valid number.")
        return
    await state.update_data(price=price)
    await state.set_state(AdminPlanStates.waiting_for_duration)
    await message.answer("Enter <b>duration in days</b> (0 = no expiry):", parse_mode="HTML")


@router.message(AdminPlanStates.waiting_for_duration)
async def msg_plan_duration(message: Message, state: FSMContext) -> None:
    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please enter a valid integer.")
        return

    data = await state.get_data()
    await state.clear()

    plan_id = await create_plan(
        name=data["name"],
        daily_search_limit=data["daily_search_limit"],
        cooldown_seconds=data["cooldown_seconds"],
        price=data["price"],
        duration_days=duration,
    )
    await message.answer(
        f"✅ Plan <b>{data['name']}</b> created (ID: {plan_id}).",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ── Edit plan ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_plan_edit:"))
async def cb_edit_plan(
    callback: CallbackQuery, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    plan_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "✏️ <b>Edit Plan</b>\n\nChoose the field to edit:",
        reply_markup=plan_edit_field_kb(plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_plan_edit_field:"))
async def cb_edit_plan_field(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    _, plan_id_str, field = callback.data.split(":")
    await state.set_state(AdminPlanStates.editing_value)
    await state.update_data(edit_plan_id=int(plan_id_str), edit_field=field)
    await callback.message.edit_text(
        f"✏️ Enter new value for <b>{field}</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminPlanStates.editing_value)
async def msg_plan_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    plan_id: int = data["edit_plan_id"]
    field: str = data["edit_field"]
    raw = message.text.strip()

    # Type coerce
    try:
        if field in ("daily_search_limit", "cooldown_seconds", "duration_days"):
            value = int(raw)
        elif field == "price":
            value = float(raw)
        else:
            value = raw
    except ValueError:
        await message.answer("⚠️ Invalid value. Please try again.")
        return

    await state.clear()
    await update_plan(plan_id, **{field: value})
    await message.answer(
        f"✅ Plan updated: <b>{field}</b> = <code>{value}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ── Delete plan ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_plan_delete:"))
async def cb_delete_plan_prompt(
    callback: CallbackQuery, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    plan_id = int(callback.data.split(":")[1])
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("Plan not found.", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ Delete plan <b>{plan['name']}</b>?\nThis will deactivate it (existing users keep access until expiry).",
        reply_markup=confirm_kb(f"admin_plan_confirm_delete:{plan_id}", "admin_plans"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_plan_confirm_delete:"))
async def cb_confirm_delete_plan(
    callback: CallbackQuery, is_root_admin: bool
) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    plan_id = int(callback.data.split(":")[1])
    await delete_plan(plan_id)
    await callback.message.edit_text(
        "✅ Plan deactivated.",
        reply_markup=confirm_kb("admin_plans", "admin_menu"),
    )
    await callback.answer("Plan deleted.")
