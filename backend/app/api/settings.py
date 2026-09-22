from __future__ import annotations

from fastapi import APIRouter

from app.config import ALLOW_LIVE_SEND
from app.utils.security import provider_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> dict:
    return {
        "providers": provider_status(),
        "live_sending_allowed": ALLOW_LIVE_SEND,
    }
