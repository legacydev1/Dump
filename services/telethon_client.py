"""
telethon_client.py - Telethon MTProto client for large file downloads.

Why Telethon instead of Bot API for downloads?
  - Bot API: max 20 MB file download
  - Telethon (user/bot account): up to 4 GB (Telegram Premium: 4 GB)

This module runs a Telethon BOT client (using the bot token, not a user account).
Bot tokens work fine with Telethon for downloading files — no phone number needed.

The client is started once at bot startup and shared as a singleton.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Callable, Awaitable

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message as TelethonMessage

from config import settings

logger = logging.getLogger(__name__)


class TelethonManager:
    """
    Singleton wrapper around a Telethon bot client.
    Uses bot token auth — no user phone number required.
    """

    def __init__(self) -> None:
        self._client: Optional[TelegramClient] = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        """
        Start the Telethon client using bot token.
        Creates/reuses the session file at TELETHON_SESSION path.
        """
        if not settings.API_ID or not settings.API_HASH:
            logger.warning(
                "API_ID / API_HASH not set — Telethon disabled. "
                "Large files (>20 MB) will not be downloadable."
            )
            return

        session_path = str(settings.TELETHON_SESSION)
        # Ensure directory exists
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)

        self._client = TelegramClient(
            session_path,
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
        )

        bot_token = settings.BOT_TOKEN
        await self._client.start(bot_token=bot_token)
        self._ready.set()
        logger.info("Telethon client started (bot mode). Large file support active.")

    async def stop(self) -> None:
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.info("Telethon client disconnected.")

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self._client.is_connected()

    @property
    def client(self) -> Optional[TelegramClient]:
        return self._client

    async def download_file(
        self,
        message: TelethonMessage,
        destination: str,
        progress_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Download the document attached to a Telethon message to `destination`.

        Args:
            message:           A Telethon Message object that has a document.
            destination:       Full file path to save the downloaded file.
            progress_callback: Optional async callable(received_bytes, total_bytes).

        Returns:
            The destination path on success, None on failure.
        """
        if not self.is_ready:
            raise RuntimeError("Telethon client is not running.")

        if not message.document:
            raise ValueError("Message has no document attached.")

        await self._client.download_media(
            message,
            file=destination,
            progress_callback=progress_callback,
        )
        return destination

    async def get_message(self, chat_id: int, message_id: int) -> Optional[TelethonMessage]:
        """
        Fetch a single message from a chat by ID.
        Used to re-fetch forwarded messages for downloading.
        """
        if not self.is_ready:
            return None
        try:
            msgs = await self._client.get_messages(chat_id, ids=message_id)
            return msgs
        except Exception as e:
            logger.error("Telethon get_message failed: %s", e)
            return None


# Global singleton
telethon_mgr = TelethonManager()
