"""
user_kb.py - All inline keyboards for regular users.
Unicode Bold Uppercase button labels. Color-coded with colored emoji indicators.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.unicode_style import (
    Bu, B,
    BTN_SEARCH, BTN_MY_PLAN, BTN_MY_REWARDS, BTN_BUY_PLAN,
    BTN_READING, BTN_HELP, BTN_BACK, BTN_BACK_MENU,
    BTN_SEARCH_AGAIN, BTN_SEND_RECEIPT, BTN_CANCEL,
    BTN_VERIFY, BTN_REWARD_HISTORY, BTN_LEADERBOARD,
    BTN_CLEAR_HISTORY, BTN_PREV, BTN_NEXT,
    BTN_MODE_DOMAIN, BTN_MODE_IP, BTN_MODE_EMAIL,
    BTN_MODE_PASS, BTN_MODE_URL, BTN_MODE_KEYWORD, BTN_MODE_SMART,
)

# Search mode labels + hints
SEARCH_MODES: Dict[str, Dict[str, str]] = {
    "domain":  {"label": "🌐 " + Bu("DOMAIN SEARCH"),   "hint": "e.g. facebook.com"},
    "ip":      {"label": "🖥 "  + Bu("IP ADDRESS"),      "hint": "e.g. 192.168.1.1"},
    "email":   {"label": "📧 " + Bu("EMAIL / LOGIN"),    "hint": "e.g. user@gmail.com"},
    "keyword": {"label": "🔑 " + Bu("KEYWORD"),          "hint": "e.g. admin, password"},
    "url":     {"label": "🔗 " + Bu("FULL URL"),         "hint": "e.g. https://site.com/login"},
    "pass":    {"label": "🔐 " + Bu("PASSWORD"),         "hint": "e.g. Admin@123"},
    "all":     {"label": "🔍 " + Bu("SMART SEARCH"),     "hint": "Search everything at once"},
}


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # 🟢 Green indicator = core feature
    builder.row(InlineKeyboardButton(
        text=f"🟢 {BTN_SEARCH}",
        callback_data="menu_search",
    ))
    builder.row(
        InlineKeyboardButton(text=f"🔵 {BTN_MY_PLAN}",    callback_data="menu_plan"),
        InlineKeyboardButton(text=f"🟡 {BTN_MY_REWARDS}", callback_data="menu_rewards"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🟣 {BTN_BUY_PLAN}",  callback_data="menu_payment"),
        InlineKeyboardButton(text=f"🔵 {BTN_READING}",   callback_data="menu_reading"),
    )
    builder.row(InlineKeyboardButton(
        text=f"⚪ {BTN_HELP}",
        callback_data="menu_help",
    ))
    return builder.as_markup()


def search_mode_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🌐 {Bu('DOMAIN')}",      callback_data="smode:domain"),
        InlineKeyboardButton(text=f"🖥 {Bu('IP ADDRESS')}",  callback_data="smode:ip"),
    )
    builder.row(
        InlineKeyboardButton(text=f"📧 {Bu('EMAIL/LOGIN')}", callback_data="smode:email"),
        InlineKeyboardButton(text=f"🔐 {Bu('PASSWORD')}",    callback_data="smode:pass"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🔗 {Bu('FULL URL')}",    callback_data="smode:url"),
        InlineKeyboardButton(text=f"🔑 {Bu('KEYWORD')}",     callback_data="smode:keyword"),
    )
    builder.row(InlineKeyboardButton(
        text=f"✨ {Bu('SMART SEARCH')}",
        callback_data="smode:all",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data="menu_back",
    ))
    return builder.as_markup()


def plan_list_kb(plans: List[Dict]) -> InlineKeyboardMarkup:
    plan_colors = ["🟢", "🔵", "🟣", "🟡", "🔴"]
    builder = InlineKeyboardBuilder()
    for i, plan in enumerate(plans):
        color = plan_colors[i % len(plan_colors)]
        label = f"{color} {Bu(plan['name'].upper())} — ${plan['price']:.2f} / {plan['duration_days']}𝐃"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"select_plan:{plan['id']}")
        )
    builder.row(InlineKeyboardButton(text=f"🔙 {Bu('BACK')}", callback_data="menu_back"))
    return builder.as_markup()


def payment_method_kb(methods: List[Dict], plan_id: int) -> InlineKeyboardMarkup:
    method_colors = ["🟢", "🔵", "🟡", "🟣", "🔴"]
    builder = InlineKeyboardBuilder()
    for i, m in enumerate(methods):
        color = method_colors[i % len(method_colors)]
        emoji = m.get("emoji", "💳")
        name  = m.get("name", "")
        builder.row(
            InlineKeyboardButton(
                text=f"{color} {emoji} {Bu(name.upper())}",
                callback_data=f"pay_method:{plan_id}:{m['id']}",
            )
        )
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data=f"select_plan:{plan_id}",
    ))
    return builder.as_markup()


def payment_confirm_kb(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🟢 {BTN_SEND_RECEIPT}", callback_data=f"send_receipt:{plan_id}"),
        InlineKeyboardButton(text=f"🔴 {BTN_CANCEL}",       callback_data="menu_back"),
    )
    return builder.as_markup()


def direct_search_kb() -> InlineKeyboardMarkup:
    """Shown while waiting for direct search query — just a back button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data="menu_back",
    ))
    return builder.as_markup()


def search_again_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"🟢 {BTN_SEARCH_AGAIN}", callback_data="menu_search"),
        InlineKeyboardButton(text=f"🔵 {BTN_BACK_MENU}",    callback_data="menu_back"),
    )
    return builder.as_markup()


def back_kb(callback: str = "menu_back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data=callback,
    ))
    return builder.as_markup()


def search_pagination_kb(
    query: str,
    page: int,
    total_pages: int,
    total_results: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav: List[InlineKeyboardButton] = []
    q_safe = query[:30]
    if page > 0:
        nav.append(InlineKeyboardButton(
            text=f"◀️ {Bu('PREV')}",
            callback_data=f"search_page:{q_safe}:{page-1}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page+1}/{total_pages}",
        callback_data="noop",
    ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text=f"{Bu('NEXT')} ▶️",
            callback_data=f"search_page:{q_safe}:{page+1}",
        ))
    if nav:
        builder.row(*nav)
    builder.row(
        InlineKeyboardButton(text=f"🟢 {Bu('NEW SEARCH')}", callback_data="menu_search"),
        InlineKeyboardButton(text=f"🔵 {Bu('MAIN MENU')}",  callback_data="menu_back"),
    )
    return builder.as_markup()


def rewards_kb(user_points: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"🟡 {BTN_REWARD_HISTORY}",
        callback_data="rewards_history",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🏆 {BTN_LEADERBOARD}",
        callback_data="rewards_leaderboard",
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data="menu_back",
    ))
    return builder.as_markup()


def rewards_history_kb(offset: int, total: int, per_page: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav: List[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text=f"◀️ {Bu('PREV')}",
            callback_data=f"rewards_hist_page:{offset - per_page}",
        ))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton(
            text=f"{Bu('NEXT')} ▶️",
            callback_data=f"rewards_hist_page:{offset + per_page}",
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text=f"🔙 {Bu('BACK')}",
        callback_data="menu_rewards",
    ))
    return builder.as_markup()


def reading_history_kb(offset: int, total: int, per_page: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav: List[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text=f"◀️ {Bu('PREV')}",
            callback_data=f"read_hist_page:{offset - per_page}",
        ))
    if offset + per_page < total:
        nav.append(InlineKeyboardButton(
            text=f"{Bu('NEXT')} ▶️",
            callback_data=f"read_hist_page:{offset + per_page}",
        ))
    if nav:
        builder.row(*nav)
    builder.row(
        InlineKeyboardButton(text=f"🔴 {BTN_CLEAR_HISTORY}", callback_data="reading_clear"),
        InlineKeyboardButton(text=f"🔙 {Bu('BACK')}",         callback_data="menu_back"),
    )
    return builder.as_markup()


def force_join_kb(buttons: list, channels: list) -> InlineKeyboardMarkup:
    """Join prompt keyboard — built dynamically in start.py."""
    from aiogram.types import InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=buttons)
