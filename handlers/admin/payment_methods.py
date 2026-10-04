"""
payment_methods.py - Admin payment method management.
Admin adds payment methods (bKash, Nagad, USDT, etc.) that users see during payment.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_all_payment_methods, get_payment_method,
    add_payment_method, update_payment_method,
    toggle_payment_method, delete_payment_method,
)
from keyboards.admin_kb import (
    admin_payment_methods_kb, admin_pm_detail_kb,
    admin_pm_edit_kb, confirm_kb,
)
from states.states import AdminPaymentMethodStates
from utils.text_format import payment_methods_list_text, payment_method_detail_text

logger = logging.getLogger(__name__)
router = Router(name="admin_payment_methods")


def _check(is_root_admin: bool, is_sub_admin: bool) -> bool:
    return is_root_admin or is_sub_admin


# ── List ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_payment_methods")
async def cb_methods_list(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    methods = await get_all_payment_methods(active_only=False)
    await callback.message.edit_text(
        payment_methods_list_text(methods),
        reply_markup=admin_payment_methods_kb(methods),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Detail ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pm_detail:"))
async def cb_pm_detail(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    method_id = int(callback.data.split(":")[1])
    m = await get_payment_method(method_id)
    if not m:
        await callback.answer("⚠️ Method not found.", show_alert=True)
        return

    await callback.message.edit_text(
        payment_method_detail_text(m),
        reply_markup=admin_pm_detail_kb(method_id, bool(m.get("is_active"))),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Toggle ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pm_toggle:"))
async def cb_pm_toggle(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    method_id = int(callback.data.split(":")[1])
    m = await get_payment_method(method_id)
    if not m:
        await callback.answer("⚠️ Method not found.", show_alert=True)
        return

    new_state = not bool(m.get("is_active"))
    await toggle_payment_method(method_id, new_state)
    status = "✅ Enabled" if new_state else "🔴 Disabled"
    await callback.answer(status, show_alert=False)

    m = await get_payment_method(method_id)
    await callback.message.edit_text(
        payment_method_detail_text(m),
        reply_markup=admin_pm_detail_kb(method_id, new_state),
        parse_mode="HTML",
    )


# ── Delete ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pm_delete:"))
async def cb_pm_delete(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    method_id = int(callback.data.split(":")[1])
    await delete_payment_method(method_id)
    await callback.answer("🗑 Payment method deleted.", show_alert=False)

    methods = await get_all_payment_methods(active_only=False)
    await callback.message.edit_text(
        payment_methods_list_text(methods),
        reply_markup=admin_payment_methods_kb(methods),
        parse_mode="HTML",
    )


# ── Add: Step 1 — Name ────────────────────────────────────────────────────────

@router.callback_query(F.data == "pm_add")
async def cb_pm_add(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.set_state(AdminPaymentMethodStates.waiting_for_name)
    await callback.message.edit_text(
        "💳 <b>Add Payment Method</b>\n\n"
        "<b>Step 1/4:</b> Enter the <b>method name</b>.\n"
        "<i>e.g. bKash, Nagad, USDT TRC20, Binance Pay</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminPaymentMethodStates.waiting_for_name)
async def msg_pm_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("⚠️ <b>Name cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(pm_name=name)
    await state.set_state(AdminPaymentMethodStates.waiting_for_account_info)
    await message.answer(
        "💳 <b>Add Payment Method</b>\n\n"
        "<b>Step 2/4:</b> Enter the <b>account number / wallet address / instructions</b>.\n"
        "<i>This will be shown to the user during payment.</i>",
        parse_mode="HTML",
    )


@router.message(AdminPaymentMethodStates.waiting_for_account_info)
async def msg_pm_account(message: Message, state: FSMContext) -> None:
    account = (message.text or "").strip()
    if not account:
        await message.answer("⚠️ <b>Account info cannot be empty.</b>", parse_mode="HTML")
        return
    await state.update_data(pm_account=account)
    await state.set_state(AdminPaymentMethodStates.waiting_for_emoji)
    await message.answer(
        "💳 <b>Add Payment Method</b>\n\n"
        "<b>Step 3/4:</b> Send an <b>emoji</b> for this method.\n"
        "<i>e.g. 💳 🟢 💰 🏦</i>\n\n"
        "Send <code>skip</code> to use 💳",
        parse_mode="HTML",
    )


@router.message(AdminPaymentMethodStates.waiting_for_emoji)
async def msg_pm_emoji(message: Message, state: FSMContext) -> None:
    raw   = (message.text or "").strip()
    emoji = "💳" if raw.lower() == "skip" else raw
    await state.update_data(pm_emoji=emoji)
    await state.set_state(AdminPaymentMethodStates.waiting_for_description)
    await message.answer(
        "💳 <b>Add Payment Method</b>\n\n"
        "<b>Step 4/4:</b> Enter a <b>description</b> (optional extra instructions).\n"
        "Send <code>skip</code> to leave empty.",
        parse_mode="HTML",
    )


@router.message(AdminPaymentMethodStates.waiting_for_description)
async def msg_pm_description(
    message: Message, state: FSMContext
) -> None:
    raw  = (message.text or "").strip()
    desc = "" if raw.lower() == "skip" else raw

    data = await state.get_data()
    await state.clear()

    new_id = await add_payment_method(
        name=data["pm_name"],
        account_info=data["pm_account"],
        emoji=data.get("pm_emoji", "💳"),
        description=desc,
        added_by=message.from_user.id,
    )

    await message.answer(
        f"✅ <b>Payment method added!</b>\n\n"
        f"<b>Name:</b>    {data['pm_name']}\n"
        f"<b>Account:</b> <code>{data['pm_account']}</code>\n"
        f"<b>ID:</b>      #{new_id}",
        parse_mode="HTML",
    )
    methods = await get_all_payment_methods(active_only=False)
    await message.answer(
        payment_methods_list_text(methods),
        reply_markup=admin_payment_methods_kb(methods),
        parse_mode="HTML",
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pm_edit:"))
async def cb_pm_edit(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    method_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "💳 <b>Edit Payment Method</b>\n\n<b>Select a field to edit:</b>",
        reply_markup=admin_pm_edit_kb(method_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pm_edit_field:"))
async def cb_pm_edit_field(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    parts     = callback.data.split(":")
    method_id = int(parts[1])
    field     = parts[2]
    await state.set_state(AdminPaymentMethodStates.editing_value)
    await state.update_data(editing_pm_id=method_id, editing_field=field)
    await callback.message.edit_text(
        f"✏️ <b>Edit Payment Method</b>\n\n"
        f"<b>Field:</b> <code>{field}</code>\n\n"
        f"<b>Send the new value:</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminPaymentMethodStates.editing_value)
async def msg_pm_edit_value(message: Message, state: FSMContext) -> None:
    data      = await state.get_data()
    method_id = data["editing_pm_id"]
    field     = data["editing_field"]
    value     = (message.text or "").strip()

    if field == "sort_order":
        try:
            value = int(value)
        except ValueError:
            await message.answer("⚠️ <b>Sort order must be a number.</b>", parse_mode="HTML")
            return

    await update_payment_method(method_id, **{field: value})
    await state.clear()

    m = await get_payment_method(method_id)
    await message.answer(
        f"✅ <b>Updated!</b> <code>{field}</code> → <code>{value}</code>",
        parse_mode="HTML",
    )
    if m:
        await message.answer(
            payment_method_detail_text(m),
            reply_markup=admin_pm_detail_kb(method_id, bool(m.get("is_active"))),
            parse_mode="HTML",
        )
