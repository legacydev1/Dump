"""
models.py - All table schemas, FTS5 virtual table, triggers, and auto-migration.
Run run_migrations() once at startup — it is idempotent (CREATE IF NOT EXISTS).
"""

from __future__ import annotations

import logging

from .connection import db

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# DDL statements
# ──────────────────────────────────────────────────────────────────────────────

_PLANS_TABLE = """
CREATE TABLE IF NOT EXISTS plans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL UNIQUE,
    daily_search_limit  INTEGER NOT NULL DEFAULT 10,
    cooldown_seconds    INTEGER NOT NULL DEFAULT 0,
    price               REAL    NOT NULL DEFAULT 0.0,
    duration_days       INTEGER NOT NULL DEFAULT 30,
    is_active           BOOLEAN NOT NULL DEFAULT 1,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,    -- Telegram user_id
    username        TEXT,
    first_name      TEXT,
    plan_id         INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    plan_expires_at DATETIME,
    is_banned       BOOLEAN NOT NULL DEFAULT 0,
    daily_searches  INTEGER NOT NULL DEFAULT 0,
    last_search_at  DATETIME,
    last_reset_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_searches  INTEGER NOT NULL DEFAULT 0,
    reward_points   INTEGER NOT NULL DEFAULT 0,
    total_reads     INTEGER NOT NULL DEFAULT 0,
    referral_count  INTEGER NOT NULL DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_ADMINS_TABLE = """
CREATE TABLE IF NOT EXISTS admins (
    user_id     INTEGER PRIMARY KEY,
    privileges  TEXT NOT NULL DEFAULT '[]',   -- JSON array of allowed actions
    added_by    INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_ALLOWED_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS allowed_groups (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT,
    added_by    INTEGER,
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    record_text TEXT    NOT NULL,
    source_file TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_LOGS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS logs_fts USING fts5(
    record_text,
    content='logs',
    content_rowid='id',
    tokenize='unicode61'
);
"""

# Triggers that keep FTS index in sync with the logs table
_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS logs_ai AFTER INSERT ON logs BEGIN
    INSERT INTO logs_fts(rowid, record_text) VALUES (new.id, new.record_text);
END;

CREATE TRIGGER IF NOT EXISTS logs_ad AFTER DELETE ON logs BEGIN
    INSERT INTO logs_fts(logs_fts, rowid, record_text) VALUES ('delete', old.id, old.record_text);
END;

CREATE TRIGGER IF NOT EXISTS logs_au AFTER UPDATE ON logs BEGIN
    INSERT INTO logs_fts(logs_fts, rowid, record_text) VALUES ('delete', old.id, old.record_text);
    INSERT INTO logs_fts(rowid, record_text) VALUES (new.id, new.record_text);
END;
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_users_plan        ON users(plan_id);
CREATE INDEX IF NOT EXISTS idx_users_banned      ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_logs_created      ON logs(created_at);
CREATE INDEX IF NOT EXISTS idx_logs_source       ON logs(source_file);
CREATE INDEX IF NOT EXISTS idx_allowed_groups_active ON allowed_groups(is_active);
"""

_PAYMENT_REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    plan_id     INTEGER NOT NULL REFERENCES plans(id),
    method_id   INTEGER REFERENCES payment_methods(id),
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    receipt_file_id TEXT,
    note        TEXT,
    reviewed_by INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_BROADCAST_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS broadcast_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id        INTEGER NOT NULL,
    message         TEXT    NOT NULL,
    media_type      TEXT,               -- NULL | photo | video | document
    media_file_id   TEXT,
    target          TEXT    NOT NULL DEFAULT 'all',   -- all | plan:<id>
    sent_count      INTEGER NOT NULL DEFAULT 0,
    fail_count      INTEGER NOT NULL DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Force-subscribe channels managed dynamically from admin panel
_FORCE_SUB_TABLE = """
CREATE TABLE IF NOT EXISTS force_sub_channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     TEXT    NOT NULL UNIQUE,   -- @username or -100xxx numeric id
    title       TEXT,
    invite_link TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    added_by    INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# ── NEW TABLES ─────────────────────────────────────────────────────────────────

# Premium custom emoji storage — admin managed
_PREMIUM_EMOJIS_TABLE = """
CREATE TABLE IF NOT EXISTS premium_emojis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,          -- friendly label e.g. "fire"
    emoji_char      TEXT    NOT NULL,          -- standard emoji char e.g. 🔥
    custom_emoji_id TEXT,                      -- Telegram custom_emoji_id string
    category        TEXT    NOT NULL DEFAULT 'general',  -- general|status|reward|ui
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    added_by        INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Payment methods — admin managed (bKash, Nagad, USDT, etc.)
_PAYMENT_METHODS_TABLE = """
CREATE TABLE IF NOT EXISTS payment_methods (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,   -- e.g. "bKash", "Nagad", "USDT TRC20"
    account_info    TEXT    NOT NULL,          -- account number / address / instructions
    emoji           TEXT    NOT NULL DEFAULT '💳',
    description     TEXT,                      -- optional extra instructions
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    added_by        INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Reward actions config — admin defines what earns how many points
_REWARD_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS reward_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action_key      TEXT    NOT NULL UNIQUE,   -- "first_search", "daily_login", "referral", etc.
    description     TEXT    NOT NULL,
    points          INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Reward transactions log
_REWARD_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS reward_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    action_key  TEXT    NOT NULL,
    points      INTEGER NOT NULL,
    note        TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Reading log — track which records users have read/viewed
_READING_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS reading_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    log_id      INTEGER REFERENCES logs(id) ON DELETE SET NULL,
    query       TEXT,
    record_text TEXT,
    read_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# ──────────────────────────────────────────────────────────────────────────────
# Seed data
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_PLANS = """
INSERT OR IGNORE INTO plans (id, name, daily_search_limit, cooldown_seconds, price, duration_days)
VALUES
    (1, 'Free',        5,   30, 0.0,   0),
    (2, 'Basic',     100,   10, 9.99,  30),
    (3, 'Pro',       500,    5, 24.99, 30),
    (4, 'Unlimited', 99999,  0, 49.99, 30);
"""

_DEFAULT_PREMIUM_EMOJIS = """
INSERT OR IGNORE INTO premium_emojis (id, name, emoji_char, custom_emoji_id, category, sort_order)
VALUES
    (1,  'sparkles',       '💫', '5382178536872223059', 'general',  1),
    (2,  'sparkles_alt',   '💫', '5379729370426384592', 'general',  2),
    (3,  'snowflake',      '❄️', '5255974869954208458', 'general',  3),
    (4,  'fire',           '🔥', '6235628846855492222', 'status',   4),
    (5,  'heart_fire',     '❤️‍🔥','6147617184479711380', 'status',   5),
    (6,  'check_green',    '✅', '6235355429237430006', 'ui',       6),
    (7,  'check_green2',   '✅', '6235478849417647339', 'ui',       7),
    (8,  'money_bag',      '💰', '6235459831302460476', 'reward',   8),
    (9,  'calendar',       '🗓', '6238042150324409739', 'ui',       9),
    (10, 'calendar2',      '🗓', '6235478329726604939', 'ui',      10),
    (11, 'red_square',     '🟥', '6235430363531843239', 'status',  11),
    (12, 'check_mark',     '✔️', '5978564823577793291', 'ui',      12),
    (13, 'no_entry',       '🚫', '5269747893769637324', 'status',  13),
    (14, 'no_entry2',      '🚫', '6071301770317927702', 'status',  14),
    (15, 'gift',           '🎁', '6069089247980165250', 'reward',  15),
    (16, 'gift2',          '🎁', '6269227083226945670', 'reward',  16),
    (17, 'star',           '🌟', '5330519486279740988', 'reward',  17),
    (18, 'letter',         '💌', '6131876116454970382', 'ui',      18),
    (19, 'bank',           '🏦', '5319236736042149889', 'general', 19),
    (20, 'bank2',          '🏦', '5318823508648669340', 'general', 20),
    (21, 'money_wings',    '🤑', '5249054346200509700', 'reward',  21),
    (22, 'cart',           '🛒', '5312361253610475399', 'general', 22),
    (23, 'cart2',          '🛒', '5420232672964275159', 'general', 23),
    (24, 'cart3',          '🛒', '5440841102871517055', 'general', 24),
    (25, 'cart4',          '🛒', '5400090058030075645', 'general', 25),
    (26, 'globe',          '🌐', '5433900293987261516', 'general', 26),
    (27, 'gear',           '⚙️', '5091361323392960482', 'ui',      27),
    (28, 'lightning',      '⚡', '5089220900671194279', 'ui',      28),
    (29, 'woman_laptop',   '👩‍💻','5091637150487677308', 'general', 29),
    (30, 'penguin',        '🐧', '5091406996075185015', 'general', 30),
    (31, 'man_grey',       '👨‍🦳','5292058354791756351', 'general', 31),
    (32, 'snake',          '🐍', '5226717982230591144', 'general', 32),
    (33, 'penguin2',       '🐧', '5220079341475503874', 'general', 33),
    (34, 'trophy',         '🏆', '5330519486279740988', 'reward',  34),
    (35, 'diamond',        '💎', '5462902520215002477', 'status',  35),
    (36, 'diamond2',       '💎', '6269402803223925585', 'status',  36),
    (37, 'diamond3',       '💎', '5864033511970706540', 'status',  37),
    (38, 'crown',          '👑', '5249054346200509700', 'status',  38),
    (39, 'crown2',         '👑', '5857263604130123563', 'status',  39),
    (40, 'walker_man',     '🚶‍♂️','5377304290157156187', 'general', 40),
    (41, 'pin',            '📌', '6037218640728691956', 'ui',      41),
    (42, 'calendar3',      '🗓️', '5472279086657199080', 'ui',      42),
    (43, 'gem',            '💎', '5462902520215002477', 'reward',  43),
    (44, 'envelope_in',    '📨', '5472239203590888751', 'ui',      44),
    (45, 'no_entry3',      '🚫', '6269019133795374514', 'status',  45),
    (46, 'thumbs_up',      '👍', '6269476006646518702', 'ui',      46),
    (47, 'link',           '🔗', '6269103435413459285', 'ui',      47),
    (48, 'bell',           '🔔', '6269118781331609137', 'ui',      48),
    (49, 'incoming_mail',  '📩', '5472239203590888751', 'ui',      49),
    (50, 'outgoing_mail',  '📨', '5861820727639937460', 'ui',      50),
    (51, 'door',           '🚪', '5863838791038407008', 'general', 51),
    (52, 'speech_bubble',  '💬', '5859410301799108911', 'ui',      52),
    (53, 'gift3',          '🎁', '5854802875632325328', 'reward',  53),
    (54, 'arrow_right',    '🔺', '5859650463485399458', 'ui',      54),
    (55, 'gem2',           '💎', '5864033511970706540', 'reward',  55),
    (56, 'check3',         '✅', '5854985398857503237', 'ui',      56),
    (57, 'cyclone',        '🌀', '6039555352045819113', 'general', 57),
    (58, 'cat',            '🐱', '5417836094098007862', 'general', 58),
    (59, 'magnify',        '🔍', '6001400232682722335', 'general', 59),
    (60, 'search_lens',   '🔍', '5039649904264217620', 'ui',      60);
"""

_DEFAULT_REWARD_CONFIG = """
INSERT OR IGNORE INTO reward_config (action_key, description, points)
VALUES
    ('first_search',    'First ever search',                    50),
    ('daily_search',    'Search once per day (daily reward)',   5),
    ('daily_login',     'Open bot daily',                       2),
    ('referral',        'Refer a new user',                     100),
    ('plan_purchase',   'Purchase any paid plan',               200),
    ('read_record',     'Read/view a log record',               1),
    ('search_10',       'Complete 10 searches total',           20),
    ('search_100',      'Complete 100 searches total',          100);
"""

# ──────────────────────────────────────────────────────────────────────────────
# Migration runner
# ──────────────────────────────────────────────────────────────────────────────

async def run_migrations() -> None:
    """
    Idempotent migration: creates all tables, FTS, triggers, indexes, and
    seeds default plans. Safe to call on every startup.
    """
    logger.info("Running database migrations…")

    # Create new tables FIRST (so payment_requests FK works)
    await db.execute(_PREMIUM_EMOJIS_TABLE)
    await db.execute(_PAYMENT_METHODS_TABLE)
    await db.execute(_REWARD_CONFIG_TABLE)
    await db.execute(_REWARD_TRANSACTIONS_TABLE)

    statements = [
        _PLANS_TABLE,
        _USERS_TABLE,
        _ADMINS_TABLE,
        _ALLOWED_GROUPS_TABLE,
        _LOGS_TABLE,
        _LOGS_FTS,
        _LOGS_TABLE,       # ensure logs exists before triggers
    ]

    # Execute individual table creates
    for stmt in statements:
        await db.execute(stmt)

    # FTS triggers (multi-statement — execute one at a time)
    for trigger_sql in _FTS_TRIGGERS.strip().split("END;"):
        t = trigger_sql.strip()
        if t:
            await db.execute(t + " END;")

    # Indexes
    for index_sql in _INDEXES.strip().split(";"):
        s = index_sql.strip()
        if s:
            await db.execute(s + ";")

    # Additional tables
    await db.execute(_PAYMENT_REQUESTS_TABLE)
    await db.execute(_BROADCAST_LOG_TABLE)
    await db.execute(_FORCE_SUB_TABLE)
    await db.execute(_READING_LOG_TABLE)

    # Add new columns to existing tables (idempotent via try/except)
    _new_user_columns = [
        ("total_searches", "INTEGER NOT NULL DEFAULT 0"),
        ("reward_points",  "INTEGER NOT NULL DEFAULT 0"),
        ("total_reads",    "INTEGER NOT NULL DEFAULT 0"),
        ("referral_count", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, col_def in _new_user_columns:
        try:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass  # Column already exists

    _new_broadcast_columns = [
        ("media_type",    "TEXT"),
        ("media_file_id", "TEXT"),
    ]
    for col_name, col_def in _new_broadcast_columns:
        try:
            await db.execute(f"ALTER TABLE broadcast_log ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    _new_payment_req_columns = [
        ("method_id", "INTEGER"),
    ]
    for col_name, col_def in _new_payment_req_columns:
        try:
            await db.execute(f"ALTER TABLE payment_requests ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass

    # Seed default data
    await db.execute(_DEFAULT_PLANS)
    # For emojis: use INSERT OR REPLACE to update existing entries with new IDs
    await db.execute(_DEFAULT_PREMIUM_EMOJIS.replace("INSERT OR IGNORE", "INSERT OR REPLACE"))
    await db.execute(_DEFAULT_REWARD_CONFIG)

    # Seed force-sub channels from config if table is empty
    from config import settings as _s
    for _ch in (_s.REQUIRED_CHANNELS + _s.REQUIRED_GROUPS):
        if _ch:
            await db.execute(
                """
                INSERT OR IGNORE INTO force_sub_channels (chat_id, title, is_active, added_by)
                VALUES (?, ?, 1, 0)
                """,
                (_ch, _ch),
            )

    await db.conn.commit()
    logger.info("Migrations complete.")
