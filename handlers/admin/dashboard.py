"""
dashboard.py - Admin entry point: /admin command, stats, and payment approvals.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import settings
from database.queries import (
    count_logs, count_users, get_active_plans,
    get_payment_request, get_pending_payments,
    update_payment_status, assign_plan,
    get_reading_stats,
)
from keyboards.admin_kb import admin_main_kb, payment_review_kb, confirm_kb
from utils.text_format import admin_stats_text, DIV, DIV2
from utils.unicode_style import Bu

logger = logging.getLogger(__name__)
router = Router(name="admin_dashboard")


def _check(is_root_admin: bool, is_sub_admin: bool) -> bool:
    return is_root_admin or is_sub_admin


# ── /admin command ────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, is_root_admin: bool, is_sub_admin: bool) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await message.answer(
            f"🚫 <b>{Bu('ACCESS DENIED.')}</b>",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🛠 <b>{Bu('ADMIN DASHBOARD')}</b>\n\n"
        f"<b>{Bu('SELECT AN OPTION:')}</b>",
        reply_markup=admin_main_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer(f"🚫 {Bu('ACCESS DENIED.')}", show_alert=True)
        return

    await callback.message.edit_text(
        f"🛠 <b>{Bu('ADMIN DASHBOARD')}</b>\n\n"
        f"<b>{Bu('SELECT AN OPTION:')}</b>",
        reply_markup=admin_main_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    user_count = await count_users()
    log_count  = await count_logs()
    plans      = await get_active_plans()
    pending    = await get_pending_payments()
    read_stats = await get_reading_stats()

    # Total reward points in system
    from database.connection import db as _db
    reward_total = await _db.fetchval("SELECT COALESCE(SUM(reward_points), 0) FROM users") or 0
    total_reads  = read_stats.get("total_reads", 0)

    await callback.message.edit_text(
        admin_stats_text(
            user_count, log_count, len(plans), len(pending),
            reward_total=reward_total,
            total_reads=total_reads,
        ),
        reply_markup=confirm_kb("admin_menu", "admin_menu"),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Pending Payments ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_payments")
async def cb_pending_payments(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    pending = await get_pending_payments()
    if not pending:
        await callback.message.edit_text(
            "✅ <b>No pending payment requests.</b>",
            reply_markup=confirm_kb("admin_menu", "admin_menu"),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    req   = pending[0]
    count = len(pending)
    method_name = req.get("method_name") or Bu("NOT SPECIFIED")
    txn_note = req.get("note") or "<i>None</i>"
    text = (
        f"⏳ <b>{Bu('PENDING PAYMENTS')}</b> ({count} {Bu('TOTAL')})\n\n"
        f"{DIV2}\n"
        f"<b>{Bu('REQUEST')} #{req['id']}</b>\n"
        f"👤 <b>{Bu('USER')}:</b>   @{req.get('username') or req['user_id']} "
        f"(<code>{req['user_id']}</code>)\n"
        f"📦 <b>{Bu('PLAN')}:</b>   <b>{req['plan_name']}</b>\n"
        f"💳 <b>{Bu('METHOD')}:</b> <b>{method_name}</b>\n"
        f"🧾 <b>{Bu('NOTE/TXN')}:</b> {txn_note}\n"
        f"📅 <b>{Bu('DATE')}:</b>   {req['created_at']}\n"
        f"{DIV2}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_review_kb(req["id"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payment_approve:"))
async def cb_payment_approve(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    req_id = int(callback.data.split(":")[1])
    req    = await get_payment_request(req_id)
    if not req or req["status"] != "pending":
        await callback.answer("⚠️ Request already processed.", show_alert=True)
        return

    reviewer_id = callback.from_user.id
    await update_payment_status(req_id, "approved", reviewer_id)
    await assign_plan(req["user_id"], req["plan_id"], req["duration_days"])

    # Award reward points for plan purchase
    from database.queries import award_points
    await award_points(req["user_id"], "plan_purchase", f"Plan: {req['plan_name']}")

    await callback.message.edit_text(
        f"✅ <b>{Bu('PAYMENT')} #{req_id} {Bu('APPROVED')}</b>\n\n"
        f"<b>{Bu('PLAN')} {req['plan_name']} {Bu('ACTIVATED FOR')} <code>{req['user_id']}</code>.</b>",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_payments", "admin_menu"),
    )
    await callback.answer(f"✅ {Bu('APPROVED!')}")

    try:
        await callback.bot.send_message(
            req["user_id"],
            f"🎉 <b>{Bu('PLAN ACTIVATED!')}</b>\n\n"
            f"{DIV2}\n"
            f"📦 <b>{Bu('PLAN')}:</b>     <b>{Bu(req['plan_name'].upper())}</b>\n"
            f"📅 <b>{Bu('DURATION')}:</b> <b>{req['duration_days']} {Bu('DAYS')}</b>\n"
            f"{DIV2}\n\n"
            f"<b>{Bu('ENJOY YOUR ENHANCED SEARCH ACCESS!')}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Could not notify user %s of approval: %s", req["user_id"], e)


@router.callback_query(F.data.startswith("payment_reject:"))
async def cb_payment_reject(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    req_id = int(callback.data.split(":")[1])
    req    = await get_payment_request(req_id)
    if not req or req["status"] != "pending":
        await callback.answer("⚠️ Request already processed.", show_alert=True)
        return

    reviewer_id = callback.from_user.id
    await update_payment_status(req_id, "rejected", reviewer_id)

    await callback.message.edit_text(
        f"❌ <b>{Bu('PAYMENT')} #{req_id} {Bu('REJECTED')}</b>",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_payments", "admin_menu"),
    )
    await callback.answer(f"❌ {Bu('REJECTED.')}")

    try:
        await callback.bot.send_message(
            req["user_id"],
            f"❌ <b>{Bu('PAYMENT REJECTED')}</b>\n\n"
            f"{DIV}\n"
            f"<b>{Bu('YOUR PAYMENT FOR')} {Bu(req['plan_name'].upper())} {Bu('WAS REJECTED.')}</b>\n"
            f"<b>{Bu('CONTACT')} {settings.SUPPORT_CONTACT} {Bu('FOR HELP.')}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Could not notify user %s of rejection: %s", req["user_id"], e)


# ── User rewards (from admin user detail) ────────────────────────────────────

@router.callback_query(F.data.startswith("admin_user_rewards:"))
async def cb_user_rewards(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    uid = int(callback.data.split(":")[1])
    from database.queries import get_user, get_user_reward_history
    user    = await get_user(uid)
    history = await get_user_reward_history(uid, limit=10)
    if not user:
        await callback.answer("⚠️ User not found.", show_alert=True)
        return

    points = user.get("reward_points", 0)
    lines  = [
        f"🎁 <b>Reward History</b> — <code>{uid}</code>\n"
        f"<b>Balance: {points:,} pts</b>\n",
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>",
    ]
    for tx in history:
        sign = "+" if tx["points"] > 0 else ""
        lines.append(
            f"<b>{sign}{tx['points']}</b> pts — <code>{tx['action_key']}</code> "
            f"<i>{tx.get('note') or ''}</i>"
        )

    from keyboards.admin_kb import confirm_kb
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=confirm_kb(f"admin_user_detail:{uid}", "admin_users"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_reads:"))
async def cb_user_reads(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not _check(is_root_admin, is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    uid  = int(callback.data.split(":")[1])
    from database.queries import get_user_reading_history, count_user_reads
    history = await get_user_reading_history(uid, limit=10)
    total   = await count_user_reads(uid)
    from utils.helpers import escape_html, truncate, format_dt

    lines = [
        f"📖 <b>Reading History</b> — <code>{uid}</code>\n"
        f"<b>Total reads: {total}</b>\n",
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>",
    ]
    for r in history:
        q  = escape_html(r.get("query") or "")
        t  = escape_html(truncate(r.get("record_text") or "", 60))
        dt = format_dt(r.get("read_at"), "%d %b %H:%M")
        lines.append(f"🔍 <code>{q}</code> — <i>{dt}</i>\n   <code>{t}</code>\n")

    from keyboards.admin_kb import confirm_kb
    await callback.message.edit_text(
        "\n".join(lines) if len(lines) > 2 else f"📖 <b>No reading history for <code>{uid}</code>.</b>",
        reply_markup=confirm_kb(f"admin_user_detail:{uid}", "admin_users"),
        parse_mode="HTML",
    )
    await callback.answer()
