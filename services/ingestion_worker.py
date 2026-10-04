"""
ingestion_worker.py — Robust chunked log file ingestion engine.

Supported formats  : .txt  .csv  .json  (auto-detected by extension)
Max file size      : unlimited (Telethon handles 4 GB)
Memory usage       : O(CHUNK_SIZE) — never loads the whole file

Transaction model:
  - isolation_level=None → SQLite autocommit mode
  - We use a dedicated write semaphore so only ONE ingestion writes at a time
  - Each chunk: executemany() → conn.commit()  (no manual BEGIN/COMMIT SQL)
  - On failure: conn.rollback() clears any pending transaction

Progress reporting:
  - Callback fired every PROGRESS_EVERY records so admin sees live updates
  - Caller passes an optional async progress_callback(inserted, total_estimate)
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Callable, List, Optional, Tuple

import aiofiles
from aiogram import Bot

from config import settings
from database.connection import db

logger = logging.getLogger(__name__)

CHUNK_SIZE: int = settings.INGESTION_CHUNK_SIZE  # rows per commit
PROGRESS_EVERY: int = max(CHUNK_SIZE * 10, 5000)  # report every N rows

# Global semaphore — only 1 ingestion writes to SQLite at a time
_write_semaphore = asyncio.Semaphore(1)


# ══════════════════════════════════════════════════════════════════════════════
# FILE READERS — true async line-by-line, O(1) memory
# ══════════════════════════════════════════════════════════════════════════════

async def _read_txt(path: str) -> AsyncGenerator[str, None]:
    """Yield one stripped line per log record."""
    async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
        async for raw_line in f:
            line = raw_line.rstrip("\n\r")
            if line.strip():
                yield line


async def _read_csv_streaming(path: str) -> AsyncGenerator[str, None]:
    """
    Stream a CSV file line-by-line without loading it into memory.
    Detects header row and picks the best text column automatically.
    """
    text_field: Optional[str] = None
    fieldnames: Optional[List[str]] = None

    async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
        # Read header line to detect columns
        header_line = await f.readline()
        if header_line:
            reader = csv.reader(io.StringIO(header_line))
            for row in reader:
                fieldnames = [c.strip() for c in row]
                break

        if fieldnames:
            for candidate in ("record_text", "text", "message", "log", "content", "url"):
                if candidate in fieldnames:
                    text_field = candidate
                    break

        # Stream remaining lines
        async for raw_line in f:
            raw_line = raw_line.rstrip("\n\r")
            if not raw_line.strip():
                continue
            try:
                row_vals = next(csv.reader(io.StringIO(raw_line)))
            except StopIteration:
                continue

            if text_field and fieldnames:
                try:
                    idx = fieldnames.index(text_field)
                    value = row_vals[idx].strip() if idx < len(row_vals) else ""
                except (ValueError, IndexError):
                    value = " | ".join(v for v in row_vals if v)
            else:
                value = " | ".join(v for v in row_vals if v)

            if value:
                yield value


async def _read_json(path: str) -> AsyncGenerator[str, None]:
    """
    Stream JSON records.
    Tries full-array parse first (for small files).
    Falls back to JSON-Lines streaming for large files.
    """
    file_size = os.path.getsize(path)

    # For files <= 64 MB try full JSON parse (faster for JSON arrays)
    if file_size <= 64 * 1024 * 1024:
        async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
            content = await f.read()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    line = _extract_json_item(item)
                    if line:
                        yield line
                return
        except (json.JSONDecodeError, ValueError):
            pass
        # Fall through to line-by-line
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                text = _extract_json_item(item)
                if text:
                    yield text
            except json.JSONDecodeError:
                yield line
    else:
        # Large JSON: stream line-by-line (JSON-Lines assumed)
        async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
            async for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    text = _extract_json_item(item)
                    if text:
                        yield text
                except json.JSONDecodeError:
                    if line:
                        yield line


def _extract_json_item(item) -> str:
    """Extract text from a JSON item (string or dict)."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("record_text", "text", "message", "log", "content", "url", "line"):
            if key in item and item[key]:
                return str(item[key]).strip()
        # Fallback: serialise entire object
        return json.dumps(item, ensure_ascii=False)
    return str(item).strip()


def _get_reader(path: str) -> AsyncGenerator[str, None]:
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return _read_csv_streaming(path)
    if ext == ".json":
        return _read_json(path)
    return _read_txt(path)


# ══════════════════════════════════════════════════════════════════════════════
# CORE INGESTION
# ══════════════════════════════════════════════════════════════════════════════

async def ingest_file(
    path: str,
    source_name: str,
    progress_callback: Optional[Callable] = None,
) -> Tuple[int, int]:
    """
    Stream-parse a file and bulk-insert into SQLite in CHUNK_SIZE batches.

    Uses a write semaphore so concurrent uploads don't collide.
    Fires progress_callback(inserted, skipped) every PROGRESS_EVERY records.

    Returns: (total_inserted, total_skipped)
    """
    total_inserted = 0
    total_skipped  = 0
    chunk: List[Tuple[str, str]] = []
    last_progress   = 0

    async def _flush() -> None:
        nonlocal total_inserted
        if not chunk:
            return
        async with _write_semaphore:
            try:
                await db.conn.executemany(
                    "INSERT INTO logs (record_text, source_file) VALUES (?, ?)",
                    chunk,
                )
                await db.conn.commit()
                total_inserted += len(chunk)
            except Exception as e:
                try:
                    await db.conn.rollback()
                except Exception:
                    pass
                logger.error("Chunk insert failed (%d rows): %s", len(chunk), e)
                raise
            finally:
                chunk.clear()

    async for record in _get_reader(path):
        record = record.strip()
        if not record:
            total_skipped += 1
            continue
        if len(record) > 65535:
            record = record[:65535]

        chunk.append((record, source_name))

        if len(chunk) >= CHUNK_SIZE:
            await _flush()
            # Yield control so bot stays responsive between chunks
            await asyncio.sleep(0)

            # Fire progress update
            if progress_callback and (total_inserted - last_progress) >= PROGRESS_EVERY:
                last_progress = total_inserted
                try:
                    await progress_callback(total_inserted, total_skipped)
                except Exception:
                    pass

    await _flush()  # final partial chunk

    # Final progress update
    if progress_callback:
        try:
            await progress_callback(total_inserted, total_skipped)
        except Exception:
            pass

    return total_inserted, total_skipped


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK  (called from handler)
# ══════════════════════════════════════════════════════════════════════════════

async def ingest_file_background(
    file_path: str,
    source_name: str,
    notify_user_id: int,
    bot: Bot,
    status_message=None,          # optional aiogram Message for live updates
) -> None:
    """
    Full ingestion pipeline run as an asyncio.create_task():
      1. Stream-parse and index in chunks
      2. Update progress on status_message (if provided) every PROGRESS_EVERY rows
      3. Delete the raw upload file
      4. Send completion/error notification to admin
    """
    logger.info("Ingestion started: %s → '%s'", file_path, source_name)

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    size_label = _fmt_size(file_size)
    start_time = time.monotonic()
    _last_edit  = 0.0   # throttle edit_text calls

    async def _progress(inserted: int, skipped: int) -> None:
        nonlocal _last_edit
        if status_message is None:
            return
        now = time.monotonic()
        # Throttle: edit at most once every 3 seconds
        if now - _last_edit < 3.0:
            return
        _last_edit = now
        elapsed = now - start_time
        rate    = inserted / elapsed if elapsed > 0 else 0
        try:
            await status_message.edit_text(
                f"⚙️ <b>Indexing</b> <code>{source_name}</code>\n\n"
                f"✅ Inserted : <b>{inserted:,}</b> records\n"
                f"⏭ Skipped  : <b>{skipped:,}</b>\n"
                f"⚡ Speed    : <b>{rate:,.0f}</b> rec/s\n"
                f"📦 File size: <b>{size_label}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass  # message deleted or flood — ignore

    try:
        inserted, skipped = await ingest_file(
            path=file_path,
            source_name=source_name,
            progress_callback=_progress,
        )

        elapsed = time.monotonic() - start_time
        rate    = inserted / elapsed if elapsed > 0 else 0

        # Delete the raw upload file
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning("Could not delete temp file %s: %s", file_path, e)

        msg = (
            f"✅ <b>Ingestion Complete</b>\n\n"
            f"📄 File     : <code>{source_name}</code>\n"
            f"📦 Size     : <b>{size_label}</b>\n"
            f"✅ Inserted : <b>{inserted:,}</b> records\n"
            f"⏭ Skipped  : <b>{skipped:,}</b> records\n"
            f"⏱ Time     : <b>{elapsed:.1f}s</b>  "
            f"(<b>{rate:,.0f}</b> rec/s)\n\n"
            "Records are now searchable via FTS5."
        )
        logger.info(
            "Ingestion complete: %s — inserted=%d skipped=%d time=%.1fs",
            source_name, inserted, skipped, elapsed,
        )

    except Exception as e:
        logger.error("Ingestion failed for %s: %s", file_path, e, exc_info=True)
        msg = (
            f"❌ <b>Ingestion Failed</b>\n\n"
            f"📄 File  : <code>{source_name}</code>\n"
            f"💥 Error : <code>{str(e)[:400]}</code>\n\n"
            "The raw file has been cleaned up."
        )
        try:
            os.remove(file_path)
        except OSError:
            pass

    # Notify admin
    try:
        await bot.send_message(notify_user_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning("Could not notify admin %s: %s", notify_user_id, e)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.2f} GB"
