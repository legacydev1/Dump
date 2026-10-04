"""
admin_kb.py - All inline keyboards for admin dashboard.
Unicode Bold Uppercase labels + color-coded emoji indicators.
🟢 = action/add  🔴 = delete/danger  🔵 = info/view  🟡 = edit/modify
🟣 = system  ⚪ = neutral/back
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.unicode_style import Bu, B


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🟢 📥 {Bu('INGEST LOGS')}",     callback_data="admin_ingest"),
        InlineKeyboardButton(text=f"🔵 🗂 {Bu('LOG SOURCES')}",      callback_data="admin_log_sources"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🟣 📋 {Bu('PLANS')}",            callback_data="admin_plans"),
        InlineKeyboardButton(text=f"🔵 👥 {Bu('USERS')}",            callback_data="admin_users"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🔵 💬 {Bu('GROUPS')}",           callback_data="admin_groups"),
        InlineKeyboardButton(text=f"🟢 📣 {Bu('BROADCAST')}",        callback_data="admin_broadcast"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🟡 ⏳ {Bu('PENDING PAYMENTS')}", callback_data="admin_payments"),
        InlineKeyboardButton(text=f"🔵 👮 {Bu('SUB-ADMINS')}",       callback_data="admin_subadmins"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🟣 📡 {Bu('FORCE-SUB')}",        callback_data="admin_force_sub"),
        InlineKeyboardButton(text=f"🟢 💳 {Bu('PAY METHODS')}",      callback_data="admin_payment_methods"),
    )
    builder.row(
        InlineKeyboardButton(text=f"✨ {Bu('PREMIUM EMOJIS')}",      callback_data="admin_emojis"),
        InlineKeyboardButton(text=f"🟡 🎁 {Bu('REWARDS')}",          callback_data="admin_rewards"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🔵 📖 {Bu('READING')}",          callback_data="admin_reading"),
        InlineKeyboardButton(text=f"🔵 📊 {Bu('STATS')}",            callback_data="admin_stats"),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════

def admin_users_kb(users: List[Dict], offset: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for u in users:
        banned = "🔴" if u.get("is_banned") else "🟢"
        name   = u.get("username") or u.get("first_name") or str(u["id"])
        label  = f"{banned} {Bu(name[:25].upper())}"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"admin_user_detail:{u['id']}")
        )
    nav: List[InlineKeyboardButton] = []
    per_page = 20
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text=f"◀️ {Bu('PREV')}",
            callback_data=f"admin_users_page:{offset - per_page}",
        ))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton(
            text=f"{Bu('NEXT')} ▶️",
            callback_data=f"admin_users_page:{offset + per_page}",
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_user_detail_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.row(InlineKeyboardButton(
            text=f"🟢 ✅ {Bu('UNBAN USER')}",
            callback_data=f"admin_unban:{user_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"🔴 🚫 {Bu('BAN USER')}",
            callback_data=f"admin_ban:{user_id}",
        ))
    builder.row(InlineKeyboardButton(
        text=f"🟣 💳 {Bu('ASSIGN PLAN')}",
        callback_data=f"admin_assign_plan:{user_id}",
    ))
    builder.row(
        InlineKeyboardButton(text=f"🟡 🎁 {Bu('REWARDS')}",  callback_data=f"admin_user_rewards:{user_id}"),
        InlineKeyboardButton(text=f"🔵 📖 {Bu('READS')}",    callback_data=f"admin_user_reads:{user_id}"),
    )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK TO USERS')}",
        callback_data="admin_users",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# PLANS
# ══════════════════════════════════════════════════════════════════════════════

def admin_plans_kb(plans: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        color  = "🟢" if plan.get("is_active") else "🔴"
        label  = f"{color} {Bu(plan['name'].upper())} · ${plan['price']:.2f}"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"admin_plan_detail:{plan['id']}")
        )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('NEW PLAN')}",
        callback_data="admin_plan_new",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_plan_detail_kb(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🟡 ✏️ {Bu('EDIT PLAN')}",
        callback_data=f"admin_plan_edit:{plan_id}",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔴 🗑 {Bu('DELETE PLAN')}",
        callback_data=f"admin_plan_delete:{plan_id}",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK TO PLANS')}",
        callback_data="admin_plans",
    ))
    return builder.as_markup()


def plan_edit_field_kb(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("NAME",            "name"),
        ("DAILY LIMIT",     "daily_search_limit"),
        ("COOLDOWN (SEC)",  "cooldown_seconds"),
        ("PRICE",           "price"),
        ("DURATION (DAYS)", "duration_days"),
    ]
    for label, field in fields:
        builder.row(
            InlineKeyboardButton(
                text=f"🟡 ✏️ {Bu(label)}",
                callback_data=f"admin_plan_edit_field:{plan_id}:{field}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data=f"admin_plan_detail:{plan_id}",
    ))
    return builder.as_markup()


def admin_assign_plan_kb(plans: List[Dict], user_id: int) -> InlineKeyboardMarkup:
    colors = ["🟢", "🔵", "🟣", "🟡"]
    builder = InlineKeyboardBuilder()
    for i, plan in enumerate(plans):
        color = colors[i % len(colors)]
        builder.row(
            InlineKeyboardButton(
                text=f"{color} {Bu(plan['name'].upper())} — {plan['duration_days']}𝐃",
                callback_data=f"admin_do_assign:{user_id}:{plan['id']}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data=f"admin_user_detail:{user_id}",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════════════════════════════════════

def admin_logs_kb(sources: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for src in sources:
        name  = (src.get("source_file") or "unknown")[:28]
        count = src.get("record_count", 0)
        builder.row(
            InlineKeyboardButton(
                text=f"🔴 🗑 {Bu(name[:20].upper())} ({count:,})",
                callback_data=f"admin_delete_source:{src['source_file']}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"🔴 💥 {Bu('FLUSH ALL LOGS')}",
        callback_data="admin_flush_logs",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# GROUPS
# ══════════════════════════════════════════════════════════════════════════════

def admin_groups_kb(groups: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in groups:
        title = (g.get("title") or str(g["chat_id"]))[:28]
        builder.row(
            InlineKeyboardButton(
                text=f"🔴 🗑 {Bu(title[:22].upper())}",
                callback_data=f"admin_remove_group:{g['chat_id']}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD GROUP')}",
        callback_data="admin_group_add",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# BROADCAST
# ══════════════════════════════════════════════════════════════════════════════

def admin_broadcast_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🔵 ✍️ {Bu('TEXT')}",     callback_data="bcast_type:text"),
        InlineKeyboardButton(text=f"🟢 🖼 {Bu('PHOTO')}",    callback_data="bcast_type:photo"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🟣 🎬 {Bu('VIDEO')}",    callback_data="bcast_type:video"),
        InlineKeyboardButton(text=f"🟡 📎 {Bu('DOCUMENT')}", callback_data="bcast_type:document"),
    )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_broadcast_target_kb(plans: Optional[List[Dict]] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🟢 📣 {Bu('ALL USERS')}",
        callback_data="broadcast_target:all",
    ))
    if plans:
        plan_colors = ["🔵", "🟣", "🟡", "🔴"]
        for i, plan in enumerate(plans):
            if plan.get("is_active"):
                color = plan_colors[i % len(plan_colors)]
                builder.row(
                    InlineKeyboardButton(
                        text=f"{color} 📦 {Bu(plan['name'].upper())} {Bu('USERS')}",
                        callback_data=f"broadcast_target:plan:{plan['id']}",
                    )
                )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_broadcast_kb() -> InlineKeyboardMarkup:
    return admin_broadcast_target_kb()


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def confirm_kb(confirm_cb: str, cancel_cb: str = "admin_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🟢 ✅ {Bu('CONFIRM')}", callback_data=confirm_cb),
        InlineKeyboardButton(text=f"🔴 ❌ {Bu('CANCEL')}",  callback_data=cancel_cb),
    )
    return builder.as_markup()


def payment_review_kb(req_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🟢 ✅ {Bu('APPROVE')}", callback_data=f"payment_approve:{req_id}"),
        InlineKeyboardButton(text=f"🔴 ❌ {Bu('REJECT')}",  callback_data=f"payment_reject:{req_id}"),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ADMINS
# ══════════════════════════════════════════════════════════════════════════════

def admin_subadmins_kb(admins: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in admins:
        builder.row(
            InlineKeyboardButton(
                text=f"🔴 🗑 {Bu('REMOVE')} {a['user_id']}",
                callback_data=f"admin_remove_subadmin:{a['user_id']}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD SUB-ADMIN')}",
        callback_data="admin_add_subadmin",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# FORCE SUBSCRIBE
# ══════════════════════════════════════════════════════════════════════════════

def admin_force_sub_main_kb(channels: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not channels:
        builder.row(InlineKeyboardButton(
            text=f"⚪ {Bu('NO CHANNELS CONFIGURED')}",
            callback_data="noop",
        ))
    else:
        for ch in channels:
            status = "🟢" if ch.get("is_active") else "🔴"
            title  = (ch.get("title") or ch["chat_id"])[:22]
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {Bu(title[:20].upper())}",
                    callback_data=f"fsub_detail:{ch['id']}",
                ),
                InlineKeyboardButton(
                    text=f"🟡 {Bu('TOGGLE')}",
                    callback_data=f"fsub_toggle:{ch['id']}",
                ),
                InlineKeyboardButton(
                    text=f"🔴 🗑",
                    callback_data=f"fsub_delete_prompt:{ch['id']}",
                ),
            )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD CHANNEL')}",
        callback_data="fsub_add",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔵 🔄 {Bu('REFRESH INFO')}",
        callback_data="fsub_refresh_all",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_force_sub_detail_kb(ch_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        toggle_text = f"🔴 {Bu('DISABLE')}"
    else:
        toggle_text = f"🟢 {Bu('ENABLE')}"
    builder.row(
        InlineKeyboardButton(text=toggle_text,               callback_data=f"fsub_toggle:{ch_id}"),
        InlineKeyboardButton(text=f"🔵 🔄 {Bu('REFRESH')}", callback_data=f"fsub_refresh:{ch_id}"),
    )
    builder.row(InlineKeyboardButton(
        text=f"🔴 🗑 {Bu('DELETE')}",
        callback_data=f"fsub_delete_prompt:{ch_id}",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data="admin_force_sub",
    ))
    return builder.as_markup()


def admin_force_sub_delete_kb(ch_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🔴 ✅ {Bu('YES, DELETE')}", callback_data=f"fsub_delete:{ch_id}"),
        InlineKeyboardButton(text=f"🟢 ❌ {Bu('CANCEL')}",      callback_data="admin_force_sub"),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# PREMIUM EMOJIS
# ══════════════════════════════════════════════════════════════════════════════

def admin_emojis_kb(emojis: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not emojis:
        builder.row(InlineKeyboardButton(
            text=f"⚪ {Bu('NO EMOJIS YET')}",
            callback_data="noop",
        ))
    else:
        for em in emojis:
            status = "🟢" if em.get("is_active") else "🔴"
            char   = em.get("emoji_char", "")
            name   = em.get("name", "")[:18]
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {char} {Bu(name[:16].upper())}",
                    callback_data=f"emoji_detail:{em['id']}",
                ),
                InlineKeyboardButton(text=f"🟡 ✏️", callback_data=f"emoji_edit:{em['id']}"),
                InlineKeyboardButton(text=f"🔴 🗑",  callback_data=f"emoji_delete:{em['id']}"),
            )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD EMOJI')}",
        callback_data="emoji_add",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_emoji_detail_kb(emoji_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        toggle_text = f"🔴 {Bu('DISABLE')}"
    else:
        toggle_text = f"🟢 {Bu('ENABLE')}"
    builder.row(
        InlineKeyboardButton(text=toggle_text,               callback_data=f"emoji_toggle:{emoji_id}"),
        InlineKeyboardButton(text=f"🟡 ✏️ {Bu('EDIT')}",    callback_data=f"emoji_edit:{emoji_id}"),
    )
    builder.row(InlineKeyboardButton(
        text=f"🔴 🗑 {Bu('DELETE')}",
        callback_data=f"emoji_delete:{emoji_id}",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data="admin_emojis",
    ))
    return builder.as_markup()


def admin_emoji_edit_kb(emoji_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("NAME",            "name"),
        ("EMOJI CHAR",      "emoji_char"),
        ("CUSTOM EMOJI ID", "custom_emoji_id"),
        ("CATEGORY",        "category"),
        ("SORT ORDER",      "sort_order"),
    ]
    for label, field in fields:
        builder.row(
            InlineKeyboardButton(
                text=f"🟡 ✏️ {Bu(label)}",
                callback_data=f"emoji_edit_field:{emoji_id}:{field}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data=f"emoji_detail:{emoji_id}",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT METHODS
# ══════════════════════════════════════════════════════════════════════════════

def admin_payment_methods_kb(methods: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not methods:
        builder.row(InlineKeyboardButton(
            text=f"⚪ {Bu('NO METHODS YET')}",
            callback_data="noop",
        ))
    else:
        for m in methods:
            status = "🟢" if m.get("is_active") else "🔴"
            emoji  = m.get("emoji", "💳")
            name   = m.get("name", "")[:20]
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {emoji} {Bu(name[:18].upper())}",
                    callback_data=f"pm_detail:{m['id']}",
                ),
                InlineKeyboardButton(text=f"🟡 🔄", callback_data=f"pm_toggle:{m['id']}"),
                InlineKeyboardButton(text=f"🔴 🗑",  callback_data=f"pm_delete:{m['id']}"),
            )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD METHOD')}",
        callback_data="pm_add",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_pm_detail_kb(method_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        toggle_text = f"🔴 {Bu('DISABLE')}"
    else:
        toggle_text = f"🟢 {Bu('ENABLE')}"
    builder.row(
        InlineKeyboardButton(text=toggle_text,             callback_data=f"pm_toggle:{method_id}"),
        InlineKeyboardButton(text=f"🟡 ✏️ {Bu('EDIT')}", callback_data=f"pm_edit:{method_id}"),
    )
    builder.row(InlineKeyboardButton(
        text=f"🔴 🗑 {Bu('DELETE')}",
        callback_data=f"pm_delete:{method_id}",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data="admin_payment_methods",
    ))
    return builder.as_markup()


def admin_pm_edit_kb(method_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("NAME",         "name"),
        ("ACCOUNT INFO", "account_info"),
        ("EMOJI",        "emoji"),
        ("DESCRIPTION",  "description"),
        ("SORT ORDER",   "sort_order"),
    ]
    for label, field in fields:
        builder.row(
            InlineKeyboardButton(
                text=f"🟡 ✏️ {Bu(label)}",
                callback_data=f"pm_edit_field:{method_id}:{field}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data=f"pm_detail:{method_id}",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# REWARD SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def admin_rewards_kb(configs: List[Dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🏆 {Bu('LEADERBOARD')}",
        callback_data="reward_leaderboard",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🟢 🎁 {Bu('AWARD POINTS')}",
        callback_data="reward_award_manual",
    ))
    if configs:
        for cfg in configs:
            status = "🟢" if cfg.get("is_active") else "🔴"
            key    = cfg.get("action_key", "")[:20]
            pts    = cfg.get("points", 0)
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {Bu(key[:18].upper())} +{pts}",
                    callback_data=f"reward_config:{cfg['action_key']}",
                ),
                InlineKeyboardButton(
                    text=f"🟡 ✏️",
                    callback_data=f"reward_edit:{cfg['action_key']}",
                ),
            )
    builder.row(InlineKeyboardButton(
        text=f"🟢 ➕ {Bu('ADD ACTION')}",
        callback_data="reward_add",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_reward_config_kb(action_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🟡 ✏️ {Bu('EDIT POINTS')}",
            callback_data=f"reward_edit:{action_key}",
        ),
        InlineKeyboardButton(
            text=f"🟣 🔄 {Bu('TOGGLE')}",
            callback_data=f"reward_toggle:{action_key}",
        ),
    )
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data="admin_rewards",
    ))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════════════
# READING SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def admin_reading_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔵 📊 {Bu('READING STATS')}",
        callback_data="reading_stats",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔵 📋 {Bu('ALL READING LOGS')}",
        callback_data="reading_all_logs",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔍 {Bu('USER READ HISTORY')}",
        callback_data="reading_user_lookup",
    ))
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('ADMIN MENU')}",
        callback_data="admin_menu",
    ))
    return builder.as_markup()


def admin_reading_nav_kb(offset: int, total: int, per_page: int = 20) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav: List[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text=f"◀️ {Bu('PREV')}",
            callback_data=f"reading_page:{offset - per_page}",
        ))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton(
            text=f"{Bu('NEXT')} ▶️",
            callback_data=f"reading_page:{offset + per_page}",
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text=f"⚪ 🔙 {Bu('BACK')}",
        callback_data="admin_reading",
    ))
    return builder.as_markup()
