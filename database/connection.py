"""
connection.py - Async SQLite connection manager with WAL mode + performance PRAGMAs.

Transaction notes:
  - The connection opens with isolation_level=None (autocommit).
  - This means every DML statement is auto-committed UNLESS you explicitly
    call db.conn.commit() after a batch of statements.
  - NEVER issue raw "BEGIN" / "COMMIT" / "ROLLBACK" SQL via db.execute()
    because aiosqlite already manages an implicit transaction internally
    and issuing BEGIN again raises "cannot start a transaction within a transaction".
  - For batch inserts, use db.conn.executemany(...) followed by db.conn.commit().
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)


class Database:
    """Singleton-style async SQLite wrapper."""

    def __init__(self) -> None:
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open the database and apply all performance PRAGMAs."""
        if self._conn is not None:
            return
        async with self._lock:
            if self._conn is not None:
                return
            path = str(settings.db_path)
            logger.info("Connecting to database: %s", path)
            self._conn = await aiosqlite.connect(path, isolation_level=None)
            self._conn.row_factory = aiosqlite.Row
            await self._apply_pragmas()
            logger.info("Database connected and PRAGMAs applied.")

    async def _apply_pragmas(self) -> None:
        """Apply WAL mode and performance tuning PRAGMAs."""
        pragmas = [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA cache_size = -64000;",    # 64 MB page cache
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA foreign_keys = ON;",
            "PRAGMA mmap_size = 268435456;",  # 256 MB memory-mapped I/O
        ]
        for pragma in pragmas:
            await self._conn.execute(pragma)

    async def close(self) -> None:
        """Gracefully close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    # ── Connection accessor ───────────────────────────────────────────────────

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError(
                "Database is not connected. Call `await db.connect()` first."
            )
        return self._conn

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement."""
        return await self.conn.execute(sql, params)

    async def executemany(self, sql: str, params_seq) -> None:
        """
        Execute a SQL statement against a sequence of parameter tuples.
        Uses db.conn.executemany (not db.execute) to avoid nested transactions.
        Caller must call db.conn.commit() afterwards if needed.
        """
        await self.conn.executemany(sql, params_seq)

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """Return the first row or None."""
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list:
        """Return all rows."""
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def fetchval(self, sql: str, params: tuple = ()):
        """Return the first column of the first row, or None."""
        row = await self.fetchone(sql, params)
        return row[0] if row else None


# Global singleton instance
db = Database()
