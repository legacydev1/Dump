"""
unicode_style.py - Unicode Mathematical Bold font converter.
Converts ASCII letters to Unicode Bold (𝐀𝐁𝐂...) style.
This renders as visually bold text even without HTML tags — works in button text too.
"""

# Unicode Mathematical Bold offsets
_BOLD_UPPER_START = 0x1D400  # 𝐀
_BOLD_LOWER_START = 0x1D41A  # 𝐚
_BOLD_DIGIT_START = 0x1D7CE  # 𝟎

# Pre-built translation maps
_TO_BOLD: dict[int, str] = {}

for i in range(26):
    _TO_BOLD[ord('A') + i] = chr(_BOLD_UPPER_START + i)
    _TO_BOLD[ord('a') + i] = chr(_BOLD_LOWER_START + i)

for i in range(10):
    _TO_BOLD[ord('0') + i] = chr(_BOLD_DIGIT_START + i)


def bold(text: str) -> str:
    """Convert ASCII letters/digits to Unicode Mathematical Bold."""
    return text.translate(_TO_BOLD)


def Bu(text: str) -> str:
    """Bold + Uppercase conversion."""
    return bold(text.upper())


def B(text: str) -> str:
    """Bold (preserves case)."""
    return bold(text)


# ── Pre-built common button labels (Unicode Bold Uppercase) ───────────────────

# User Menu
BTN_SEARCH         = bold("🔍 ") + Bu("SEARCH LOGS")
BTN_MY_PLAN        = bold("📊 ") + Bu("MY PLAN")
BTN_MY_REWARDS     = bold("🏆 ") + Bu("MY REWARDS")
BTN_BUY_PLAN       = bold("💳 ") + Bu("BUY / UPGRADE PLAN")
BTN_READING        = bold("📖 ") + Bu("READING HISTORY")
BTN_HELP           = bold("❓ ") + Bu("HELP")
BTN_BACK           = bold("🔙 ") + Bu("BACK")
BTN_BACK_MENU      = bold("🏠 ") + Bu("MAIN MENU")
BTN_SEARCH_AGAIN   = bold("🔍 ") + Bu("SEARCH AGAIN")
BTN_SEND_RECEIPT   = bold("📤 ") + Bu("SEND RECEIPT")
BTN_CANCEL         = bold("❌ ") + Bu("CANCEL")
BTN_VERIFY         = bold("✅ ") + Bu("I'VE JOINED — VERIFY")
BTN_REWARD_HISTORY = bold("📋 ") + Bu("REWARD HISTORY")
BTN_LEADERBOARD    = bold("🏆 ") + Bu("LEADERBOARD")
BTN_CLEAR_HISTORY  = bold("🗑 ") + Bu("CLEAR HISTORY")

# Search Modes
BTN_MODE_DOMAIN    = bold("🌐 ") + Bu("DOMAIN")
BTN_MODE_IP        = bold("🖥 ")  + Bu("IP ADDRESS")
BTN_MODE_EMAIL     = bold("📧 ") + Bu("EMAIL / LOGIN")
BTN_MODE_PASS      = bold("🔐 ") + Bu("PASSWORD")
BTN_MODE_URL       = bold("🔗 ") + Bu("FULL URL")
BTN_MODE_KEYWORD   = bold("🔑 ") + Bu("KEYWORD")
BTN_MODE_SMART     = bold("✨ ") + Bu("SMART SEARCH (ALL)")

# Navigation
BTN_PREV           = bold("◀️ ") + Bu("PREV")
BTN_NEXT           = Bu("NEXT") + bold(" ▶️")

# Admin Menu
BTN_INGEST         = bold("📥 ") + Bu("INGEST LOGS")
BTN_LOG_SOURCES    = bold("🗂 ")  + Bu("LOG SOURCES")
BTN_PLANS          = bold("📋 ") + Bu("PLANS")
BTN_USERS          = bold("👥 ") + Bu("USERS")
BTN_GROUPS         = bold("💬 ") + Bu("GROUPS")
BTN_BROADCAST      = bold("📣 ") + Bu("BROADCAST")
BTN_PAYMENTS       = bold("⏳ ") + Bu("PENDING PAYMENTS")
BTN_SUBADMINS      = bold("👮 ") + Bu("SUB-ADMINS")
BTN_FORCE_SUB      = bold("📡 ") + Bu("FORCE-SUBSCRIBE")
BTN_PAY_METHODS    = bold("💳 ") + Bu("PAYMENT METHODS")
BTN_EMOJIS         = bold("✨ ") + Bu("PREMIUM EMOJIS")
BTN_REWARDS        = bold("🎁 ") + Bu("REWARD SYSTEM")
BTN_READING_SYS    = bold("📖 ") + Bu("READING SYSTEM")
BTN_STATS          = bold("📊 ") + Bu("STATS")
BTN_ADMIN_MENU     = bold("🔙 ") + Bu("ADMIN MENU")
BTN_NEW_PLAN       = bold("➕ ") + Bu("NEW PLAN")
BTN_ADD_GROUP      = bold("➕ ") + Bu("ADD GROUP")
BTN_ADD_CHANNEL    = bold("➕ ") + Bu("ADD CHANNEL")
BTN_ADD_EMOJI      = bold("➕ ") + Bu("ADD EMOJI")
BTN_ADD_METHOD     = bold("➕ ") + Bu("ADD METHOD")
BTN_ADD_ACTION     = bold("➕ ") + Bu("ADD ACTION")
BTN_ADD_SUBADMIN   = bold("➕ ") + Bu("ADD SUB-ADMIN")
BTN_FLUSH_LOGS     = bold("💥 ") + Bu("FLUSH ALL LOGS")
BTN_CONFIRM        = bold("✅ ") + Bu("CONFIRM")
BTN_APPROVE        = bold("✅ ") + Bu("APPROVE")
BTN_REJECT         = bold("❌ ") + Bu("REJECT")
BTN_ALL_USERS      = bold("📣 ") + Bu("ALL USERS")
BTN_TEXT_BCAST     = bold("✍️ ") + Bu("TEXT")
BTN_PHOTO_BCAST    = bold("🖼 ") + Bu("PHOTO")
BTN_VIDEO_BCAST    = bold("🎬 ") + Bu("VIDEO")
BTN_DOC_BCAST      = bold("📎 ") + Bu("DOCUMENT")
BTN_REFRESH        = bold("🔄 ") + Bu("REFRESH")
BTN_REFRESH_INFO   = bold("🔄 ") + Bu("REFRESH INFO")
BTN_TOGGLE         = bold("🔄 ") + Bu("TOGGLE")
BTN_ENABLE         = bold("✅ ") + Bu("ENABLE")
BTN_DISABLE        = bold("🔴 ") + Bu("DISABLE")
BTN_DELETE         = bold("🗑 ")  + Bu("DELETE")
BTN_EDIT           = bold("✏️ ") + Bu("EDIT")
BTN_EDIT_PLAN      = bold("✏️ ") + Bu("EDIT PLAN")
BTN_DEL_PLAN       = bold("🗑 ")  + Bu("DELETE PLAN")
BTN_ASSIGN_PLAN    = bold("💳 ") + Bu("ASSIGN PLAN")
BTN_VIEW_REWARDS   = bold("🎁 ") + Bu("VIEW REWARDS")
BTN_READ_HISTORY   = bold("📖 ") + Bu("READING HISTORY")
BTN_BAN            = bold("🚫 ") + Bu("BAN USER")
BTN_UNBAN          = bold("✅ ") + Bu("UNBAN USER")
BTN_READING_STATS  = bold("📊 ") + Bu("READING STATS")
BTN_ALL_LOGS       = bold("📋 ") + Bu("ALL READING LOGS")
BTN_USER_LOOKUP    = bold("🔍 ") + Bu("USER READ HISTORY")
BTN_MANUAL_AWARD   = bold("🎁 ") + Bu("AWARD POINTS")
BTN_YES_DELETE     = bold("✅ ") + Bu("YES, DELETE")
BTN_BACK_PLANS     = bold("🔙 ") + Bu("BACK TO PLANS")
BTN_BACK_USERS     = bold("🔙 ") + Bu("BACK TO USERS")
