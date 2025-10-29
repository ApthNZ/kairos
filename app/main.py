"""Main FastAPI application for RSS Triage System."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import config
import database
from feed_fetcher import fetch_all_feeds, load_feeds_from_file
from webhook_handler import queue_webhook, process_webhooks_background
from digest_generator import generate_digest, get_latest_digest

settings = config.settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic models
class FeedCreate(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    priority: int = 0


class TriageAction(BaseModel):
    action: str  # 'alert', 'digest', or 'skip'


class HealthResponse(BaseModel):
    status: str
    version: str
    database: bool
    pending_items: int


# Global scheduler
scheduler = AsyncIOScheduler()


# Authentication dependency
async def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify authentication token if configured."""
    if settings.AUTH_TOKEN:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Support both "Bearer <token>" and plain token
        token = authorization
        if authorization.startswith("Bearer "):
            token = authorization[7:]

        if token != settings.AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

    return True


# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting RSS Triage System")

    # Initialize database
    await database.init_db()
    logger.info("Database initialized")

    # Load feeds from file if exists
    # Prefer feeds.txt (for local docker-compose with custom feeds)
    # Fall back to feeds-starter.txt (for Render/cloud deployments with defaults)
    full_feeds = Path("/app/feeds.txt")
    starter_feeds = Path("/app/feeds-starter.txt")

    if full_feeds.exists():
        logger.info("Loading feeds from feeds.txt")
        await load_feeds_from_file(str(full_feeds))
    elif starter_feeds.exists():
        logger.info("Loading feeds from feeds-starter.txt (default)")
        await load_feeds_from_file(str(starter_feeds))
    else:
        logger.warning("No feeds file found. Add feeds via API or create feeds.txt")

    # Start webhook background processor
    webhook_task = asyncio.create_task(process_webhooks_background())

    # Schedule feed fetching
    feed_trigger = IntervalTrigger(minutes=settings.FEED_REFRESH_MINUTES)
    scheduler.add_job(
        fetch_all_feeds,
        trigger=feed_trigger,
        id='feed_fetcher',
        name='Fetch RSS Feeds',
        replace_existing=True
    )

    # Schedule digest generation
    hour, minute = settings.DIGEST_GENERATION_TIME.split(':')
    digest_trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.TIMEZONE)
    scheduler.add_job(
        generate_digest,
        trigger=digest_trigger,
        id='digest_generator',
        name='Generate Daily Digest',
        replace_existing=True
    )

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started")

    # Initial feed fetch
    logger.info("Performing initial feed fetch")
    asyncio.create_task(fetch_all_feeds())

    yield

    # Shutdown
    logger.info("Shutting down RSS Triage System")
    scheduler.shutdown()
    webhook_task.cancel()


# Create FastAPI app
app = FastAPI(
    title="RSS Triage System",
    description="RSS feed aggregation and triage system",
    version="1.0.0",
    lifespan=lifespan
)


# Health endpoint (no auth required)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        pending = await database.get_pending_count()
        db_ok = True
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        db_ok = False
        pending = -1

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "database": db_ok,
        "pending_items": pending
    }


# Metrics endpoint (no auth required)
@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics."""
    stats = await database.get_stats()
    pending = await database.get_pending_count()

    return {
        "pending_items": pending,
        "stats": stats,
        "scheduler_running": scheduler.running,
        "next_feed_fetch": scheduler.get_job('feed_fetcher').next_run_time.isoformat()
        if scheduler.get_job('feed_fetcher') else None,
        "next_digest": scheduler.get_job('digest_generator').next_run_time.isoformat()
        if scheduler.get_job('digest_generator') else None
    }


# Feed management endpoints
@app.get("/api/feeds")
async def list_feeds(auth: bool = Depends(verify_auth)):
    """List all feeds."""
    feeds = await database.get_feeds(active_only=False)
    return {"feeds": feeds}


@app.post("/api/feeds")
async def add_feed(feed: FeedCreate, auth: bool = Depends(verify_auth)):
    """Add a new feed."""
    try:
        feed_id = await database.add_feed(str(feed.url), feed.name, feed.priority)
        return {"id": feed_id, "message": "Feed added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/feeds/{feed_id}")
async def remove_feed(feed_id: int, auth: bool = Depends(verify_auth)):
    """Remove a feed."""
    try:
        await database.delete_feed(feed_id)
        return {"message": "Feed deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/feeds/refresh")
async def refresh_feeds(auth: bool = Depends(verify_auth)):
    """Manually trigger feed fetch."""
    asyncio.create_task(fetch_all_feeds())
    return {"message": "Feed refresh started"}


# Triage endpoints
@app.get("/api/items/next")
async def get_next_item(auth: bool = Depends(verify_auth)):
    """Get next item for review."""
    item = await database.get_next_item()

    if not item:
        return {"item": None, "remaining": 0}

    remaining = await database.get_pending_count()

    return {
        "item": item,
        "remaining": remaining
    }


@app.post("/api/items/{item_id}/triage")
async def triage_item(item_id: int, action: TriageAction, auth: bool = Depends(verify_auth)):
    """Triage an item."""
    # Validate action
    if action.action not in ['alert', 'digest', 'skip']:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Get item to verify it exists
    item = await database.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Process based on action
    if action.action == 'alert':
        # Update status and queue webhook
        await database.update_item_status(item_id, 'alerted', settings.USER_IDENTIFIER)
        webhook_id = await queue_webhook(item_id, settings.USER_IDENTIFIER)
        return {
            "message": "Item marked for immediate alert",
            "webhook_id": webhook_id
        }

    elif action.action == 'digest':
        # Update status (will be included in next digest)
        await database.update_item_status(item_id, 'digested', settings.USER_IDENTIFIER)
        return {"message": "Item added to daily digest"}

    elif action.action == 'skip':
        # Update status
        await database.update_item_status(item_id, 'skipped', settings.USER_IDENTIFIER)
        return {"message": "Item skipped"}


@app.post("/api/items/{item_id}/undo")
async def undo_triage(item_id: int, auth: bool = Depends(verify_auth)):
    """Undo a triage action by setting item back to pending."""
    # Get item to verify it exists
    item = await database.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check if item can be undone (not already pending)
    if item['status'] == 'pending':
        raise HTTPException(status_code=400, detail="Item is already pending")

    # Set back to pending
    await database.update_item_status(item_id, 'pending', None)

    return {"message": "Item restored to pending"}


@app.post("/api/items/skip-all")
async def skip_all_items(auth: bool = Depends(verify_auth)):
    """Skip all pending items."""
    count = await database.skip_all_pending(settings.USER_IDENTIFIER)
    return {
        "message": f"Skipped {count} items",
        "count": count
    }


@app.get("/api/items/stats")
async def get_item_stats(auth: bool = Depends(verify_auth)):
    """Get item statistics."""
    stats = await database.get_stats()
    return stats


# Digest endpoints
@app.post("/api/digest/generate")
async def trigger_digest(auth: bool = Depends(verify_auth)):
    """Manually trigger digest generation."""
    result = await generate_digest()
    return result


@app.get("/api/digest/latest")
async def download_latest_digest(auth: bool = Depends(verify_auth)):
    """Download the latest digest file."""
    latest = await get_latest_digest()

    if not latest or not latest.exists():
        raise HTTPException(status_code=404, detail="No digest files found")

    return FileResponse(
        path=latest,
        filename=latest.name,
        media_type="text/markdown"
    )


# Mount static files for web interface
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
