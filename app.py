"""
Taskforce Management System - FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from database.engine import create_db


# -- Background scheduler -------------------------------------------------------

def _make_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    return AsyncIOScheduler()


scheduler = _make_scheduler()


def _sync_job():
    """Blocking Roblox sync - called via asyncio.to_thread so it does not block the loop."""
    from database.engine import get_session
    from utils.roblox_sync import sync_from_roblox

    session_gen = get_session()
    session = next(session_gen)
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*60}\n?? [{ts}] Starting automatic Roblox sync...\n{'='*60}")
        result = sync_from_roblox()
        if result.get("success"):
            stats = result.get("stats", {})
            print(
                f"? Roblox sync completed: {stats.get('added', 0)} added, "
                f"{stats.get('updated', 0)} updated, {stats.get('rank_changes', 0)} rank changes"
            )
        else:
            print(f"??  Roblox sync failed: {result.get('message', 'Unknown error')}")
    except Exception as exc:
        print(f"? Background Roblox sync error: {exc}")
    finally:
        try:
            session_gen.close()
        except Exception:
            pass


async def _async_sync_job():
    await asyncio.to_thread(_sync_job)


def _stats_job():
    from utils.stats_logger import capture_member_stats
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n?? [{ts}] Capturing member statistics...")
    capture_member_stats()


async def _async_stats_job():
    await asyncio.to_thread(_stats_job)


# -- Lifespan (replaces Flask before_first_request / teardown) -----------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db()
    print("\n? Database tables verified.\n")

    if settings.ROBLOX_SYNC_ENABLED:
        print(f"{'='*60}")
        print(f"?? Roblox Sync: ENABLED (every {settings.ROBLOX_SYNC_INTERVAL}s)")
        print(f"{'='*60}")

    if settings.ROBLOX_BACKGROUND_SYNC_ENABLED:
        scheduler.add_job(
            _async_sync_job, "interval",
            seconds=settings.ROBLOX_SYNC_INTERVAL,
            id="roblox_sync_job", replace_existing=True,
        )
        scheduler.add_job(
            _async_stats_job, "cron",
            hour=0, minute=0,
            id="member_stats_job", replace_existing=True,
        )
        scheduler.start()
        print("? Background scheduler started.")
        # Initial sync 5 s after startup
        await asyncio.sleep(5)
        asyncio.create_task(_async_sync_job())
    elif settings.ROBLOX_SYNC_ENABLED:
        print("??  Background sync disabled - set ROBLOX_BACKGROUND_SYNC_ENABLED=true to enable.")
    else:
        print("??  Roblox auto-sync is DISABLED.")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("?? Scheduler stopped.")


# -- App ------------------------------------------------------------------------

app = FastAPI(
    title="Taskforce Management System",
    version="2.0.0",
    lifespan=lifespan,
    # Disable auto-generated API docs in production if desired:
    # docs_url=None, redoc_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=43200,  # 12 hours
    https_only=False,  # set True in production
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# -- Global error handler -------------------------------------------------------



# -- Register routers -----------------------------------------------------------

from routers.auth import router as auth_router
from routers.public import router as public_router
from routers.members import router as members_router
from routers.ac import router as ac_router
from routers.sync import router as sync_router
from routers.missions import router as missions_router
from api.discord_bot_api import router as bot_api_router

app.include_router(auth_router)
app.include_router(public_router)
app.include_router(members_router)
app.include_router(ac_router, prefix="/ac")
app.include_router(sync_router)
app.include_router(missions_router, prefix="/api/v1/missions")
app.include_router(bot_api_router, prefix="/api/v1")
