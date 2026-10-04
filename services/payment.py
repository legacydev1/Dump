"""
payment.py - Payment activation service.

Handles plan activation after a payment is approved by an admin.
This module is the single authoritative place for all payment-related
business logic, keeping handlers thin.

Webhook-ready: expose activate_payment() so a future webhook handler
can call it the same way the admin approval flow does.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot

from config import settings
from database.queries import (
    assign_plan,
    get_payment_request,
    get_plan,
    update_payment_status,
)

logger = logging.getLogger(__name__)


async def activate_payment(
    req_id: int,
    reviewer_id: int,
    bot: Optional[Bot] = None,
) -> dict:
    """
    Approve a pending payment request and activate the plan for the user.

    Args:
        req_id:      The payment_requests.id to approve.
        reviewer_id: The admin user_id performing the approval.
        bot:         Optional Bot instance for user notification.

    Returns:
        dict with keys: success (bool), message (str), user_id (int|None)

    This function is idempotent — calling it on an already-approved request
    returns success=False with a descriptive message.
    """
    req = await get_payment_request(req_id)
    if not req:
        return {"success": False, "message": f"Payment request #{req_id} not found.", "user_id": None}

    if req["status"] != "pending":
        return {
            "success": False,
            "message": f"Request #{req_id} is already '{req['status']}'.",
            "user_id": req["user_id"],
        }

    plan = await get_plan(req["plan_id"])
    if not plan:
        return {
            "success": False,
            "message": f"Plan ID {req['plan_id']} not found.",
            "user_id": req["user_id"],
        }

    duration = plan["duration_days"]

    # Update DB: mark approved and activate plan
    await update_payment_status(req_id, "approved", reviewer_id)
    await assign_plan(req["user_id"], req["plan_id"], duration)

    logger.info(
        "Payment #%s approved by %s — user %s → plan '%s' (%d days)",
        req_id, reviewer_id, req["user_id"], plan["name"], duration,
    )

    # Notify user if bot is available
    if bot:
        try:
            expires = datetime.utcnow() + timedelta(days=duration)
            await bot.send_message(
                req["user_id"],
                f"🎉 <b>Plan Activated!</b>\n\n"
                f"Your <b>{plan['name']}</b> plan is now active.\n"
                f"📅 Expires: <b>{expires.strftime('%Y-%m-%d')}</b>\n\n"
                f"Enjoy {plan['daily_search_limit']} daily searches!",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "Could not send activation notice to user %s: %s", req["user_id"], e
            )

    return {
        "success": True,
        "message": f"Plan '{plan['name']}' activated for user {req['user_id']}.",
        "user_id": req["user_id"],
    }


async def reject_payment(
    req_id: int,
    reviewer_id: int,
    reason: str = "",
    bot: Optional[Bot] = None,
) -> dict:
    """
    Reject a pending payment request.

    Args:
        req_id:      The payment_requests.id to reject.
        reviewer_id: The admin user_id performing the rejection.
        reason:      Optional reason shown to the user.
        bot:         Optional Bot instance for user notification.

    Returns:
        dict with keys: success (bool), message (str), user_id (int|None)
    """
    req = await get_payment_request(req_id)
    if not req:
        return {"success": False, "message": f"Payment request #{req_id} not found.", "user_id": None}

    if req["status"] != "pending":
        return {
            "success": False,
            "message": f"Request #{req_id} is already '{req['status']}'.",
            "user_id": req["user_id"],
        }

    await update_payment_status(req_id, "rejected", reviewer_id)
    logger.info("Payment #%s rejected by %s", req_id, reviewer_id)

    if bot:
        try:
            support = settings.SUPPORT_CONTACT
            reason_line = f"\nReason: {reason}" if reason else ""
            await bot.send_message(
                req["user_id"],
                f"❌ <b>Payment Rejected</b>\n\n"
                f"Your payment for <b>{req.get('plan_name', 'the plan')}</b> "
                f"could not be verified.{reason_line}\n\n"
                f"Please contact {support} if you believe this is an error.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "Could not send rejection notice to user %s: %s", req["user_id"], e
            )

    return {
        "success": True,
        "message": f"Payment request #{req_id} rejected.",
        "user_id": req["user_id"],
    }
