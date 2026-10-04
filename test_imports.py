errors = []

try:
    from states.states import AdminForceSub
    print(f"states.AdminForceSub: OK — {list(AdminForceSub.__states__)}")
except Exception as e:
    errors.append(f"states FAILED: {e}")

try:
    from database.queries import (
        get_force_sub_channels,
        get_force_sub_channel,
        add_force_sub_channel,
        toggle_force_sub_channel,
        delete_force_sub_channel,
        update_force_sub_channel_info,
    )
    print("database.queries force_sub: OK")
except Exception as e:
    errors.append(f"database queries FAILED: {e}")

try:
    from middlewares.force_sub import ForceSubscribeMiddleware, invalidate_cache
    print("middlewares.force_sub: OK")
except Exception as e:
    errors.append(f"middlewares FAILED: {e}")

try:
    from keyboards.admin_kb import (
        admin_main_kb,
        admin_force_sub_main_kb,
        admin_force_sub_detail_kb,
        admin_force_sub_delete_kb,
    )
    print("keyboards.admin_kb force_sub: OK")
except Exception as e:
    errors.append(f"keyboards FAILED: {e}")

try:
    from handlers.admin.force_sub_admin import router
    print("handlers.admin.force_sub_admin: OK")
except Exception as e:
    errors.append(f"force_sub_admin handler FAILED: {e}")

try:
    from handlers import admin_router, user_router
    print("all handlers: OK")
except Exception as e:
    errors.append(f"handlers FAILED: {e}")

if errors:
    print("\n--- ERRORS ---")
    for err in errors:
        print(" ", err)
else:
    print("\nALL CHECKS PASSED ✅")
