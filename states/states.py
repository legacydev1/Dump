"""
states.py - All FSM state groups for the bot.
"""

from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    # Direct search — no mode selection, user just types query
    waiting_for_query = State()


class PaymentStates(StatesGroup):
    choosing_plan           = State()
    choosing_method         = State()
    waiting_for_txn_id      = State()   # user enters transaction ID
    waiting_for_receipt     = State()   # user sends screenshot/document
    waiting_for_note        = State()


class AdminIngestionStates(StatesGroup):
    waiting_for_file = State()


class AdminBroadcastStates(StatesGroup):
    waiting_for_content = State()
    confirming          = State()


class AdminPlanStates(StatesGroup):
    waiting_for_name     = State()
    waiting_for_limit    = State()
    waiting_for_cooldown = State()
    waiting_for_price    = State()
    waiting_for_duration = State()
    editing_field        = State()
    editing_value        = State()


class AdminUserStates(StatesGroup):
    waiting_for_user_id      = State()
    waiting_for_plan_choice  = State()


class AdminGroupStates(StatesGroup):
    waiting_for_chat_id = State()


class AdminSubAdminStates(StatesGroup):
    waiting_for_user_id    = State()
    waiting_for_privileges = State()


class AdminForceSub(StatesGroup):
    waiting_for_channel_id = State()


class AdminEmojiStates(StatesGroup):
    waiting_for_name            = State()
    waiting_for_emoji_char      = State()
    waiting_for_custom_emoji_id = State()
    waiting_for_category        = State()
    editing_field               = State()
    editing_value               = State()


class AdminPaymentMethodStates(StatesGroup):
    waiting_for_name         = State()
    waiting_for_account_info = State()
    waiting_for_emoji        = State()
    waiting_for_description  = State()
    editing_field            = State()
    editing_value            = State()


class AdminRewardStates(StatesGroup):
    waiting_for_action_key   = State()
    waiting_for_description  = State()
    waiting_for_points       = State()
    editing_field            = State()
    editing_value            = State()
    waiting_for_user_id      = State()
    waiting_for_award_points = State()
    waiting_for_award_note   = State()


class ReadingStates(StatesGroup):
    browsing = State()


class AdminReadingStates(StatesGroup):
    viewing_user_history = State()
