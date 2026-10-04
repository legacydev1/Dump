"""
config.py - Central configuration using pydantic-settings.
All settings are loaded from environment variables or .env file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ──────────────────────────────────────────────────────────────────
    BOT_TOKEN: str

    # Root admins: comma-separated list of Telegram user IDs
    ADMIN_IDS: List[int] = []

    # ── Telegram MTProto API (Telethon — large file support) ─────────────────
    API_ID: Optional[int] = None
    API_HASH: Optional[str] = None
    # Telethon session file path (stored next to DB)
    TELETHON_SESSION: str = "data/telethon_session"

    # ── Force-Subscribe channels / groups ─────────────────────────────────────
    # Accepts @username or -100xxxxxxxx numeric IDs, comma-separated
    REQUIRED_CHANNELS: List[str] = []
    REQUIRED_GROUPS: List[str] = []

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_PATH: str = "data/bot.db"

    # ── File handling ─────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "data/uploads"
    # 0 = no limit (Telethon handles files of any size)
    MAX_FILE_SIZE_MB: int = 0

    # ── Plans ─────────────────────────────────────────────────────────────────
    DEFAULT_PLAN_ID: int = 1          # ID of the free/default plan in DB

    # ── Payment ───────────────────────────────────────────────────────────────
    PAYMENT_INSTRUCTIONS: str = (
        "Send payment to the following address and forward the receipt to admin."
    )
    SUPPORT_CONTACT: str = "@admin"

    # ── Search result limits ──────────────────────────────────────────────────
    # Free users get at most this many log lines per search query (as .txt file)
    FREE_RESULT_LIMIT: int = 50
    # Plan IDs that are considered "premium" (get ALL results, no cap)
    # Comma-separated integers or JSON list
    PREMIUM_PLAN_IDS: List[int] = [2, 3, 4]

    # ── Bot behaviour ─────────────────────────────────────────────────────────
    RESULTS_PER_PAGE: int = 10
    INGESTION_CHUNK_SIZE: int = 500   # rows committed per transaction

    # ── Search Response Video ─────────────────────────────────────────────────
    # Telegram file_id of a video to send with every search result.
    # Leave empty to disable video responses.
    SEARCH_RESULT_VIDEO: Optional[str] = None

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("ADMIN_IDS", "PREMIUM_PLAN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v if v is not None else []

    @field_validator("REQUIRED_CHANNELS", "REQUIRED_GROUPS", mode="before")
    @classmethod
    def parse_str_list(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v or v in ("[]", ""):
                return []
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v if v is not None else []

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def db_path(self) -> Path:
        p = Path(self.DATABASE_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def upload_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


# Singleton – import this everywhere
settings = Settings()
