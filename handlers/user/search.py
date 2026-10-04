"""
search.py - Direct search flow (no mode selection required).

User clicks SEARCH LOGS → types anything → bot auto-detects type and searches.
Supports: domain, IP, email, URL, keyword — all auto-detected.
Results sent as .txt file (url:login:pass format).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from config import settings
from database.queries import increment_search_count, award_points, log_read
from keyboards.user_kb import back_kb, search_again_kb
from middlewares.throttling import get_search_cooldown_remaining, set_last_search
from services.search_engine import build_txt_output, search_logs_all
from states.states import SearchStates
from utils.text_format import (
    E_CHECK, E_DIAMOND, E_FIRE, E_MAGNIFY, E_STAR,
    E_CROWN, E_LIGHTNING, E_SNOWFLAKE, E_GEAR,
    DIV, DIV2, DIV3,
)
from utils.unicode_style import Bu

logger = logging.getLogger(__name__)
router = Router(name="search")

# ── Regex patterns for auto-detection ────────────────────────────────────────
_RE_IP_BARE    = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
_RE_IP_URL     = re.compile(r'^https?://(\d{1,3}(?:\.\d{1,3}){3})', re.I)
_RE_HTTP       = re.compile(r'^https?://', re.I)
_RE_DOMAIN     = re.compile(r'^[\w\-]+(?:\.[\w\-]+)+$')
_RE_EMAIL      = re.compile(r'^[\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}$')


def _auto_detect_mode(query: str) -> Tuple[str, str]:
    """
    Returns (mode, mode_label) for a given query string.
    All detection is automatic — user never selects manually.
    """
    q = query.strip()

    if _RE_IP_URL.match(q):
        return "ip", f"🖥 {Bu('IP ADDRESS URL')}"
    if _RE_HTTP.match(q):
        return "url", f"🔗 {Bu('FULL URL')}"
    if _RE_IP_BARE.match(q):
        return "ip", f"🖥 {Bu('IP ADDRESS')}"
    if _RE_EMAIL.match(q):
        return "email", f"📧 {Bu('EMAIL / LOGIN')}"
    if _RE_DOMAIN.match(q) and "@" not in q:
        return "domain", f"🌐 {Bu('DOMAIN')}"
    # Default: FTS5 keyword search
    return "all", f"🔍 {Bu('SMART SEARCH')}"


def _is_premium(db_user: Dict[str, Any]) -> bool:
    plan_id = db_user.get("plan_id")
    return plan_id is not None and int(plan_id) in settings.PREMIUM_PLAN_IDS


async def _safe_edit(msg, text: str, **kwargs) -> None:
    try:
        await msg.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "no text in the message" in err or \
           "message can't be edited" in err or \
           "message is not modified" in err:
            await msg.answer(text, **kwargs)
        else:
            raise


async def _check_quota(event, db_user: Dict[str, Any]) -> bool:
    plan_limit: int = db_user.get("daily_search_limit") or 0
    used:        int = db_user.get("daily_searches") or 0
    cooldown:    int = db_user.get("cooldown_seconds") or 0
    user_id:     int = db_user["id"]

    if plan_limit > 0 and used >= plan_limit:
        support = settings.SUPPORT_CONTACT
        text = (
            f"⛔ <b>{Bu('DAILY LIMIT REACHED!')}</b>\n\n"
            f"{DIV2}\n"
            f"📊 <b>{Bu('USED')}:</b>  <b>{used}/{plan_limit}</b>\n"
            f"🕛 <b>{Bu('RESETS')}:</b> <b>{Bu('MIDNIGHT UTC')}</b>\n"
            f"{DIV2}\n\n"
            f"{E_DIAMOND} <b>{Bu('UPGRADE FOR MORE SEARCHES')}</b>\n"
            f"<a href=\"https://t.me/{support.lstrip('@')}\"><b>{support}</b></a>"
        )
        if isinstance(event, Message):
            await event.answer(text, parse_mode="HTML", reply_markup=back_kb())
        else:
            await event.message.answer(text, parse_mode="HTML", reply_markup=back_kb())
            await event.answer()
        return False

    remaining = get_search_cooldown_remaining(user_id, cooldown)
    if remaining > 0:
        text = f"⏳ <b>{Bu('PLEASE WAIT')} {remaining:.1f}s {Bu('BEFORE NEXT SEARCH.')}</b>"
        if isinstance(event, Message):
            await event.answer(text, parse_mode="HTML")
        else:
            await event.answer(text, show_alert=True)
        return False

    return True


# ── Entry point: SEARCH LOGS button ──────────────────────────────────────────

@router.callback_query(F.data == "menu_search")
async def cb_start_search(
    callback: CallbackQuery, state: FSMContext, db_user: dict
) -> None:
    await state.set_state(SearchStates.waiting_for_query)
    premium = _is_premium(db_user)
    used    = db_user.get("daily_searches", 0)
    limit   = db_user.get("daily_search_limit", 0)
    remain  = max(0, limit - used)

    limit_line = (
        f"{E_CROWN} <b>{Bu('PREMIUM')} — {Bu('ALL RESULTS, NO CAP')}</b>"
        if premium else
        f"{E_LIGHTNING} <b>{Bu('FREE')} — {Bu('CAP')}: {settings.FREE_RESULT_LIMIT} {Bu('RESULTS')} | {Bu('REMAINING TODAY')}: {remain}/{limit}</b>"
    )

    text = (
        f"{E_FIRE} <b>{Bu('LOGSBOT SEARCH')}</b> {E_FIRE}\n\n"
        f"{DIV2}\n"
        f"<b>{Bu('JUST TYPE ANYTHING BELOW')} 👇</b>\n"
        f"{DIV}\n"
        f"🌐 <code>facebook.com</code>         → <b>{Bu('DOMAIN')}</b>\n"
        f"🖥 <code>192.168.1.1</code>          → <b>{Bu('IP ADDRESS')}</b>\n"
        f"📧 <code>user@gmail.com</code>        → <b>{Bu('EMAIL/LOGIN')}</b>\n"
        f"🔗 <code>https://site.com/login</code> → <b>{Bu('FULL URL')}</b>\n"
        f"🔑 <code>admin</code>, <code>password</code>, etc.  → <b>{Bu('KEYWORD')}</b>\n"
        f"{DIV}\n"
        f"{E_GEAR} <b>{Bu('AUTO-DETECTED — NO SELECTION NEEDED')}</b>\n"
        f"{DIV2}\n"
        f"{limit_line}"
    )
    await _safe_edit(callback.message, text,
                     parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()


# ── Receive query (direct — no mode selection) ────────────────────────────────

@router.message(SearchStates.waiting_for_query)
async def msg_receive_query(
    message: Message, state: FSMContext, db_user: dict
) -> None:
    query = (message.text or "").strip()

    if len(query) < 2:
        await message.answer(
            f"⚠️ <b>{Bu('PLEASE ENTER AT LEAST 2 CHARACTERS.')}</b>",
            parse_mode="HTML",
        )
        return

    if not await _check_quota(message, db_user):
        await state.clear()
        return

    await state.clear()

    # Auto-detect search type
    mode, mode_label = _auto_detect_mode(query)
    premium  = _is_premium(db_user)
    limit    = None if premium else settings.FREE_RESULT_LIMIT

    status_msg = await message.answer(
        f"{E_MAGNIFY} <b>{Bu('SEARCHING')}…</b>\n\n"
        f"<b>{Bu('QUERY')}:</b> <code>{query}</code>\n"
        f"<b>{Bu('TYPE')}:</b>  {mode_label}",
        parse_mode="HTML",
    )

    try:
        records, total_in_db = await search_logs_all(query, limit=limit, mode=mode)
    except Exception as e:
        logger.error("Search error user=%s mode=%s query='%s': %s",
                     db_user["id"], mode, query, e)
        await status_msg.edit_text(
            f"⚠️ <b>{Bu('SEARCH FAILED. PLEASE TRY AGAIN.')}</b>",
            reply_markup=back_kb(),
            parse_mode="HTML",
        )
        return

    set_last_search(db_user["id"])
    await increment_search_count(db_user["id"])

    # Reward points
    await award_points(db_user["id"], "daily_search")
    total_srch = (db_user.get("total_searches") or 0) + 1
    if total_srch == 1:
        await award_points(db_user["id"], "first_search")
    elif total_srch == 10:
        await award_points(db_user["id"], "search_10")
    elif total_srch == 100:
        await award_points(db_user["id"], "search_100")

    # Log read
    if records:
        await log_read(
            user_id=db_user["id"],
            record_text=f"{len(records)} records for: {query}",
            query=query,
        )

    # ── No results ────────────────────────────────────────────────────────────
    if not records:
        await status_msg.edit_text(
            f"{E_SNOWFLAKE} <b>{Bu('NO RESULTS FOUND')}</b>\n\n"
            f"{DIV}\n"
            f"🔍 <b>{Bu('QUERY')}:</b> <code>{query}</code>\n"
            f"{E_GEAR} <b>{Bu('TYPE')}:</b>  {mode_label}\n"
            f"{DIV}\n\n"
            f"<b>{Bu('TRY A DIFFERENT KEYWORD OR SPELLING.')}</b>",
            parse_mode="HTML",
            reply_markup=search_again_kb(),
        )
        return

    # ── Build .txt file ───────────────────────────────────────────────────────
    txt_content    = build_txt_output(records, query, total_in_db, mode=mode)
    file_bytes     = txt_content.encode("utf-8")
    safe_query     = re.sub(r'[^\w\-.]', '_', query)[:35]
    filename       = f"logs_{safe_query}.txt"
    complete_count = len(records)

    if premium:
        caption = (
            f"{E_FIRE} <b>{Bu('SEARCH COMPLETE')}</b> {E_FIRE}\n\n"
            f"{DIV2}\n"
            f"🔍 <b>{Bu('QUERY')}</b>    <code>{query}</code>\n"
            f"{E_GEAR} <b>{Bu('TYPE')}</b>     {mode_label}\n"
            f"📊 <b>{Bu('TOTAL DB')}</b> <b>{total_in_db:,}</b>\n"
            f"{E_CHECK} <b>{Bu('IN FILE')}</b>  <b>{complete_count:,}</b>\n"
            f"{DIV2}\n"
            f"📄 <b>{Bu('FORMAT')}:</b> <code>url:login:pass</code>"
        )
    elif total_in_db > settings.FREE_RESULT_LIMIT:
        support = settings.SUPPORT_CONTACT
        caption = (
            f"{E_FIRE} <b>{Bu('SEARCH COMPLETE')}</b>\n\n"
            f"{DIV2}\n"
            f"🔍 <b>{Bu('QUERY')}</b>    <code>{query}</code>\n"
            f"{E_GEAR} <b>{Bu('TYPE')}</b>     {mode_label}\n"
            f"📊 <b>{Bu('TOTAL DB')}</b> <b>{total_in_db:,}</b>\n"
            f"📁 <b>{Bu('IN FILE')}</b>  <b>{complete_count}</b> "
            f"<i>({Bu('FREE CAP')}: {settings.FREE_RESULT_LIMIT})</i>\n"
            f"{DIV2}\n"
            f"📄 <b>{Bu('FORMAT')}:</b> <code>url:login:pass</code>\n\n"
            f"{E_DIAMOND} <b>{Bu('UPGRADE FOR ALL RESULTS')} →</b> "
            f"<a href=\"https://t.me/{support.lstrip('@')}\"><b>{support}</b></a>"
        )
    else:
        caption = (
            f"{E_CHECK} <b>{Bu('SEARCH COMPLETE')}</b>\n\n"
            f"{DIV2}\n"
            f"🔍 <b>{Bu('QUERY')}</b>    <code>{query}</code>\n"
            f"{E_GEAR} <b>{Bu('TYPE')}</b>     {mode_label}\n"
            f"📊 <b>{Bu('TOTAL DB')}</b> <b>{total_in_db:,}</b>\n"
            f"{E_STAR} <b>{Bu('IN FILE')}</b>  <b>{complete_count:,}</b>\n"
            f"{DIV2}\n"
            f"📄 <b>{Bu('FORMAT')}:</b> <code>url:login:pass</code>"
        )

    await status_msg.delete()

    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename),
        caption=caption,
        parse_mode="HTML",
        reply_markup=search_again_kb(),
    )

    # Video response if configured
    video_fid = getattr(settings, "SEARCH_RESULT_VIDEO", None)
    if video_fid:
        try:
            await message.answer_video(
                video=video_fid,
                caption=f"🎬 <b>{Bu('SEARCH RESULTS')} — {query}</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.debug("Could not send result video: %s", e)
