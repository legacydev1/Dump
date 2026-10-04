"""
broadcast.py - Admin broadcast: text, photo, video, document with target audience.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_users_by_plan, get_all_active_users,
    log_broadcast, get_all_plans,
)
from keyboards.admin_kb import (
    admin_broadcast_type_kb, admin_broadcast_target_kb, admin_main_kb,
)
from services.broadcast import send_broadcast
from states.states import AdminBroadcastStates

logger = logging.getLogger(__name__)
router = Router(name="admin_broadcast")


# ── Step 1: Choose content type ───────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast_menu(
    callback: CallbackQuery, state: FSMContext, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminBroadcastStates.waiting_for_content)
    await callback.message.edit_text(
        "📣 <b>Broadcast Message</b>\n\n"
        "<b>Step 1:</b> Choose the <b>content type</b> to broadcast:",
        reply_markup=admin_broadcast_type_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Step 2: Receive content based on chosen type ──────────────────────────────

@router.callback_query(
    AdminBroadcastStates.waiting_for_content,
    F.data.startswith("bcast_type:"),
)
async def cb_broadcast_type(
    callback: CallbackQuery, state: FSMContext
) -> None:
    btype = callback.data.split(":", 1)[1]  # text | photo | video | document
    await state.update_data(broadcast_type=btype)

    hints = {
        "text":     "Send your <b>text message</b> (HTML formatting supported):",
        "photo":    "Send a <b>photo</b> (optionally add a caption):",
        "video":    "Send a <b>video</b> (optionally add a caption):",
        "document": "Send a <b>document/file</b> (optionally add a caption):",
    }
    await callback.message.edit_text(
        f"📣 <b>Broadcast — {btype.title()}</b>\n\n"
        f"{hints.get(btype, 'Send your content:')}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_for_content)
async def msg_broadcast_content(message: Message, state: FSMContext) -> None:
    data  = await state.get_data()
    btype = data.get("broadcast_type", "text")

    media_file_id: str | None = None
    text: str = ""

    if btype == "text":
        text = message.html_text or message.text or ""
        if not text.strip():
            await message.answer("⚠️ <b>Message cannot be empty.</b>", parse_mode="HTML")
            return

    elif btype == "photo":
        if not message.photo:
            await message.answer("⚠️ <b>Please send a photo.</b>", parse_mode="HTML")
            return
        media_file_id = message.photo[-1].file_id
        text = message.html_text or message.caption or ""

    elif btype == "video":
        if not message.video:
            await message.answer("⚠️ <b>Please send a video.</b>", parse_mode="HTML")
            return
        media_file_id = message.video.file_id
        text = message.html_text or message.caption or ""

    elif btype == "document":
        if not message.document:
            await message.answer("⚠️ <b>Please send a document.</b>", parse_mode="HTML")
            return
        media_file_id = message.document.file_id
        text = message.html_text or message.caption or ""

    await state.update_data(
        broadcast_text=text,
        broadcast_media_file_id=media_file_id,
    )
    await state.set_state(AdminBroadcastStates.confirming)

    # Show preview
    preview = text[:300] if text else "<i>(no caption)</i>"
    media_note = f"\n📎 <b>Media:</b> {btype}" if media_file_id else ""
    plans = await get_all_plans()

    await message.answer(
        f"📋 <b>Preview:</b>\n\n{preview}{media_note}\n\n"
        f"<b>Choose target audience:</b>",
        reply_markup=admin_broadcast_target_kb(plans),
        parse_mode="HTML",
    )


# ── Step 3: Choose target and send ───────────────────────────────────────────

@router.callback_query(
    AdminBroadcastStates.confirming,
    F.data.startswith("broadcast_target:"),
)
async def cb_broadcast_send(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    data           = await state.get_data()
    text: str      = data.get("broadcast_text", "")
    btype: str     = data.get("broadcast_type", "text")
    media_id: str  = data.get("broadcast_media_file_id")
    target: str    = callback.data.split(":", 1)[1]
    await state.clear()

    if target == "all":
        users = await get_all_active_users()
    elif target.startswith("plan:"):
        plan_id = int(target.split(":")[1])
        users = await get_users_by_plan(plan_id)
    else:
        await callback.answer("Unknown target.", show_alert=True)
        return

    if not users:
        await callback.message.edit_text(
            "⚠️ <b>No users found for selected target.</b>",
            reply_markup=admin_main_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📤 <b>Sending to {len(users):,} users…</b>",
        parse_mode="HTML",
    )
    await callback.answer()

    media_type = btype if btype != "text" else None
    asyncio.create_task(
        _do_broadcast(
            bot=bot,
            admin_id=callback.from_user.id,
            users=users,
            text=text,
            target=target,
            media_type=media_type,
            media_file_id=media_id,
            status_message=callback.message,
        ),
        name="broadcast_task",
    )


async def _do_broadcast(
    bot: Bot,
    admin_id: int,
    users: list,
    text: str,
    target: str,
    media_type: str | None,
    media_file_id: str | None,
    status_message,
) -> None:
    sent, failed = await send_broadcast(
        bot, users, text,
        media_type=media_type,
        media_file_id=media_file_id,
    )
    await log_broadcast(
        admin_id, text, target, sent, failed,
        media_type=media_type,
        media_file_id=media_file_id,
    )
    try:
        await status_message.edit_text(
            f"✅ <b>Broadcast Complete</b>\n\n"
            f"📤 <b>Sent:</b>   <b>{sent:,}</b>\n"
            f"❌ <b>Failed:</b> <b>{failed:,}</b>\n"
            f"📦 <b>Type:</b>   <b>{media_type or 'text'}</b>",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    except Exception as e:
        logger.warning("Could not update broadcast status: %s", e)
