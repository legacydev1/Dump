"""
handlers/user/__init__.py - Assembles all user sub-routers.
"""

from aiogram import Router

from .start import router as start_router
from .search import router as search_router
from .payment import router as payment_router
from .plan import router as plan_router
from .help import router as help_router
from .rewards import router as rewards_router
from .reading import router as reading_router

user_router = Router(name="user")

user_router.include_router(start_router)
user_router.include_router(search_router)
user_router.include_router(payment_router)
user_router.include_router(plan_router)
user_router.include_router(help_router)
user_router.include_router(rewards_router)
user_router.include_router(reading_router)

__all__ = ["user_router"]
