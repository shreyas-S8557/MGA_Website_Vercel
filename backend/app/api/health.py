from __future__ import annotations

from fastapi import APIRouter

from app.utils.security import provider_status

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict:
    db_ok = True
    db_error = None
    from app.db import database

    try:
        database.count_mga_leads_by_status()
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    import app.config as config

    if db_ok and config.ON_VERCEL and not database.using_turso():
        # Works, but a SQLite file in Vercel's /tmp is lost within hours.
        db_ok = False
        db_error = (
            "Running on Vercel without TURSO_DATABASE_URL: leads are stored in "
            "temporary /tmp storage and WILL be lost. Set TURSO_DATABASE_URL and "
            "TURSO_AUTH_TOKEN."
        )

    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"status": "ok" if db_ok else "error", "path": database.describe(), "error": db_error},
    }


@router.get("/providers")
def providers() -> dict:
    return {"providers": provider_status()}
