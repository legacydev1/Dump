"""
ingestion.py — Admin log file ingestion handler.

Supports:
  • Direct document upload (.txt / .csv / .json)
  • Forwarded messages from any channel / group / saved messages
  • Files ≤ 19 MB  → Bot API download  (fast, no extra library)
  • Files  > 19 MB → Telethon MTProto  (supports up to 4 GB)

Flow:
  1. Admin clicks 📥 Ingest or /ingest command
  2. Bot enters AdminIngestionStates.waiting_for_file
  3. Admin sends or forwards a supported document
  4. Handler validates extension, picks download method
  5. File downloaded → background ingestion task started
  6. Live progress updates sent to admin every few seconds
  7. Completion / error notification sent when done
  8. Raw file deleted after indexing
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, Message

from config import settings
from keyboards.admin_kb import admin_main_kb, confirm_kb
from keyboards.user_kb import back_kb
from services.ingestion_worker import _fmt_size, ingest_file_background
from services.telethon_client import telethon_mgr
from states.states import AdminIngestionStates

logger = logging.getLogger(__name__)
router = Router(name="admin_ingestion")

ALLOWED_EXTENSIONS  = {".txt", ".csv", ".json"}
_BOT_API_LIMIT_BYTES = 19 * 1024 * 1024   # 19 MB


# ── Safe edit helper ──────────────────────────────────────────────────────────

async def _safe_edit(msg, text: str, **kwargs) -> None:
    """Edit a message text; fall back to answer() if not editable."""
    try:
        await msg.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "no text in the message" in err \
                or "message can't be edited" in err \
                or "message is not modified" in err:
            await msg.answer(text, **kwargs)
        else:
            raise


# ── Unique upload path helper ─────────────────────────────────────────────────

def _unique_path(original_name: str) -> Path:
    """
    Return a unique file path in UPLOAD_DIR to avoid overwriting
    a previous upload with the same filename.
    """
    stem = Path(original_name).stem
    ext  = Path(original_name).suffix.lower()
    uid  = uuid.uuid4().hex[:8]
    return settings.upload_dir / f"{stem}_{uid}{ext}"


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_ingest")
async def cb_admin_ingest(
    callback: CallbackQuery,
    state: FSMContext,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    tl_status = (
        "✅ <b>Telethon active</b> — files up to <b>4 GB</b> supported."
        if telethon_mgr.is_ready
        else "⚠️ <b>Bot API only</b> — max <b>19 MB</b>.\n"
             "   Set API_ID + API_HASH to enable large files."
    )

    await state.set_state(AdminIngestionStates.waiting_for_file)

    text = (
        "📥 <b>Log Ingestion</b>\n\n"
        f"{tl_status}\n\n"
        "Send or <b>forward</b> a file:\n"
        "  • <b>.txt</b>  — one log record per line\n"
        "  • <b>.csv</b>  — auto-detects text column\n"
        "  • <b>.json</b> — array of strings or JSON-Lines\n\n"
        "You can forward from any channel, group, or Saved Messages.\n"
        "⚡ Large files are indexed in the background — bot stays responsive."
    )
    await _safe_edit(callback.message, text, parse_mode="HTML", reply_markup=back_kb("admin_menu"))
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════════════
# RECEIVE FILE
# ══════════════════════════════════════════════════════════════════════════════

@router.message(AdminIngestionStates.waiting_for_file, F.document)
async def msg_receive_file(
    message: Message,
    state: FSMContext,
    bot: Bot,
    is_root_admin: bool,
    is_sub_admin: bool,
) -> None:
    if not (is_root_admin or is_sub_admin):
        return

    doc: Document = message.document
    orig_name: str = doc.file_name or "upload.txt"
    ext: str       = Path(orig_name).suffix.lower()
    file_size: int = doc.file_size or 0

    # ── Validate extension ────────────────────────────────────────────────────
    if ext not in ALLOWED_EXTENSIONS:
        await message.answer(
            f"⚠️ File type <b>{ext}</b> is not supported.\n"
            f"Please upload: <code>{', '.join(sorted(ALLOWED_EXTENSIONS))}</code>",
            parse_mode="HTML",
        )
        return  # stay in FSM state — let admin try again

    await state.clear()

    is_forwarded  = (message.forward_origin is not None or message.forward_from is not None)
    source_label  = "forwarded" if is_forwarded else "uploaded"
    size_label    = _fmt_size(file_size) if file_size else "unknown size"
    upload_path   = _unique_path(orig_name)
    admin_id      = message.from_user.id

    # ── Status message (will be updated with live progress) ───────────────────
    status_msg = await message.answer(
        f"📥 <b>Received</b> {source_label} file\n"
        f"📄 <code>{orig_name}</code>  ({size_label})\n\n"
        f"⬇️ Downloading…",
        parse_mode="HTML",
    )

    # ── Download ──────────────────────────────────────────────────────────────
    if file_size > _BOT_API_LIMIT_BYTES:
        # Large file path — Telethon required
        if not telethon_mgr.is_ready:
            await status_msg.edit_text(
                f"❌ <b>File too large for Bot API</b>\n\n"
                f"Size: <b>{size_label}</b> (limit: 19 MB)\n\n"
                "Enable large file support by setting "
                "<code>API_ID</code> and <code>API_HASH</code> in <code>.env</code>.",
                parse_mode="HTML",
                reply_markup=back_kb("admin_menu"),
            )
            return

        await status_msg.edit_text(
            f"⬇️ <b>Large file</b> ({size_label})\n"
            f"📄 <code>{orig_name}</code>\n\n"
            "Using Telethon MTProto — progress updates below…",
            parse_mode="HTML",
        )
        asyncio.create_task(
            _telethon_download_then_ingest(
                message=message,
                status_msg=status_msg,
                orig_name=orig_name,
                upload_path=str(upload_path),
                admin_id=admin_id,
                bot=bot,
            ),
            name=f"tl_ingest_{orig_name[:30]}",
        )
        return

    # Small file path — Bot API
    try:
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, destination=str(upload_path))
    except Exception as e:
        logger.error("Bot API download failed for %s: %s", orig_name, e)
        await status_msg.edit_text(
            f"❌ <b>Download failed</b>\n\n"
            f"File: <code>{orig_name}</code>\n"
            f"Error: <code>{str(e)[:300]}</code>",
            parse_mode="HTML",
            reply_markup=back_kb("admin_menu"),
        )
        return

    await status_msg.edit_text(
        f"✅ <b>Downloaded</b> <code>{orig_name}</code> ({size_label})\n\n"
        "⚙️ Indexing in background…\n"
        "You'll receive a notification when done.",
        parse_mode="HTML",
    )

    asyncio.create_task(
        ingest_file_background(
            file_path=str(upload_path),
            source_name=orig_name,
            notify_user_id=admin_id,
            bot=bot,
            status_message=status_msg,
        ),
        name=f"ingest_{orig_name[:30]}",
    )


@router.message(AdminIngestionStates.waiting_for_file)
async def msg_ingest_not_a_file(message: Message) -> None:
    """Catch any non-document message while waiting for a file upload."""
    await message.answer(
        "⚠️ Please send a <b>.txt</b>, <b>.csv</b>, or <b>.json</b> file.\n"
        "You can also forward a file from another chat.",
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TELETHON LARGE FILE DOWNLOAD + INGEST  (background task)
# ══════════════════════════════════════════════════════════════════════════════

async def _telethon_download_then_ingest(
    message: Message,
    status_msg,
    orig_name: str,
    upload_path: str,
    admin_id: int,
    bot: Bot,
) -> None:
    """Download via Telethon with progress updates, then ingest."""
    last_pct = -1

    async def _dl_progress(received: int, total: int) -> None:
        nonlocal last_pct
        if total <= 0:
            return
        pct = int(received / total * 100)
        if pct >= last_pct + 10:   # update every 10%
            last_pct = pct
            try:
                await status_msg.edit_text(
                    f"⬇️ <b>Downloading</b> <code>{orig_name}</code>\n\n"
                    f"Progress: <b>{pct}%</b>  "
                    f"({_fmt_size(received)} / {_fmt_size(total)})",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    try:
        tl_msg = await telethon_mgr.get_message(message.chat.id, message.message_id)
        if tl_msg is None or not tl_msg.document:
            raise RuntimeError(
                "Could not fetch the message via Telethon. "
                "Make sure the bot has access to this chat."
            )

        await telethon_mgr.download_file(
            message=tl_msg,
            destination=upload_path,
            progress_callback=_dl_progress,
        )

        await status_msg.edit_text(
            f"✅ <b>Download complete</b>\n"
            f"📄 <code>{orig_name}</code>\n\n"
            "⚙️ Indexing in background — progress updates below…",
            parse_mode="HTML",
        )

        await ingest_file_background(
            file_path=upload_path,
            source_name=orig_name,
            notify_user_id=admin_id,
            bot=bot,
            status_message=status_msg,
        )

    except Exception as e:
        logger.error("Telethon ingest failed for %s: %s", orig_name, e, exc_info=True)
        try:
            await status_msg.edit_text(
                f"❌ <b>Failed</b>: <code>{orig_name}</code>\n\n"
                f"Error: <code>{str(e)[:300]}</code>",
                parse_mode="HTML",
                reply_markup=back_kb("admin_menu"),
            )
        except Exception:
            pass
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# LOG SOURCE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_log_sources")
async def cb_log_sources(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    from database.queries import count_logs, get_log_sources
    from keyboards.admin_kb import admin_logs_kb

    sources = await get_log_sources()
    total   = await count_logs()

    if not sources:
        await _safe_edit(
            callback.message,
            "📂 <b>No log sources</b>\n\nUpload a file to get started.",
            parse_mode="HTML",
            reply_markup=confirm_kb("admin_menu", "admin_menu"),
        )
        await callback.answer()
        return

    await _safe_edit(
        callback.message,
        f"🗂 <b>Log Sources</b>\n\n"
        f"Total records: <b>{total:,}</b>\n\n"
        "Select a source to delete:",
        parse_mode="HTML",
        reply_markup=admin_logs_kb(sources),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_source:"))
async def cb_delete_source_prompt(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    source = callback.data.split(":", 1)[1]
    await _safe_edit(
        callback.message,
        f"⚠️ <b>Delete source?</b>\n\n"
        f"<code>{source}</code>\n\n"
        "All records from this file will be permanently removed.",
        parse_mode="HTML",
        reply_markup=confirm_kb(
            f"admin_confirm_delete_source:{source}", "admin_log_sources"
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_source:"))
async def cb_confirm_delete_source(
    callback: CallbackQuery, is_root_admin: bool, is_sub_admin: bool
) -> None:
    if not (is_root_admin or is_sub_admin):
        await callback.answer("🚫 Access denied.", show_alert=True)
        return

    from database.queries import delete_logs_by_source
    source  = callback.data.split(":", 1)[1]
    deleted = await delete_logs_by_source(source)
    await _safe_edit(
        callback.message,
        f"✅ Deleted <b>{deleted:,}</b> records from:\n<code>{source}</code>",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_log_sources", "admin_menu"),
    )
    await callback.answer(f"Deleted {deleted:,} records.")


@router.callback_query(F.data == "admin_flush_logs")
async def cb_flush_logs_prompt(callback: CallbackQuery, is_root_admin: bool) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    await _safe_edit(
        callback.message,
        "💥 <b>Flush ALL Logs</b>\n\n"
        "⚠️ This permanently deletes <b>every</b> log record and rebuilds the FTS index.\n\n"
        "This cannot be undone. Continue?",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_confirm_flush_logs", "admin_log_sources"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_confirm_flush_logs")
async def cb_confirm_flush_logs(callback: CallbackQuery, is_root_admin: bool) -> None:
    if not is_root_admin:
        await callback.answer("🚫 Root admin only.", show_alert=True)
        return

    from database.queries import flush_all_logs

    status = await callback.message.edit_text("⏳ Flushing all logs…")
    deleted = await flush_all_logs()
    await status.edit_text(
        f"✅ Flushed <b>{deleted:,}</b> records.\nFTS index rebuilt.",
        parse_mode="HTML",
        reply_markup=confirm_kb("admin_menu", "admin_menu"),
    )
    await callback.answer()
