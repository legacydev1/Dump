"""
payment.py - Complete plan purchase flow.

Flow:
  1. /menu_payment  → Plan list
  2. select_plan:ID → Payment method list (admin-configured)
  3. pay_method:P:M → Payment instructions (account info shown)
  4. send_receipt:P → Ask for Transaction ID (text)
  5. FSM: waiting_for_txn_id  → Save txn_id, ask for screenshot
  6. FSM: waiting_for_receipt → Save screenshot, submit request
  7. Admin gets notification → Approve / Reject
  8. User gets notification on approval/rejection
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database.queries import (
    create_payment_request, get_active_plans,
    get_plan, get_all_payment_methods, get_payment_method,
)
from keyboards.user_kb import back_kb, payment_method_kb, plan_list_kb
from keyboards.admin_kb import payment_review_kb
from states.states import PaymentStates
from utils.text_format import payment_instructions_text, DIV, DIV2, DIV3
from utils.text_format import E_CHECK, E_MONEY, E_DIAMOND, E_CALENDAR, E_BANK
from utils.text_format import E_STAR, E_FIRE, E_SNOWFLAKE, E_CROWN
from utils.unicode_style import Bu

logger = logging.getLogger(__name__)
router = Router(name="payment")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Show plan list
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "menu_payment")
async def cb_show_plans(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    plans = await get_active_plans()
    if not plans:
        support = settings.SUPPORT_CONTACT
        await callback.message.edit_text(
            f"⚠️ <b>{Bu('NO PLANS AVAILABLE')}</b>\n\n"
            f"<b>{Bu('CONTACT')}:</b> {support}",
            reply_markup=back_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"{E_CROWN} <b>{Bu('CHOOSE A SUBSCRIPTION PLAN')}</b>\n\n"
        f"{DIV2}\n"
        f"<b>{Bu('SELECT A PLAN TO CONTINUE:')}</b>",
        reply_markup=plan_list_kb(plans),
        parse_mode="HTML",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Show payment methods
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("select_plan:"))
async def cb_select_plan(callback: CallbackQuery, state: FSMContext) -> None:
    plan_id = int(callback.data.split(":")[1])
    plan    = await get_plan(plan_id)
    if not plan or not plan.get("is_active"):
        await callback.answer(
            f"⚠️ {Bu('THIS PLAN IS NO LONGER AVAILABLE.')}",
            show_alert=True,
        )
        return

    await state.update_data(selected_plan_id=plan_id)

    methods = await get_all_payment_methods(active_only=True)
    if not methods:
        # No methods — show instructions and go straight to receipt
        await callback.message.edit_text(
            payment_instructions_text(plan, method=None),
            reply_markup=_receipt_start_kb(plan_id),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Show method selection
    plan_name = plan["name"]
    price     = plan["price"]
    duration  = plan["duration_days"]
    await callback.message.edit_text(
        f"{E_MONEY} <b>{Bu('BUY PLAN')} — {Bu(plan_name.upper())}</b>\n\n"
        f"{DIV}\n"
        f"💰 <b>{Bu('PRICE')}:</b>    <b>${price:.2f}</b>\n"
        f"{E_CALENDAR} <b>{Bu('DURATION')}:</b> <b>{duration} {Bu('DAYS')}</b>\n"
        f"{DIV}\n\n"
        f"<b>{Bu('SELECT PAYMENT METHOD:')}</b>",
        reply_markup=payment_method_kb(methods, plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Show payment instructions for selected method
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("pay_method:"))
async def cb_pay_method(callback: CallbackQuery, state: FSMContext) -> None:
    parts     = callback.data.split(":")
    plan_id   = int(parts[1])
    method_id = int(parts[2])

    plan   = await get_plan(plan_id)
    method = await get_payment_method(method_id)

    if not plan or not plan.get("is_active"):
        await callback.answer(f"⚠️ {Bu('PLAN NO LONGER AVAILABLE.')}", show_alert=True)
        return
    if not method or not method.get("is_active"):
        await callback.answer(f"⚠️ {Bu('PAYMENT METHOD NO LONGER AVAILABLE.')}", show_alert=True)
        return

    await state.update_data(selected_plan_id=plan_id, selected_method_id=method_id)

    await callback.message.edit_text(
        payment_instructions_text(plan, method=method),
        reply_markup=_receipt_start_kb(plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Ask for Transaction ID
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("send_receipt:"))
async def cb_send_receipt_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    plan_id = int(callback.data.split(":")[1])
    await state.set_state(PaymentStates.waiting_for_txn_id)
    await state.update_data(selected_plan_id=plan_id)

    await callback.message.edit_text(
        f"📋 <b>{Bu('STEP 1 OF 2 — TRANSACTION ID')}</b>\n\n"
        f"{DIV}\n"
        f"<b>{Bu('SEND YOUR TRANSACTION ID / REFERENCE NUMBER.')}</b>\n\n"
        f"<i>{Bu('EXAMPLE')}:</i>\n"
        f"<code>TXN123456789</code>\n"
        f"<code>8801XXXXXXXXX</code>\n\n"
        f"<b>{Bu('TYPE AND SEND THE TRANSACTION ID BELOW:')}</b>",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Receive Transaction ID, ask for screenshot
# ══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.waiting_for_txn_id)
async def msg_receive_txn_id(message: Message, state: FSMContext) -> None:
    txn_id = (message.text or "").strip()
    if not txn_id:
        await message.answer(
            f"⚠️ <b>{Bu('PLEASE ENTER YOUR TRANSACTION ID.')}</b>",
            parse_mode="HTML",
        )
        return

    if len(txn_id) < 4:
        await message.answer(
            f"⚠️ <b>{Bu('TRANSACTION ID IS TOO SHORT.')}</b>\n\n"
            f"<b>{Bu('PLEASE ENTER A VALID ID.')}</b>",
            parse_mode="HTML",
        )
        return

    await state.update_data(txn_id=txn_id)
    await state.set_state(PaymentStates.waiting_for_receipt)

    await message.answer(
        f"📸 <b>{Bu('STEP 2 OF 2 — PAYMENT SCREENSHOT')}</b>\n\n"
        f"{DIV}\n"
        f"{E_CHECK} <b>{Bu('TRANSACTION ID')}:</b> <code>{txn_id}</code>\n"
        f"{DIV}\n\n"
        f"<b>{Bu('NOW SEND A SCREENSHOT OF YOUR PAYMENT.')}</b>\n"
        f"<i>{Bu('SEND AS PHOTO OR FILE.')}</i>\n\n"
        f"<b>{Bu('YOU CAN ALSO SKIP THIS STEP')} — {Bu('JUST SEND')}</b> "
        f"<code>{Bu('SKIP')}</code>",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Receive screenshot, submit request
# ══════════════════════════════════════════════════════════════════════════════

@router.message(PaymentStates.waiting_for_receipt)
async def msg_receive_receipt(
    message: Message, state: FSMContext, db_user: dict, bot: Bot
) -> None:
    data      = await state.get_data()
    plan_id   = data.get("selected_plan_id")
    method_id = data.get("selected_method_id")
    txn_id    = data.get("txn_id", "")

    if not plan_id:
        await message.answer(
            f"⚠️ <b>{Bu('SESSION EXPIRED. PLEASE START AGAIN.')}</b>",
            reply_markup=back_kb(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    # Accept photo, document, or "skip"
    file_id: str | None = None
    skipped = False

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.text and message.text.strip().lower() == "skip":
        skipped = True
    elif message.text:
        # Text might be additional note — save as note
        file_id = None
    else:
        await message.answer(
            f"⚠️ <b>{Bu('PLEASE SEND A PHOTO, FILE, OR TYPE')} <code>skip</code>.</b>",
            parse_mode="HTML",
        )
        return

    # note = txn_id + any caption
    note_parts = [f"TXN: {txn_id}"] if txn_id else []
    caption    = message.caption or (message.text if not skipped else "") or ""
    if caption.strip().lower() != "skip" and caption.strip():
        note_parts.append(caption.strip())
    note = " | ".join(note_parts)

    req_id = await create_payment_request(
        user_id=db_user["id"],
        plan_id=plan_id,
        receipt_file_id=file_id,
        note=note[:500],
        method_id=method_id,
    )

    plan         = await get_plan(plan_id)
    plan_name    = plan["name"] if plan else str(plan_id)
    method       = await get_payment_method(method_id) if method_id else None
    method_name  = method["name"] if method else Bu("NOT SPECIFIED")
    support      = settings.SUPPORT_CONTACT
    user_display = (
        f"@{db_user.get('username')}" if db_user.get("username")
        else f"ID {db_user['id']}"
    )

    await state.clear()

    # ── Confirm to user ───────────────────────────────────────────────────────
    await message.answer(
        f"{E_CHECK} <b>{Bu('PAYMENT REQUEST SUBMITTED!')}</b>\n\n"
        f"{DIV2}\n"
        f"📦 <b>{Bu('PLAN')}:</b>     <b>{Bu(plan_name.upper())}</b>\n"
        f"💳 <b>{Bu('METHOD')}:</b>   <b>{method_name}</b>\n"
        f"🧾 <b>{Bu('TXN ID')}:</b>   <code>{txn_id or Bu('NOT PROVIDED')}</code>\n"
        f"📋 <b>{Bu('REQUEST')} #:</b> <code>{req_id}</code>\n"
        f"{DIV2}\n\n"
        f"{E_STAR} <b>{Bu('YOUR REQUEST IS UNDER REVIEW.')}</b>\n"
        f"<b>{Bu('YOU WILL BE NOTIFIED ONCE APPROVED.')}</b>\n\n"
        f"💬 <b>{Bu('SUPPORT')}:</b> "
        f"<a href=\"https://t.me/{support.lstrip('@')}\"><b>{support}</b></a>",
        parse_mode="HTML",
        reply_markup=back_kb(),
    )

    # ── Notify admins ─────────────────────────────────────────────────────────
    admin_caption = (
        f"💳 <b>{Bu('NEW PAYMENT REQUEST')} #{req_id}</b>\n\n"
        f"{DIV}\n"
        f"👤 <b>{Bu('USER')}:</b>    {user_display} (<code>{db_user['id']}</code>)\n"
        f"📦 <b>{Bu('PLAN')}:</b>    <b>{plan_name}</b>\n"
        f"💳 <b>{Bu('METHOD')}:</b>  <b>{method_name}</b>\n"
        f"🧾 <b>{Bu('TXN ID')}:</b>  <code>{txn_id or 'N/A'}</code>\n"
        f"📝 <b>{Bu('NOTE')}:</b>    {caption[:150] or '<i>None</i>'}\n"
        f"{DIV}"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            if file_id:
                if message.photo:
                    await bot.send_photo(
                        admin_id, file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=payment_review_kb(req_id),
                    )
                else:
                    await bot.send_document(
                        admin_id, file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=payment_review_kb(req_id),
                    )
            else:
                await bot.send_message(
                    admin_id, admin_caption,
                    parse_mode="HTML",
                    reply_markup=payment_review_kb(req_id),
                )
        except Exception as e:
            logger.warning("Could not notify admin %s: %s", admin_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _receipt_start_kb(plan_id: int):
    """Keyboard shown on payment instruction page."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from utils.unicode_style import Bu as _Bu
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🟢 📤 {_Bu('PROCEED TO PAYMENT')}",
                callback_data=f"send_receipt:{plan_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔴 ❌ {_Bu('CANCEL')}",
                callback_data="menu_back",
            ),
        ],
    ])
