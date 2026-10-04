"""
handlers/admin/__init__.py - Assembles all admin sub-routers.
"""

from aiogram import Router

from .broadcast import router as broadcast_router
from .dashboard import router as dashboard_router
from .emojis import router as emojis_router
from .force_sub_admin import router as force_sub_router
from .groups import router as groups_router
from .ingestion import router as ingestion_router
from .payment_methods import router as payment_methods_router
from .plans import router as plans_router
from .reading import router as reading_router
from .rewards import router as rewards_router
from .users import router as users_router

admin_router = Router(name="admin")

# Order matters: more specific routers first
admin_router.include_router(dashboard_router)
admin_router.include_router(ingestion_router)
admin_router.include_router(plans_router)
admin_router.include_router(users_router)
admin_router.include_router(groups_router)
admin_router.include_router(broadcast_router)
admin_router.include_router(force_sub_router)
admin_router.include_router(emojis_router)
admin_router.include_router(payment_methods_router)
admin_router.include_router(rewards_router)
admin_router.include_router(reading_router)

__all__ = ["admin_router"]
