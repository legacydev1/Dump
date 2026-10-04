"""
queries.py - All SQL helper functions (CRUD + business logic queries).
Every function is async and uses the shared db singleton.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .connection import db


# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════

async def get_user(user_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    return dict(row) if row else None


async def upsert_user(user_id: int, username: str, first_name: str) -> None:
    """Insert or update basic user info. Does NOT overwrite plan data."""
    await db.execute(
        """
        INSERT INTO users (id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name
        """,
        (user_id, username or "", first_name or ""),
    )
    await db.conn.commit()


async def ensure_default_plan(user_id: int, default_plan_id: int) -> None:
    """Assign the default plan if the user has none."""
    await db.execute(
        """
        UPDATE users SET plan_id = ?
        WHERE id = ? AND plan_id IS NULL
        """,
        (default_plan_id, user_id),
    )
    await db.conn.commit()


async def get_user_with_plan(user_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        """
        SELECT u.*, p.name AS plan_name, p.daily_search_limit,
               p.cooldown_seconds, p.price, p.duration_days
        FROM users u
        LEFT JOIN plans p ON u.plan_id = p.id
        WHERE u.id = ?
        """,
        (user_id,),
    )
    return dict(row) if row else None


async def ban_user(user_id: int, banned: bool = True) -> None:
    await db.execute(
        "UPDATE users SET is_banned = ? WHERE id = ?",
        (1 if banned else 0, user_id),
    )
    await db.conn.commit()


async def assign_plan(user_id: int, plan_id: int, duration_days: int) -> None:
    expires = datetime.utcnow() + timedelta(days=duration_days)
    await db.execute(
        """
        UPDATE users
        SET plan_id = ?, plan_expires_at = ?, daily_searches = 0
        WHERE id = ?
        """,
        (plan_id, expires.isoformat(), user_id),
    )
    await db.conn.commit()


async def increment_search_count(user_id: int) -> None:
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        UPDATE users
        SET daily_searches  = daily_searches + 1,
            total_searches  = total_searches + 1,
            last_search_at  = ?
        WHERE id = ?
        """,
        (now, user_id),
    )
    await db.conn.commit()


async def reset_daily_quota(user_id: int) -> None:
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE users SET daily_searches = 0, last_reset_at = ? WHERE id = ?",
        (now, user_id),
    )
    await db.conn.commit()


async def reset_all_daily_quotas() -> int:
    """Reset daily search counters for all users. Returns affected row count."""
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        "UPDATE users SET daily_searches = 0, last_reset_at = ?", (now,)
    )
    await db.conn.commit()
    return cur.rowcount


async def get_all_users_paginated(offset: int = 0, limit: int = 20) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT u.id, u.username, u.first_name, u.is_banned,
               u.daily_searches, u.plan_expires_at, u.reward_points,
               u.total_searches, u.total_reads,
               p.name AS plan_name
        FROM users u
        LEFT JOIN plans p ON u.plan_id = p.id
        ORDER BY u.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return [dict(r) for r in rows]


async def count_users() -> int:
    return await db.fetchval("SELECT COUNT(*) FROM users") or 0


async def get_users_by_plan(plan_id: int) -> List[Dict]:
    rows = await db.fetchall(
        "SELECT id, username FROM users WHERE plan_id = ? AND is_banned = 0",
        (plan_id,),
    )
    return [dict(r) for r in rows]


async def get_all_active_users() -> List[Dict]:
    rows = await db.fetchall(
        "SELECT id, username FROM users WHERE is_banned = 0"
    )
    return [dict(r) for r in rows]


async def increment_total_reads(user_id: int) -> None:
    await db.execute(
        "UPDATE users SET total_reads = total_reads + 1 WHERE id = ?",
        (user_id,),
    )
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# PLANS
# ══════════════════════════════════════════════════════════════════════════════

async def get_plan(plan_id: int) -> Optional[Dict]:
    row = await db.fetchone("SELECT * FROM plans WHERE id = ?", (plan_id,))
    return dict(row) if row else None


async def get_active_plans() -> List[Dict]:
    rows = await db.fetchall(
        "SELECT * FROM plans WHERE is_active = 1 ORDER BY price ASC"
    )
    return [dict(r) for r in rows]


async def get_all_plans() -> List[Dict]:
    rows = await db.fetchall("SELECT * FROM plans ORDER BY price ASC")
    return [dict(r) for r in rows]


async def create_plan(
    name: str,
    daily_search_limit: int,
    cooldown_seconds: int,
    price: float,
    duration_days: int,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO plans (name, daily_search_limit, cooldown_seconds, price, duration_days)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, daily_search_limit, cooldown_seconds, price, duration_days),
    )
    await db.conn.commit()
    return cur.lastrowid


async def update_plan(plan_id: int, **kwargs) -> None:
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [plan_id]
    await db.execute(f"UPDATE plans SET {fields} WHERE id = ?", tuple(values))
    await db.conn.commit()


async def delete_plan(plan_id: int) -> None:
    await db.execute("UPDATE plans SET is_active = 0 WHERE id = ?", (plan_id,))
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# ADMINS
# ══════════════════════════════════════════════════════════════════════════════

async def get_admin(user_id: int) -> Optional[Dict]:
    row = await db.fetchone("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    return dict(row) if row else None


async def get_all_admins() -> List[Dict]:
    rows = await db.fetchall("SELECT * FROM admins ORDER BY created_at DESC")
    return [dict(r) for r in rows]


async def add_admin(user_id: int, privileges: List[str], added_by: int) -> None:
    await db.execute(
        """
        INSERT INTO admins (user_id, privileges, added_by)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET privileges = excluded.privileges
        """,
        (user_id, json.dumps(privileges), added_by),
    )
    await db.conn.commit()


async def remove_admin(user_id: int) -> None:
    await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    await db.conn.commit()


async def admin_has_privilege(user_id: int, privilege: str) -> bool:
    row = await db.fetchone(
        "SELECT privileges FROM admins WHERE user_id = ?", (user_id,)
    )
    if not row:
        return False
    privs = json.loads(row["privileges"] or "[]")
    return privilege in privs or "all" in privs


# ══════════════════════════════════════════════════════════════════════════════
# ALLOWED GROUPS
# ══════════════════════════════════════════════════════════════════════════════

async def get_allowed_groups() -> List[Dict]:
    rows = await db.fetchall(
        "SELECT * FROM allowed_groups WHERE is_active = 1 ORDER BY created_at DESC"
    )
    return [dict(r) for r in rows]


async def add_group(chat_id: int, title: str, added_by: int) -> None:
    await db.execute(
        """
        INSERT INTO allowed_groups (chat_id, title, added_by)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET is_active = 1, title = excluded.title
        """,
        (chat_id, title, added_by),
    )
    await db.conn.commit()


async def remove_group(chat_id: int) -> None:
    await db.execute(
        "UPDATE allowed_groups SET is_active = 0 WHERE chat_id = ?", (chat_id,)
    )
    await db.conn.commit()


async def is_group_allowed(chat_id: int) -> bool:
    val = await db.fetchval(
        "SELECT 1 FROM allowed_groups WHERE chat_id = ? AND is_active = 1",
        (chat_id,),
    )
    return bool(val)


# ══════════════════════════════════════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════════════════════════════════════

async def insert_logs_bulk(records: List[Tuple[str, str]]) -> int:
    """
    Bulk insert into logs table. records = [(record_text, source_file), ...]
    FTS triggers handle FTS index update automatically.
    Returns number of inserted rows.
    """
    await db.executemany(
        "INSERT INTO logs (record_text, source_file) VALUES (?, ?)",
        records,
    )
    await db.conn.commit()
    return len(records)


async def count_logs() -> int:
    return await db.fetchval("SELECT COUNT(*) FROM logs") or 0


async def delete_logs_by_source(source_file: str) -> int:
    cur = await db.execute(
        "DELETE FROM logs WHERE source_file = ?", (source_file,)
    )
    await db.conn.commit()
    return cur.rowcount


async def flush_all_logs() -> int:
    cur = await db.execute("DELETE FROM logs")
    # Rebuild FTS after full flush
    await db.execute("INSERT INTO logs_fts(logs_fts) VALUES ('rebuild')")
    await db.conn.commit()
    return cur.rowcount


async def get_log_sources() -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT source_file, COUNT(*) AS record_count, MAX(created_at) AS last_added
        FROM logs
        GROUP BY source_file
        ORDER BY last_added DESC
        """
    )
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT REQUESTS
# ══════════════════════════════════════════════════════════════════════════════

async def create_payment_request(
    user_id: int,
    plan_id: int,
    receipt_file_id: Optional[str] = None,
    note: str = "",
    method_id: Optional[int] = None,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO payment_requests (user_id, plan_id, receipt_file_id, note, method_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, plan_id, receipt_file_id, note, method_id),
    )
    await db.conn.commit()
    return cur.lastrowid


async def get_pending_payments() -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT pr.*, u.username, u.first_name, p.name AS plan_name,
               p.duration_days, pm.name AS method_name
        FROM payment_requests pr
        JOIN users u ON pr.user_id = u.id
        JOIN plans p ON pr.plan_id = p.id
        LEFT JOIN payment_methods pm ON pr.method_id = pm.id
        WHERE pr.status = 'pending'
        ORDER BY pr.created_at ASC
        """
    )
    return [dict(r) for r in rows]


async def get_payment_request(req_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        """
        SELECT pr.*, u.username, u.first_name, p.name AS plan_name,
               p.duration_days, pm.name AS method_name
        FROM payment_requests pr
        JOIN users u ON pr.user_id = u.id
        JOIN plans p ON pr.plan_id = p.id
        LEFT JOIN payment_methods pm ON pr.method_id = pm.id
        WHERE pr.id = ?
        """,
        (req_id,),
    )
    return dict(row) if row else None


async def update_payment_status(
    req_id: int, status: str, reviewed_by: int
) -> None:
    now = datetime.utcnow().isoformat()
    await db.execute(
        """
        UPDATE payment_requests
        SET status = ?, reviewed_by = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, reviewed_by, now, req_id),
    )
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# BROADCAST LOG
# ══════════════════════════════════════════════════════════════════════════════

async def log_broadcast(
    admin_id: int,
    message: str,
    target: str,
    sent_count: int,
    fail_count: int,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO broadcast_log (admin_id, message, target, sent_count, fail_count,
                                   media_type, media_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (admin_id, message, target, sent_count, fail_count, media_type, media_file_id),
    )
    await db.conn.commit()
    return cur.lastrowid


async def get_broadcast_history(limit: int = 10) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT bl.*, u.username
        FROM broadcast_log bl
        LEFT JOIN users u ON bl.admin_id = u.id
        ORDER BY bl.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# FORCE-SUBSCRIBE CHANNELS
# ══════════════════════════════════════════════════════════════════════════════

async def get_force_sub_channels(active_only: bool = True) -> List[Dict]:
    """Return all (or only active) force-sub channels ordered by creation."""
    if active_only:
        rows = await db.fetchall(
            "SELECT * FROM force_sub_channels WHERE is_active = 1 ORDER BY created_at ASC"
        )
    else:
        rows = await db.fetchall(
            "SELECT * FROM force_sub_channels ORDER BY created_at ASC"
        )
    return [dict(r) for r in rows]


async def get_force_sub_channel(channel_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        "SELECT * FROM force_sub_channels WHERE id = ?", (channel_id,)
    )
    return dict(row) if row else None


async def add_force_sub_channel(
    chat_id: str, title: str, invite_link: str, added_by: int
) -> int:
    await db.execute(
        """
        INSERT INTO force_sub_channels (chat_id, title, invite_link, is_active, added_by)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title       = excluded.title,
            invite_link = excluded.invite_link,
            is_active   = 1,
            added_by    = excluded.added_by
        """,
        (chat_id, title, invite_link, added_by),
    )
    await db.conn.commit()
    row = await db.fetchone(
        "SELECT id FROM force_sub_channels WHERE chat_id = ?", (chat_id,)
    )
    return row["id"] if row else 0


async def toggle_force_sub_channel(channel_id: int, active: bool) -> None:
    await db.execute(
        "UPDATE force_sub_channels SET is_active = ? WHERE id = ?",
        (1 if active else 0, channel_id),
    )
    await db.conn.commit()


async def delete_force_sub_channel(channel_id: int) -> None:
    await db.execute(
        "DELETE FROM force_sub_channels WHERE id = ?", (channel_id,)
    )
    await db.conn.commit()


async def update_force_sub_channel_info(
    channel_id: int, title: str, invite_link: str
) -> None:
    await db.execute(
        "UPDATE force_sub_channels SET title = ?, invite_link = ? WHERE id = ?",
        (title, invite_link, channel_id),
    )
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# PREMIUM EMOJIS
# ══════════════════════════════════════════════════════════════════════════════

async def get_all_emojis(active_only: bool = False) -> List[Dict]:
    if active_only:
        rows = await db.fetchall(
            "SELECT * FROM premium_emojis WHERE is_active = 1 ORDER BY sort_order ASC, id ASC"
        )
    else:
        rows = await db.fetchall(
            "SELECT * FROM premium_emojis ORDER BY sort_order ASC, id ASC"
        )
    return [dict(r) for r in rows]


async def get_emoji(emoji_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        "SELECT * FROM premium_emojis WHERE id = ?", (emoji_id,)
    )
    return dict(row) if row else None


async def get_emojis_by_category(category: str) -> List[Dict]:
    rows = await db.fetchall(
        "SELECT * FROM premium_emojis WHERE category = ? AND is_active = 1 ORDER BY sort_order ASC",
        (category,),
    )
    return [dict(r) for r in rows]


async def add_emoji(
    name: str,
    emoji_char: str,
    custom_emoji_id: str,
    category: str = "general",
    sort_order: int = 0,
    added_by: int = 0,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO premium_emojis (name, emoji_char, custom_emoji_id, category, sort_order, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, emoji_char, custom_emoji_id, category, sort_order, added_by),
    )
    await db.conn.commit()
    return cur.lastrowid


async def update_emoji(emoji_id: int, **kwargs) -> None:
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [emoji_id]
    await db.execute(f"UPDATE premium_emojis SET {fields} WHERE id = ?", tuple(values))
    await db.conn.commit()


async def toggle_emoji(emoji_id: int, active: bool) -> None:
    await db.execute(
        "UPDATE premium_emojis SET is_active = ? WHERE id = ?",
        (1 if active else 0, emoji_id),
    )
    await db.conn.commit()


async def delete_emoji(emoji_id: int) -> None:
    await db.execute("DELETE FROM premium_emojis WHERE id = ?", (emoji_id,))
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT METHODS
# ══════════════════════════════════════════════════════════════════════════════

async def get_all_payment_methods(active_only: bool = False) -> List[Dict]:
    if active_only:
        rows = await db.fetchall(
            "SELECT * FROM payment_methods WHERE is_active = 1 ORDER BY sort_order ASC, id ASC"
        )
    else:
        rows = await db.fetchall(
            "SELECT * FROM payment_methods ORDER BY sort_order ASC, id ASC"
        )
    return [dict(r) for r in rows]


async def get_payment_method(method_id: int) -> Optional[Dict]:
    row = await db.fetchone(
        "SELECT * FROM payment_methods WHERE id = ?", (method_id,)
    )
    return dict(row) if row else None


async def add_payment_method(
    name: str,
    account_info: str,
    emoji: str = "💳",
    description: str = "",
    sort_order: int = 0,
    added_by: int = 0,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO payment_methods (name, account_info, emoji, description, sort_order, added_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, account_info, emoji, description, sort_order, added_by),
    )
    await db.conn.commit()
    return cur.lastrowid


async def update_payment_method(method_id: int, **kwargs) -> None:
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [method_id]
    await db.execute(f"UPDATE payment_methods SET {fields} WHERE id = ?", tuple(values))
    await db.conn.commit()


async def toggle_payment_method(method_id: int, active: bool) -> None:
    await db.execute(
        "UPDATE payment_methods SET is_active = ? WHERE id = ?",
        (1 if active else 0, method_id),
    )
    await db.conn.commit()


async def delete_payment_method(method_id: int) -> None:
    await db.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
    await db.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# REWARD SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

async def get_reward_config() -> List[Dict]:
    rows = await db.fetchall(
        "SELECT * FROM reward_config ORDER BY id ASC"
    )
    return [dict(r) for r in rows]


async def get_reward_action(action_key: str) -> Optional[Dict]:
    row = await db.fetchone(
        "SELECT * FROM reward_config WHERE action_key = ? AND is_active = 1",
        (action_key,),
    )
    return dict(row) if row else None


async def update_reward_config(action_key: str, **kwargs) -> None:
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [action_key]
    await db.execute(
        f"UPDATE reward_config SET {fields} WHERE action_key = ?", tuple(values)
    )
    await db.conn.commit()


async def add_reward_action(
    action_key: str, description: str, points: int
) -> int:
    cur = await db.execute(
        """
        INSERT OR IGNORE INTO reward_config (action_key, description, points)
        VALUES (?, ?, ?)
        """,
        (action_key, description, points),
    )
    await db.conn.commit()
    return cur.lastrowid


async def award_points(user_id: int, action_key: str, note: str = "") -> int:
    """
    Award points to a user for a given action.
    Returns points awarded (0 if action not found/inactive).
    """
    action = await get_reward_action(action_key)
    if not action:
        return 0

    points = action["points"]
    now = datetime.utcnow().isoformat()

    # Log transaction
    await db.execute(
        """
        INSERT INTO reward_transactions (user_id, action_key, points, note)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, action_key, points, note),
    )
    # Update user total
    await db.execute(
        "UPDATE users SET reward_points = reward_points + ? WHERE id = ?",
        (points, user_id),
    )
    await db.conn.commit()
    return points


async def get_user_reward_history(user_id: int, limit: int = 20) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT * FROM reward_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    return [dict(r) for r in rows]


async def get_reward_leaderboard(limit: int = 10) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT u.id, u.username, u.first_name, u.reward_points
        FROM users
        WHERE is_banned = 0
        ORDER BY reward_points DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


async def deduct_points(user_id: int, points: int, note: str = "") -> bool:
    """
    Deduct points from a user. Returns False if insufficient balance.
    """
    user = await get_user(user_id)
    if not user or user.get("reward_points", 0) < points:
        return False

    await db.execute(
        """
        INSERT INTO reward_transactions (user_id, action_key, points, note)
        VALUES (?, 'deduct', ?, ?)
        """,
        (user_id, -points, note),
    )
    await db.execute(
        "UPDATE users SET reward_points = reward_points - ? WHERE id = ?",
        (points, user_id),
    )
    await db.conn.commit()
    return True


# ══════════════════════════════════════════════════════════════════════════════
# READING SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

async def log_read(
    user_id: int,
    record_text: str,
    query: str = "",
    log_id: Optional[int] = None,
) -> int:
    cur = await db.execute(
        """
        INSERT INTO reading_log (user_id, log_id, query, record_text)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, log_id, query, record_text[:1000]),
    )
    await db.conn.commit()
    await increment_total_reads(user_id)
    return cur.lastrowid


async def get_user_reading_history(user_id: int, limit: int = 20, offset: int = 0) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT * FROM reading_log
        WHERE user_id = ?
        ORDER BY read_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    )
    return [dict(r) for r in rows]


async def count_user_reads(user_id: int) -> int:
    return await db.fetchval(
        "SELECT COUNT(*) FROM reading_log WHERE user_id = ?", (user_id,)
    ) or 0


async def get_reading_stats() -> Dict:
    total = await db.fetchval("SELECT COUNT(*) FROM reading_log") or 0
    unique_users = await db.fetchval(
        "SELECT COUNT(DISTINCT user_id) FROM reading_log"
    ) or 0
    today_reads = await db.fetchval(
        "SELECT COUNT(*) FROM reading_log WHERE DATE(read_at) = DATE('now')"
    ) or 0
    return {
        "total_reads": total,
        "unique_readers": unique_users,
        "today_reads": today_reads,
    }


async def get_all_reading_logs_paginated(offset: int = 0, limit: int = 20) -> List[Dict]:
    rows = await db.fetchall(
        """
        SELECT rl.*, u.username, u.first_name
        FROM reading_log rl
        JOIN users u ON rl.user_id = u.id
        ORDER BY rl.read_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return [dict(r) for r in rows]


async def delete_user_reading_history(user_id: int) -> int:
    cur = await db.execute(
        "DELETE FROM reading_log WHERE user_id = ?", (user_id,)
    )
    await db.conn.commit()
    return cur.rowcount
