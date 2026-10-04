# 🤖 Telegram Log Search Bot

High-performance async Telegram bot for searching large log datasets.
Built with **aiogram 3.x**, **SQLite WAL + FTS5**, and a full admin dashboard.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Full-text search | SQLite FTS5 — sub-second results on 1M+ records |
| 📦 Subscription plans | Tiered daily limits, cooldowns, expiry |
| 💳 Payment workflow | Manual receipt upload → admin approval → auto-activation |
| 📥 Log ingestion | Chunked background import of `.txt` / `.csv` / `.json` |
| 🔒 Force-subscribe | Gate all access behind channel/group membership |
| 🛡 Role system | Root admin → Sub-admin → User |
| 📣 Broadcast | Rate-limited messages to all users or by plan tier |
| 💬 Group whitelist | Control which groups the bot responds in |
| 🐳 Docker-ready | Single `docker-compose up` deployment |

---

## 📁 Project Structure

```
bot/
├── main.py                  # Entry point
├── config.py                # pydantic-settings configuration
├── .env.example             # Environment variable template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── database/
│   ├── connection.py        # aiosqlite WAL singleton
│   ├── models.py            # Schema, FTS5, triggers, auto-migration
│   └── queries.py           # All SQL helpers
├── middlewares/
│   ├── force_sub.py         # Channel membership enforcement
│   ├── auth.py              # Role injection + ban check
│   └── throttling.py        # Rate limiting
├── handlers/
│   ├── user/                # start, search, plan, payment, help
│   └── admin/               # dashboard, ingestion, plans, users, groups, broadcast
├── services/
│   ├── search_engine.py     # FTS5 search + LIKE fallback
│   ├── ingestion_worker.py  # Chunked file parsing + indexing
│   ├── payment.py           # Plan activation / rejection logic
│   └── broadcast.py         # Rate-limited mass messaging
├── keyboards/
│   ├── user_kb.py
│   └── admin_kb.py
├── states/states.py         # FSM state groups
└── utils/
    ├── helpers.py
    └── text_format.py
```

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone <your-repo>
cd bot
cp .env.example .env
nano .env          # Fill in BOT_TOKEN, ADMIN_IDS, REQUIRED_CHANNELS
```

### 2. Run locally (Python)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 3. Run with Docker Compose (recommended for VPS)

```bash
docker-compose up -d
docker-compose logs -f          # Follow live logs
```

---

## ⚙️ Configuration Reference

All settings live in `.env` (copy from `.env.example`).

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | BotFather token |
| `ADMIN_IDS` | ✅ | Comma-separated root admin user IDs |
| `REQUIRED_CHANNELS` | — | Channels users must join (`@channel` or numeric ID) |
| `REQUIRED_GROUPS` | — | Groups users must join |
| `DATABASE_PATH` | — | SQLite file path (default: `data/bot.db`) |
| `UPLOAD_DIR` | — | Temp upload folder (default: `data/uploads`) |
| `MAX_FILE_SIZE_MB` | — | Max ingestable file size (default: `200`) |
| `DEFAULT_PLAN_ID` | — | Plan ID assigned to new users (default: `1` = Free) |
| `PAYMENT_INSTRUCTIONS` | — | Text shown to users when they choose to upgrade |
| `SUPPORT_CONTACT` | — | Admin/support username shown in help |
| `RESULTS_PER_PAGE` | — | Search results per page (default: `10`) |
| `INGESTION_CHUNK_SIZE` | — | DB rows per transaction during ingestion (default: `500`) |
| `LOG_LEVEL` | — | `DEBUG` / `INFO` / `WARNING` (default: `INFO`) |

---

## 🔑 Bot Commands

| Command | Access | Description |
|---|---|---|
| `/start` | All users | Welcome screen + main menu |
| `/help` | All users | FAQ and search syntax guide |
| `/admin` | Admins | Open admin dashboard |

All navigation after `/start` is handled via inline keyboard buttons.

---

## 🛠 Admin Dashboard

Access via `/admin` command. Root admins see all options; sub-admins see what their privileges allow.

### Log Ingestion
- Upload `.txt`, `.csv`, or `.json` via Telegram
- Files are processed in a background task — bot stays responsive
- Each line / row / JSON entry becomes one searchable record
- Source tracking lets you delete records by file name

### Plan Management
- Create / edit / delete subscription tiers
- Fields: name, daily search limit, cooldown (seconds), price, duration (days)
- Assign plans directly to any user

### User Management
- Paginated user list with plan and status
- Ban / unban individual users
- Override plan assignment per user

### Payment Workflow
1. User selects plan → sees price + payment instructions
2. User uploads receipt screenshot → admin is notified instantly
3. Admin taps **✅ Approve** → plan activates automatically, user is notified
4. Admin taps **❌ Reject** → user is notified with support contact

### Broadcasting
- Send HTML-formatted message to **all users** or **specific plan tier**
- Rate-limited (50ms between sends) with auto-retry on Telegram flood wait

### Group Whitelist
- Add / remove groups where the bot is allowed to operate
- Useful for restricting bot responses to your own communities

### Sub-Admin Management
- Root admin can promote any user to sub-admin
- Assign granular privilege sets: `ingest`, `plans`, `users`, `groups`, `broadcast`, `payments`, or `all`

---

## 🔍 Search Syntax

| Syntax | Example | Meaning |
|---|---|---|
| Plain keyword | `error` | Records containing "error" (prefix match) |
| AND | `error AND login` | Both terms must be present |
| OR | `error OR warning` | Either term present |
| Exact phrase | `"connection refused"` | Exact phrase match |
| Exclude | `-debug` or `NOT debug` | Records without "debug" |
| Combined | `"login failed" AND -debug` | Phrase present, "debug" absent |

---

## 🗄 Database Schema

```sql
-- Core tables
users          -- Telegram users + plan assignment + quota tracking
plans          -- Subscription tiers
admins         -- Sub-admin privileges (JSON)
allowed_groups -- Group whitelist
logs           -- Searchable log records (main data table)
payment_requests -- Payment lifecycle tracking
broadcast_log  -- Broadcast history

-- FTS5 virtual table (ultra-fast full-text search)
logs_fts       -- content='logs', synced via INSERT/UPDATE/DELETE triggers

-- Indexes
idx_users_plan, idx_users_banned
idx_logs_created, idx_logs_source
idx_allowed_groups_active
```

All PRAGMAs applied at startup:
- `journal_mode = WAL` — concurrent reads while writing
- `synchronous = NORMAL` — fast writes, safe on crash
- `cache_size = -64000` — 64 MB page cache
- `temp_store = MEMORY` — temp tables in RAM
- `mmap_size = 268435456` — 256 MB memory-mapped I/O

---

## 🐳 Production Deployment (VPS)

```bash
# 1. Copy project to your VPS
scp -r bot/ user@your-vps:/opt/logsbot

# 2. SSH in and configure
ssh user@your-vps
cd /opt/logsbot
cp .env.example .env && nano .env

# 3. Start
docker-compose up -d

# 4. View logs
docker-compose logs -f

# 5. Update bot (after code changes)
docker-compose pull
docker-compose up -d --build
```

### Systemd alternative (without Docker)

```ini
# /etc/systemd/system/logsbot.service
[Unit]
Description=Telegram Log Search Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/logsbot
ExecStart=/opt/logsbot/venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/logsbot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable logsbot
systemctl start logsbot
journalctl -u logsbot -f
```

---

## 📦 Default Subscription Plans

Seeded automatically on first start:

| ID | Name | Daily Searches | Cooldown | Price | Duration |
|---|---|---|---|---|---|
| 1 | Free | 10 | 30s | $0.00 | ∞ |
| 2 | Basic | 100 | 10s | $9.99 | 30 days |
| 3 | Pro | 500 | 5s | $24.99 | 30 days |
| 4 | Unlimited | 99,999 | 0s | $49.99 | 30 days |

Plans are fully editable via the admin dashboard.

---

## ⚡ Performance Notes

- FTS5 with `tokenize='unicode61'` handles Unicode, emoji, and multilingual logs
- Ingestion worker commits in configurable chunks (`INGESTION_CHUNK_SIZE`) — memory usage stays flat regardless of file size
- WAL mode allows concurrent reads during bulk inserts — search never blocks during ingestion
- All DB operations use a single shared `aiosqlite` connection — no pool overhead, no threading issues
- Throttling middleware protects against spam (30 msg/60s per user) without Redis

---

## 📄 License

MIT — free to use, modify, and deploy.
