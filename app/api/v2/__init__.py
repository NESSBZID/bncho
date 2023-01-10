from __future__ import annotations

from fastapi import APIRouter

from . import players
from . import sessions


apiv2_router = APIRouter(tags=["API v2"], prefix="/v2")

apiv2_router.include_router(players.router)
apiv2_router.include_router(sessions.router)
