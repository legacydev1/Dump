"""
text_format.py - All formatted message text builders.
All text is bold. Ultra-modern premium design with full custom emoji support.

Custom Emoji: <tg-emoji emoji-id="ID">CHAR</tg-emoji>
Renders as animated premium emojis for Telegram Premium users.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import settings
from .helpers import escape_html, format_dt, truncate
from .unicode_style import Bu, B


# ══════════════════════════════════════════════════════════════════════════════
# PREMIUM EMOJI SYSTEM — All custom_emoji_ids from your collection
# ══════════════════════════════════════════════════════════════════════════════

def pe(emoji_id: str, char: str) -> str:
    """Wrap a character in a Telegram custom premium emoji tag."""
    return f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'


# ── Core UI Emojis ─────────────────────────────────────────────────────────────
E_SPARKLES   = pe("5382178536872223059", "💫")
E_SPARKLES2  = pe("5379729370426384592", "💫")
E_SNOWFLAKE  = pe("5255974869954208458", "❄️")
E_FIRE       = pe("6235628846855492222", "🔥")
E_HEART_FIRE = pe("6147617184479711380", "❤️‍🔥")
E_CHECK      = pe("6235355429237430006", "✅")
E_CHECK2     = pe("6235478849417647339", "✅")
E_CHECK3     = pe("5854985398857503237", "✅")
E_CHECKMARK  = pe("5978564823577793291", "✔️")
E_MONEY      = pe("6235459831302460476", "💰")
E_CALENDAR   = pe("6238042150324409739", "🗓")
E_CALENDAR2  = pe("5472279086657199080", "🗓️")
E_NO         = pe("5269747893769637324", "🚫")
E_NO2        = pe("6071301770317927702", "🚫")
E_NO3        = pe("6269019133795374514", "🚫")
E_GIFT       = pe("6069089247980165250", "🎁")
E_GIFT2      = pe("6269227083226945670", "🎁")
E_GIFT3      = pe("5854802875632325328", "🎁")
E_STAR       = pe("5330519486279740988", "🌟")
E_LETTER     = pe("6131876116454970382", "💌")
E_BANK       = pe("5319236736042149889", "🏦")
E_MONEY_FACE = pe("5249054346200509700", "🤑")
E_CART       = pe("5312361253610475399", "🛒")
E_CART2      = pe("5420232672964275159", "🛒")
E_GLOBE      = pe("5433900293987261516", "🌐")
E_GEAR       = pe("5091361323392960482", "⚙️")
E_LIGHTNING  = pe("5089220900671194279", "⚡")
E_TROPHY     = pe("5330519486279740988", "🏆")
E_DIAMOND    = pe("5462902520215002477", "💎")
E_DIAMOND2   = pe("6269402803223925585", "💎")
E_DIAMOND3   = pe("5864033511970706540", "💎")
E_CROWN      = pe("5857263604130123563", "👑")
E_PIN        = pe("6037218640728691956", "📌")
E_GEM        = pe("5462902520215002477", "💎")
E_ENVELOPE   = pe("5472239203590888751", "📩")
E_THUMBS_UP  = pe("6269476006646518702", "👍")
E_LINK       = pe("6269103435413459285", "🔗")
E_BELL       = pe("6269118781331609137", "🔔")
E_MAIL_OUT   = pe("5861820727639937460", "📨")
E_DOOR       = pe("5863838791038407008", "🚪")
E_BUBBLE     = pe("5859410301799108911", "💬")
E_ARROW      = pe("5859650463485399458", "🔺")
E_CYCLONE    = pe("6039555352045819113", "🌀")
E_MAGNIFY    = pe("6001400232682722335", "🔍")
E_RED_SQ     = pe("6235430363531843239", "🟥")

# Decorative dividers using premium emojis
DIV  = f"{E_SNOWFLAKE}{'─' * 20}{E_SNOWFLAKE}"
DIV2 = f"{E_FIRE}{'━' * 18}{E_FIRE}"
DIV3 = f"{E_DIAMOND}{'─' * 20}{E_DIAMOND}"


# ══════════════════════════════════════════════════════════════════════════════
# USER TEXTS
# ══════════════════════════════════════════════════════════════════════════════

def welcome_text(user: Dict[str, Any]) -> str:
    name        = escape_html(user.get("first_name") or user.get("username") or "User")
    plan_name   = escape_html(user.get("plan_name") or "Free")
    expires     = format_dt(user.get("plan_expires_at"))
    daily_limit = user.get("daily_search_limit", 0)
    used        = user.get("daily_searches", 0)
    remaining   = max(0, daily_limit - used)
    points      = user.get("reward_points", 0)
    total_reads = user.get("total_reads", 0)
    total_srch  = user.get("total_searches", 0)

    plan_badges = {"Free": "🆓", "Basic": "⭐", "Pro": "💎", "Unlimited": "👑"}
    plan_badge  = plan_badges.get(plan_name, E_STAR)

    return (
        f"{E_SPARKLES} <b>{Bu('WELCOME BACK')}, {name}!</b> {E_SPARKLES2}\n\n"
        f"{DIV}\n"
        f"{E_CROWN} <b>{Bu('PLAN')}</b>         {plan_badge} <b>{Bu(plan_name.upper())}</b>\n"
        f"{E_CALENDAR} <b>{Bu('EXPIRES')}</b>     <b>{expires}</b>\n"
        f"{E_MAGNIFY} <b>{Bu('REMAINING')}</b>   <b>{remaining}</b><b>/</b><b>{daily_limit}</b>\n"
        f"{E_STAR} <b>{Bu('POINTS')}</b>      <b>{points:,} {Bu('PTS')}</b>\n"
        f"📖 <b>{Bu('TOTAL READS')}</b>   <b>{total_reads:,}</b>\n"
        f"{E_LIGHTNING} <b>{Bu('SEARCHES')}</b>    <b>{total_srch:,} {Bu('TOTAL')}</b>\n"
        f"{DIV}\n\n"
        f"{E_FIRE} <b>{Bu('SEARCH MODES')}:</b>\n"
        f"  🌐 <b>{Bu('DOMAIN')}</b>  │  🖥 <b>{Bu('IP')}</b>  │  📧 <b>{Bu('EMAIL')}</b>\n"
        f"  🔐 <b>{Bu('PASSWORD')}</b> │  🔗 <b>{Bu('URL')}</b>  │  🔑 <b>{Bu('KEYWORD')}</b>\n"
        f"  ✨ <b>{Bu('SMART SEARCH')}</b> <i>({Bu('FTS5 — RECOMMENDED')})</i>\n\n"
        f"{E_DIAMOND} <b>{Bu('BUY PREMIUM')} →</b> "
        f"<a href=\"https://t.me/{settings.SUPPORT_CONTACT.lstrip('@')}\">"
        f"<b>{settings.SUPPORT_CONTACT}</b></a>\n\n"
        f"{E_ARROW} <b>{Bu('USE THE MENU BELOW')}</b> {E_ARROW}"
    )


def plan_info_text(user: Dict[str, Any]) -> str:
    plan_name   = escape_html(user.get("plan_name") or "Free")
    expires     = format_dt(user.get("plan_expires_at"))
    daily_limit = user.get("daily_search_limit", 0)
    cooldown    = user.get("cooldown_seconds", 0)
    used        = user.get("daily_searches", 0)
    remaining   = max(0, daily_limit - used)
    total       = user.get("total_searches", 0)
    points      = user.get("reward_points", 0)
    reads       = user.get("total_reads", 0)

    return (
        f"{E_CROWN} <b>{Bu('YOUR ACTIVE PLAN')}</b>\n\n"
        f"{DIV2}\n"
        f"📦 <b>{Bu('PLAN NAME')}</b>       <b>{Bu(plan_name.upper())}</b>\n"
        f"{E_CALENDAR} <b>{Bu('EXPIRES')}</b>       <b>{expires}</b>\n"
        f"{E_MAGNIFY} <b>{Bu('DAILY LIMIT')}</b>   <b>{daily_limit:,}</b>\n"
        f"⏱ <b>{Bu('COOLDOWN')}</b>        <b>{cooldown}s</b>\n"
        f"{E_CHECK} <b>{Bu('REMAINING')}</b>     <b>{remaining:,} {Bu('TODAY')}</b>\n"
        f"{DIV2}\n"
        f"{E_LIGHTNING} <b>{Bu('TOTAL SEARCHES')}</b> <b>{total:,}</b>\n"
        f"📖 <b>{Bu('TOTAL READS')}</b>    <b>{reads:,}</b>\n"
        f"{E_STAR} <b>{Bu('REWARD POINTS')}</b>  <b>{points:,} {Bu('PTS')}</b>\n"
        f"{DIV2}"
    )


def help_text() -> str:
    support      = settings.SUPPORT_CONTACT
    support_link = f"https://t.me/{support.lstrip('@')}"
    return (
        f"{E_SPARKLES} <b>{Bu('HELP & FAQ')}</b> {E_SPARKLES2}\n\n"
        f"{DIV}\n"
        f"{E_MAGNIFY} <b>{Bu('SEARCH MODES')}:</b>\n"
        f"  🌐 <b>{Bu('DOMAIN')}</b>      — <code>facebook.com</code>\n"
        f"  🖥 <b>{Bu('IP ADDRESS')}</b>  — <code>192.168.1.1</code>\n"
        f"  📧 <b>{Bu('EMAIL/LOGIN')}</b> — <code>user@gmail.com</code>\n"
        f"  🔐 <b>{Bu('PASSWORD')}</b>    — <code>Admin@123</code>\n"
        f"  🔗 <b>{Bu('FULL URL')}</b>    — <code>https://site.com/login</code>\n"
        f"  🔑 <b>{Bu('KEYWORD')}</b>     — <code>admin</code>, <code>bank</code>\n"
        f"  ✨ <b>{Bu('SMART SEARCH')}</b> — <i>FTS5 across all fields</i>\n"
        f"{DIV}\n"
        f"📄 <b>{Bu('OUTPUT FORMAT')}:</b>\n"
        f"  {E_CHECK} {Bu('RESULTS SENT AS')} <code>.txt</code> {Bu('FILE')}\n"
        f"  {E_CHECK} {Bu('FORMAT')}: <code>url:login:pass</code>\n"
        f"  {E_CHECK} {Bu('ONLY COMPLETE RECORDS INCLUDED')}\n"
        f"{DIV}\n"
        f"{E_GEAR} <b>{Bu('ADVANCED SYNTAX')}:</b>\n"
        f"  <code>AND</code>  — <code>gmail AND password</code>\n"
        f"  <code>OR</code>   — <code>gmail OR yahoo</code>\n"
        f"  <code>\"phrase\"</code> — <code>\"login failed\"</code>\n"
        f"  <code>-word</code>  — <code>facebook -test</code>\n"
        f"{DIV}\n"
        f"📦 <b>{Bu('PLAN LIMITS')}:</b>\n"
        f"  🆓 <b>{Bu('FREE')}:</b>    <b>{settings.FREE_RESULT_LIMIT}</b> {Bu('RESULTS/SEARCH')}\n"
        f"  {E_CROWN} <b>{Bu('PREMIUM')}:</b> <b>{Bu('ALL RESULTS, NO CAP')}</b>\n"
        f"  {E_BELL} {Bu('RESETS EVERY MIDNIGHT UTC')}\n"
        f"{DIV}\n"
        f"{E_TROPHY} <b>{Bu('REWARD SYSTEM')}:</b>\n"
        f"  {E_STAR} {Bu('EARN POINTS FOR SEARCHES & READS')}\n"
        f"  {E_GIFT} {Bu('CHECK')} <b>{Bu('MY REWARDS')}</b> {Bu('IN MENU')}\n"
        f"{DIV}\n"
        f"{E_DIAMOND} <b>{Bu('BUY PREMIUM')}:</b>\n"
        f"  <a href=\"{support_link}\"><b>{support}</b></a>\n\n"
        f"{E_BUBBLE} <b>{Bu('SUPPORT')}:</b> <a href=\"{support_link}\"><b>{support}</b></a>"
    )


def rewards_text(user: Dict[str, Any]) -> str:
    points      = user.get("reward_points", 0)
    total_srch  = user.get("total_searches", 0)
    total_reads = user.get("total_reads", 0)
    if points >= 1000:
        badge = E_CROWN
    elif points >= 500:
        badge = E_DIAMOND
    elif points >= 100:
        badge = E_STAR
    else:
        badge = E_GIFT
    return (
        f"{E_TROPHY} <b>{Bu('YOUR REWARDS')}</b>\n\n"
        f"{DIV3}\n"
        f"{badge} <b>{Bu('TOTAL POINTS')}</b>   <b>{points:,} {Bu('PTS')}</b>\n"
        f"{E_LIGHTNING} <b>{Bu('TOTAL SEARCHES')}</b> <b>{total_srch:,}</b>\n"
        f"📖 <b>{Bu('TOTAL READS')}</b>    <b>{total_reads:,}</b>\n"
        f"{DIV3}\n\n"
        f"{E_FIRE} <b>{Bu('HOW TO EARN POINTS')}:</b>\n"
        f"  {E_CHECK} <b>{Bu('DAILY LOGIN')}</b>          — <b>+2 {Bu('PTS')}</b>\n"
        f"  {E_CHECK} <b>{Bu('SEARCH DAILY')}</b>         — <b>+5 {Bu('PTS')}</b>\n"
        f"  {E_CHECK} <b>{Bu('FIRST EVER SEARCH')}</b>    — <b>+50 {Bu('PTS')}</b>\n"
        f"  {E_CHECK} <b>{Bu('REACH 10 SEARCHES')}</b>    — <b>+20 {Bu('PTS')}</b>\n"
        f"  {E_CHECK} <b>{Bu('REACH 100 SEARCHES')}</b>   — <b>+100 {Bu('PTS')}</b>\n"
        f"  {E_GIFT} <b>{Bu('PURCHASE A PLAN')}</b>      — <b>+200 {Bu('PTS')}</b>\n"
        f"  {E_STAR} <b>{Bu('REFER A FRIEND')}</b>       — <b>+100 {Bu('PTS')}</b>\n"
        f"{DIV3}"
    )


def rewards_history_text(history: List[Dict], offset: int) -> str:
    if not history:
        return (
            f"{E_TROPHY} <b>Reward History</b>\n\n"
            f"{E_SNOWFLAKE} <b>No reward transactions yet.</b>\n\n"
            f"<i>Start searching to earn your first points!</i>"
        )

    lines = [
        f"{E_TROPHY} <b>Reward History</b>\n",
        f"{DIV3}",
    ]
    for i, tx in enumerate(history, start=offset + 1):
        sign  = "+" if tx["points"] > 0 else ""
        pts   = tx["points"]
        key   = escape_html(tx.get("action_key", ""))
        note  = escape_html(tx.get("note") or "")
        dt    = format_dt(tx.get("created_at"), "%d %b %Y %H:%M")
        icon  = E_CHECK if pts > 0 else E_RED_SQ
        lines.append(f"{icon} <b>{sign}{pts} pts</b> — <b>{key}</b>")
        if note:
            lines.append(f"   {E_PIN} <i>{note}</i>")
        lines.append(f"   {E_CALENDAR2} <i>{dt}</i>\n")
    return "\n".join(lines)


def leaderboard_text(entries: List[Dict]) -> str:
    if not entries:
        return f"{E_TROPHY} <b>Leaderboard</b>\n\n<b>No data yet.</b>"

    medals = [f"{E_CROWN}", f"{E_DIAMOND}", f"{E_STAR}"]
    lines  = [
        f"{E_TROPHY} <b>Top Reward Leaders</b>\n",
        f"{DIV2}",
    ]
    for i, e in enumerate(entries, 1):
        medal  = medals[i - 1] if i <= 3 else f"<b>{i}.</b>"
        name   = escape_html(e.get("username") or e.get("first_name") or str(e["id"]))
        points = e.get("reward_points", 0)
        lines.append(f"{medal} <b>{name}</b> — <b>{points:,} pts</b>")
    lines.append(f"\n{DIV2}")
    return "\n".join(lines)


def reading_history_text(records: List[Dict], offset: int) -> str:
    if not records:
        return (
            f"📖 <b>Reading History</b>\n\n"
            f"{E_SNOWFLAKE} <b>No reading records yet.</b>\n\n"
            f"<i>Your search results will be tracked here.</i>"
        )

    lines = [f"📖 <b>Reading History</b>\n", f"{DIV}"]
    for i, r in enumerate(records, start=offset + 1):
        query = escape_html(r.get("query") or "")
        text  = escape_html(truncate(r.get("record_text") or "", 80))
        dt    = format_dt(r.get("read_at"), "%d %b %Y %H:%M")
        lines.append(
            f"<b>{i}.</b> {E_MAGNIFY} <code>{query}</code>\n"
            f"   <code>{text}</code>\n"
            f"   {E_CALENDAR2} <i>{dt}</i>\n"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT TEXTS
# ══════════════════════════════════════════════════════════════════════════════

def payment_instructions_text(
    plan: Dict[str, Any],
    method: Optional[Dict[str, Any]] = None,
) -> str:
    plan_name    = escape_html(plan.get("name", ""))
    price        = plan.get("price", 0)
    duration     = plan.get("duration_days", 30)
    support      = settings.SUPPORT_CONTACT
    support_link = f"https://t.me/{support.lstrip('@')}"

    if method:
        method_emoji = method.get("emoji", "💳")
        method_name  = escape_html(method.get("name", ""))
        account_info = escape_html(method.get("account_info", ""))
        description  = escape_html(method.get("description") or "")

        return (
            f"{E_MONEY} <b>Buy Premium — {plan_name}</b>\n\n"
            f"{DIV2}\n"
            f"📦 <b>Plan</b>      <b>{plan_name}</b>\n"
            f"💰 <b>Price</b>     <b>${price:.2f}</b>\n"
            f"{E_CALENDAR} <b>Duration</b>  <b>{duration} days</b>\n"
            f"{DIV2}\n"
            f"{method_emoji} <b>Payment Method: {method_name}</b>\n\n"
            f"{E_BANK} <b>Send To:</b>\n"
            f"<code>{account_info}</code>\n\n"
            + (f"{E_PIN} <b>Note:</b> <i>{description}</i>\n\n" if description else "")
            + f"{DIV}\n"
            f"<b>Steps:</b>\n"
            f"<b>1️⃣</b> Send exactly <b>${price:.2f}</b> to address above\n"
            f"<b>2️⃣</b> Tap <b>📤 Send Receipt</b> below\n"
            f"<b>3️⃣</b> Upload your payment screenshot\n"
            f"<b>4️⃣</b> Wait for admin approval {E_CHECK}\n\n"
            f"{E_BUBBLE} <b>Support:</b> <a href=\"{support_link}\"><b>{support}</b></a>"
        )
    else:
        return (
            f"{E_MONEY} <b>Buy Premium — {plan_name}</b>\n\n"
            f"{DIV2}\n"
            f"📦 <b>Plan</b>      <b>{plan_name}</b>\n"
            f"💰 <b>Price</b>     <b>${price:.2f}</b>\n"
            f"{E_CALENDAR} <b>Duration</b>  <b>{duration} days</b>\n"
            f"{DIV2}\n"
            f"<b>Contact admin to complete payment:</b>\n"
            f"<a href=\"{support_link}\"><b>{support}</b></a>\n\n"
            f"<b>Send your Telegram User ID and plan name.</b>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN TEXTS
# ══════════════════════════════════════════════════════════════════════════════

def admin_stats_text(
    user_count: int,
    log_count: int,
    plan_count: int,
    pending_payments: int,
    reward_total: int = 0,
    total_reads: int = 0,
) -> str:
    return (
        f"{E_LIGHTNING} <b>{Bu('BOT STATISTICS')}</b>\n\n"
        f"{DIV2}\n"
        f"👥 <b>{Bu('TOTAL USERS')}</b>        <b>{user_count:,}</b>\n"
        f"📄 <b>{Bu('LOG RECORDS')}</b>        <b>{log_count:,}</b>\n"
        f"📦 <b>{Bu('ACTIVE PLANS')}</b>       <b>{plan_count}</b>\n"
        f"⏳ <b>{Bu('PENDING PAYMENTS')}</b>   <b>{pending_payments}</b>\n"
        f"{DIV}\n"
        f"{E_STAR} <b>{Bu('POINTS IN SYSTEM')}</b>   <b>{reward_total:,}</b>\n"
        f"📖 <b>{Bu('TOTAL READS')}</b>         <b>{total_reads:,}</b>\n"
        f"{DIV2}"
    )


def ingestion_progress_text(file_name: str, processed: int, total: Optional[int]) -> str:
    name = escape_html(file_name)
    if total and total > 0:
        pct    = int(processed / total * 100)
        filled = int(pct / 5)
        bar    = "█" * filled + "░" * (20 - filled)
        return (
            f"{E_GEAR} <b>{Bu('INGESTING')}: {name}</b>\n\n"
            f"<code>[{bar}]</code> <b>{pct}%</b>\n"
            f"{E_LIGHTNING} <b>{processed:,}</b> / <b>{total:,}</b> {Bu('RECORDS')}"
        )
    return (
        f"{E_GEAR} <b>{Bu('INGESTING')}: {name}</b>\n\n"
        f"{E_FIRE} <b>{processed:,}</b> {Bu('RECORDS PROCESSED')}…"
    )


def emoji_list_text(emojis: List[Dict]) -> str:
    if not emojis:
        return (
            f"✨ <b>Premium Emojis</b>\n\n"
            f"{E_SNOWFLAKE} <b>No emojis configured yet.</b>"
        )
    active   = sum(1 for e in emojis if e.get("is_active"))
    inactive = len(emojis) - active
    return (
        f"✨ <b>Premium Emoji Management</b>\n\n"
        f"{DIV}\n"
        f"📊 <b>Total</b>    <b>{len(emojis)}</b>\n"
        f"{E_CHECK} <b>Active</b>   <b>{active}</b>\n"
        f"{E_RED_SQ} <b>Inactive</b> <b>{inactive}</b>\n"
        f"{DIV}\n\n"
        f"<i>Tap any emoji to view or manage it.</i>"
    )


def emoji_detail_text(em: Dict) -> str:
    status  = f"{E_CHECK} Active" if em.get("is_active") else f"{E_RED_SQ} Inactive"
    char    = em.get("emoji_char", "")
    name    = escape_html(em.get("name", ""))
    eid     = em.get("custom_emoji_id") or "Not set"
    cat     = em.get("category", "general")
    sort    = em.get("sort_order", 0)
    created = format_dt(em.get("created_at"))
    # Preview the premium emoji if ID is set
    preview = pe(eid, char) if eid and eid != "Not set" else char
    return (
        f"✨ <b>Emoji Detail</b>\n\n"
        f"{DIV}\n"
        f"<b>Preview</b>    {preview}\n"
        f"<b>Char</b>       <b>{char}</b>\n"
        f"<b>Name</b>       <b>{name}</b>\n"
        f"<b>ID</b>         <code>{eid}</code>\n"
        f"<b>Category</b>   <b>{cat}</b>\n"
        f"<b>Sort</b>       <b>{sort}</b>\n"
        f"<b>Status</b>     <b>{status}</b>\n"
        f"<b>Added</b>      <i>{created}</i>\n"
        f"{DIV}"
    )


def payment_methods_list_text(methods: List[Dict]) -> str:
    if not methods:
        return (
            f"💳 <b>Payment Methods</b>\n\n"
            f"{E_SNOWFLAKE} <b>No payment methods yet.</b>\n\n"
            f"<i>Add methods so users can make payments.</i>"
        )
    active   = sum(1 for m in methods if m.get("is_active"))
    inactive = len(methods) - active
    return (
        f"💳 <b>Payment Method Management</b>\n\n"
        f"{DIV}\n"
        f"📊 <b>Total</b>    <b>{len(methods)}</b>\n"
        f"{E_CHECK} <b>Active</b>   <b>{active}</b>\n"
        f"{E_RED_SQ} <b>Inactive</b> <b>{inactive}</b>\n"
        f"{DIV}\n\n"
        f"{E_BELL} <b>Users only see ACTIVE methods.</b>"
    )


def payment_method_detail_text(m: Dict) -> str:
    status  = f"{E_CHECK} Active" if m.get("is_active") else f"{E_RED_SQ} Inactive"
    emoji   = m.get("emoji", "💳")
    name    = escape_html(m.get("name", ""))
    account = escape_html(m.get("account_info", ""))
    desc    = escape_html(m.get("description") or "None")
    sort    = m.get("sort_order", 0)
    created = format_dt(m.get("created_at"))
    return (
        f"💳 <b>Payment Method Detail</b>\n\n"
        f"{DIV}\n"
        f"<b>Emoji</b>    {emoji}\n"
        f"<b>Name</b>     <b>{name}</b>\n"
        f"<b>Account</b>  <code>{account}</code>\n"
        f"<b>Info</b>     <i>{desc}</i>\n"
        f"<b>Sort</b>     <b>{sort}</b>\n"
        f"<b>Status</b>   <b>{status}</b>\n"
        f"<b>Added</b>    <i>{created}</i>\n"
        f"{DIV}"
    )


def reward_config_text(configs: List[Dict]) -> str:
    if not configs:
        return (
            f"{E_TROPHY} <b>Reward System</b>\n\n"
            f"{E_SNOWFLAKE} <b>No reward actions configured.</b>"
        )
    lines = [
        f"{E_TROPHY} <b>Reward System Management</b>\n",
        f"{DIV2}",
    ]
    for cfg in configs:
        status = E_CHECK if cfg.get("is_active") else E_RED_SQ
        key    = cfg.get("action_key", "")
        desc   = escape_html(cfg.get("description", ""))
        pts    = cfg.get("points", 0)
        lines.append(f"{status} <b>{key}</b> — {E_STAR} <b>+{pts} pts</b>")
        lines.append(f"   <i>{desc}</i>\n")
    lines.append(DIV2)
    return "\n".join(lines)


def reading_stats_text(stats: Dict, user_count: int = 0) -> str:
    return (
        f"📖 <b>Reading System Stats</b>\n\n"
        f"{DIV3}\n"
        f"📊 <b>Total Reads</b>     <b>{stats.get('total_reads', 0):,}</b>\n"
        f"👥 <b>Unique Readers</b>  <b>{stats.get('unique_readers', 0):,}</b>\n"
        f"📅 <b>Today's Reads</b>   <b>{stats.get('today_reads', 0):,}</b>\n"
        f"{DIV3}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH RESULT TEXTS
# ══════════════════════════════════════════════════════════════════════════════

def search_result_text(
    query: str,
    results: List[Dict],
    page: int,
    total_pages: int,
    total_count: int,
) -> str:
    if not results:
        return (
            f"{E_MAGNIFY} <b>Search:</b> <code>{escape_html(query)}</code>\n\n"
            f"{E_RED_SQ} <b>No results found. Try a different query.</b>"
        )
    lines = [
        f"{E_FIRE} <b>Search:</b> <code>{escape_html(query)}</code>\n"
        f"📊 <b>Found</b> <b>{total_count}</b> result(s) — "
        f"<b>Page {page + 1}/{total_pages}</b>\n"
        f"{DIV}\n"
    ]
    for i, row in enumerate(results, start=1):
        text = escape_html(truncate(row.get("record_text", ""), 300))
        lines.append(f"<b>{i}.</b> {text}\n")
    return "\n".join(lines)
