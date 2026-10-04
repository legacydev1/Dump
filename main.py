"""
main.py - Single entry point for the Telegram Log Search Bot.

Start with:
    python main.py
or via Docker:
    docker-compose up

Startup sequence:
    1. Configure logging
    2. Connect to SQLite (WAL mode)
    3. Run DB migrations (idempotent)
    4. Register middlewares (outer → inner order)
    5. Register all routers
    6. Schedule background tasks (daily quota reset)
    7. Start aiogram polling
    8. Graceful shutdown on SIGINT / SIGTERM
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import db, run_migrations
from handlers import admin_router, user_router
from middlewares import (
    AuthMiddleware, ForceSubscribeMiddleware,
    GroupSupportMiddleware, ThrottlingMiddleware,
)
from services.telethon_client import telethon_mgr

# ── Logging setup ──────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Quieten noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ── Background task: daily quota reset ────────────────────────────────────────

async def _daily_quota_reset_loop() -> None:
    """
    Reset all users' daily search counters once every 24 hours.
    Runs independently of the bot event loop — never blocks handlers.
    """
    from database.queries import reset_all_daily_quotas

    logger.info("Daily quota reset task started.")
    while True:
        # Sleep until next midnight UTC
        now = datetime.utcnow()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sleep_seconds = (next_midnight - now).total_seconds()
        logger.info(
            "Next quota reset in %.0f seconds (at %s UTC).",
            sleep_seconds,
            next_midnight.strftime("%Y-%m-%d %H:%M"),
        )
        await asyncio.sleep(sleep_seconds)

        try:
            affected = await reset_all_daily_quotas()
            logger.info("Daily quota reset complete — %d users reset.", affected)
        except Exception as e:
            logger.error("Daily quota reset failed: %s", e)


# ── Bot & Dispatcher factory ───────────────────────────────────────────────────

def _build_dispatcher() -> Dispatcher:
    """
    Create the Dispatcher, attach all middlewares and routers.
    Middleware registration order (outer → inner):
        1. ThrottlingMiddleware  — spam protection (outermost)
        2. ForceSubscribeMiddleware — channel membership gate
        3. AuthMiddleware        — user registration + role injection (innermost outer)
    """
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # ── Outer middlewares (run on every Update before routing) ─────────────────
    # Middleware order: outermost → innermost
    dp.update.outer_middleware(GroupSupportMiddleware())   # Group chat filtering
    dp.update.outer_middleware(ThrottlingMiddleware())     # Spam protection
    dp.update.outer_middleware(ForceSubscribeMiddleware()) # Channel membership gate
    dp.update.outer_middleware(AuthMiddleware())           # User registration + role injection

    # ── Routers ────────────────────────────────────────────────────────────────
    # Admin router first so admin callbacks take priority
    dp.include_router(admin_router)
    dp.include_router(user_router)

    return dp


# ── Main coroutine ─────────────────────────────────────────────────────────────

async def main() -> None:
    _setup_logging()
    logger.info("=" * 60)
    logger.info("  Telegram Log Search Bot — Starting up")
    logger.info("=" * 60)

    # Connect DB and run migrations
    await db.connect()
    await run_migrations()
    logger.info("Database ready.")

    # Start Telethon MTProto client (large file support)
    await telethon_mgr.start()

    # Ensure upload directory exists
    _ = settings.upload_dir

    # Build bot and dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = _build_dispatcher()

    # Schedule background tasks
    quota_task = asyncio.create_task(
        _daily_quota_reset_loop(), name="daily_quota_reset"
    )

    # Announce startup to all root admins
    bot_info = await bot.get_me()
    logger.info("Bot identity: @%s (ID: %s)", bot_info.username, bot_info.id)
    logger.info("Root admins: %s", settings.ADMIN_IDS)
    logger.info("Required channels: %s", settings.REQUIRED_CHANNELS)

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🟢 <b>Bot started</b>\n"
                f"@{bot_info.username} is now online.\n"
                f"DB: <code>{settings.DATABASE_PATH}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass  # Admin may not have started the bot yet

    logger.info("Starting polling…")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    finally:
        logger.info("Shutting down…")
        quota_task.cancel()
        try:
            await quota_task
        except asyncio.CancelledError:
            pass
        await telethon_mgr.stop()
        await db.close()
        await bot.session.close()
        logger.info("Shutdown complete.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt).")
