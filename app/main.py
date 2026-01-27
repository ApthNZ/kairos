"""Main FastAPI application for RSS Triage System."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends, Header, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, HttpUrl, EmailStr, Field
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


# Security Middleware: Add security headers to all responses
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# Rate Limiting Middleware
RATE_LIMIT_REQUESTS = 100  # requests per minute
rate_limit_store: Dict[str, list] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean up old entries (older than 60 seconds)
        rate_limit_store[client_ip] = [
            t for t in rate_limit_store[client_ip]
            if current_time - t < 60
        ]

        # Check rate limit
        if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "60"}
            )

        # Record this request
        rate_limit_store[client_ip].append(current_time)

        response = await call_next(request)

        # Add rate limit headers
        remaining = RATE_LIMIT_REQUESTS - len(rate_limit_store[client_ip])
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        return response


# Pydantic models
class FeedCreate(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    priority: int = 5
    category: str = 'RSS'


class TriageAction(BaseModel):
    action: str  # 'alert', 'digest', or 'skip'


class HealthResponse(BaseModel):
    status: str
    version: str
    database: bool
    pending_items: int


# Auth models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: Dict[str, Any]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(default='analyst', pattern='^(analyst|admin)$')
    force_password_reset: bool = Field(default=False)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern='^(analyst|admin)$')
    active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


# Global scheduler
scheduler = AsyncIOScheduler()


# Authentication dependencies
async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Get current authenticated user from session token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Support both "Bearer <token>" and plain token
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    # Check for legacy single-token auth
    if settings.AUTH_TOKEN and token == settings.AUTH_TOKEN:
        # Return a pseudo-user for legacy auth compatibility
        return {
            'id': 0,
            'username': settings.USER_IDENTIFIER,
            'role': 'admin',
            'active': 1
        }

    # Session-based auth
    session = await database.get_session_by_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if session['expires_at'] < datetime.utcnow():
        await database.delete_session(token)
        raise HTTPException(status_code=401, detail="Session expired")

    user = await database.get_user_by_id(session['user_id'])
    if not user or not user['active']:
        raise HTTPException(status_code=401, detail="User inactive or not found")

    return user


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin role for access."""
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# Legacy auth compatibility
async def verify_auth(authorization: Optional[str] = Header(None)):
    """Verify authentication - legacy wrapper."""
    await get_current_user(authorization)
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

    # Schedule session cleanup (hourly)
    session_trigger = IntervalTrigger(hours=1)
    scheduler.add_job(
        database.cleanup_expired_sessions,
        trigger=session_trigger,
        id='session_cleanup',
        name='Cleanup Expired Sessions',
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


# Create FastAPI app (disable OpenAPI docs in production)
app = FastAPI(
    title="RSS Triage System",
    description="RSS feed aggregation and triage system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)


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


# Authentication endpoints
@app.post("/api/auth/login")
async def login(request: Request, credentials: LoginRequest):
    """Authenticate user and create session."""
    user = await database.authenticate_user(credentials.username, credentials.password)

    if not user:
        # Generic error to prevent user enumeration
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    token = await database.create_session(
        user['id'],
        settings.SESSION_EXPIRY_HOURS,
        ip_address,
        user_agent
    )

    # Update last login
    await database.update_user_last_login(user['id'])

    # Log login action
    await database.log_action(user['id'], 'login', details={'ip': ip_address})

    # Return token and user info (without password hash)
    return {
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "force_password_reset": bool(user.get('force_password_reset', 0))
        }
    }


@app.post("/api/auth/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Logout and invalidate session."""
    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        await database.delete_session(token)

    # Log logout action
    if user['id'] != 0:  # Don't log for legacy auth
        await database.log_action(user['id'], 'logout')

    return {"message": "Logged out successfully"}


@app.get("/api/auth/me")
async def get_current_user_info(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current authenticated user info."""
    if user['id'] == 0:
        # Legacy auth user
        return {
            "id": 0,
            "username": user['username'],
            "role": user['role'],
            "legacy_auth": True
        }

    # Full user from database
    full_user = await database.get_user_by_id(user['id'])
    return {
        "id": full_user['id'],
        "username": full_user['username'],
        "email": full_user['email'],
        "role": full_user['role'],
        "created_at": full_user['created_at'],
        "last_login": full_user['last_login'],
        "force_password_reset": bool(full_user.get('force_password_reset', 0))
    }


@app.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Change current user's password."""
    if user['id'] == 0:
        raise HTTPException(status_code=400, detail="Cannot change password for legacy auth")

    # Verify current password
    db_user = await database.get_user_by_id(user['id'])
    if not database.verify_password(request.current_password, db_user['password_hash']):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Update password
    await database.update_user_password(user['id'], request.new_password)

    # Clear force_password_reset flag if set
    await database.clear_force_password_reset(user['id'])

    # Log password change
    await database.log_action(user['id'], 'password_change')

    return {"message": "Password changed successfully"}


# Admin user management endpoints
@app.get("/api/admin/users")
async def list_users(admin: Dict[str, Any] = Depends(require_admin)):
    """List all users (admin only)."""
    users = await database.get_all_users()
    return {"users": users}


@app.post("/api/admin/users")
async def create_user(
    user_data: UserCreate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Create a new user (admin only)."""
    # Check for existing username/email
    existing = await database.get_user_by_username(user_data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    try:
        user_id = await database.create_user(
            user_data.username,
            user_data.email,
            user_data.password,
            user_data.role,
            user_data.force_password_reset
        )

        # Log admin action
        await database.log_action(
            admin['id'],
            'user_created',
            details={
                'created_user_id': user_id,
                'username': user_data.username,
                'force_password_reset': user_data.force_password_reset
            }
        )

        return {"id": user_id, "message": "User created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/users/{user_id}")
async def update_user_admin(
    user_id: int,
    user_data: UserUpdate,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Update a user (admin only)."""
    # Don't allow modifying legacy auth user
    if user_id == 0:
        raise HTTPException(status_code=400, detail="Cannot modify legacy auth user")

    # Check user exists
    existing = await database.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user
    await database.update_user(
        user_id,
        username=user_data.username,
        email=user_data.email,
        role=user_data.role,
        active=user_data.active
    )

    # If deactivating, invalidate their sessions
    if user_data.active is False:
        await database.delete_user_sessions(user_id)

    # Log admin action
    await database.log_action(
        admin['id'],
        'user_updated',
        details={'updated_user_id': user_id, 'changes': user_data.model_dump(exclude_unset=True)}
    )

    return {"message": "User updated successfully"}


@app.delete("/api/admin/users/{user_id}")
async def deactivate_user(
    user_id: int,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Deactivate a user (soft delete, admin only)."""
    if user_id == 0:
        raise HTTPException(status_code=400, detail="Cannot deactivate legacy auth user")

    # Don't allow self-deactivation
    if user_id == admin['id']:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    existing = await database.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    await database.update_user(user_id, active=False)
    await database.delete_user_sessions(user_id)

    # Log admin action
    await database.log_action(
        admin['id'],
        'user_deactivated',
        details={'deactivated_user_id': user_id, 'username': existing['username']}
    )

    return {"message": "User deactivated successfully"}


@app.post("/api/admin/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: ResetPasswordRequest,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Reset a user's password (admin only)."""
    if user_id == 0:
        raise HTTPException(status_code=400, detail="Cannot reset password for legacy auth user")

    existing = await database.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    await database.update_user_password(user_id, request.new_password)

    # Invalidate existing sessions so they need to re-login
    await database.delete_user_sessions(user_id)

    # Log admin action
    await database.log_action(
        admin['id'],
        'password_reset',
        details={'reset_user_id': user_id, 'username': existing['username']}
    )

    return {"message": "Password reset successfully"}


# Admin dashboard endpoints
@app.get("/api/admin/stats")
async def get_admin_stats(
    days: int = 30,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Get user contribution statistics (admin only)."""
    user_stats = await database.get_all_user_stats(days)

    # Calculate totals
    totals = {
        'alerted': sum(u['stats']['alerted'] for u in user_stats),
        'digested': sum(u['stats']['digested'] for u in user_stats),
        'skipped': sum(u['stats']['skipped'] for u in user_stats),
        'total': sum(u['stats']['total'] for u in user_stats)
    }

    return {
        "period_days": days,
        "users": user_stats,
        "totals": totals
    }


@app.get("/api/admin/stats/daily")
async def get_daily_stats(
    days: int = 30,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Get daily triage statistics (admin only)."""
    stats = await database.get_daily_stats(days)
    return {"period_days": days, "daily": stats}


@app.get("/api/admin/audit")
async def get_audit_log(
    limit: int = 100,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Get recent audit log entries (admin only)."""
    logs = await database.get_recent_audit_logs(limit)
    return {"logs": logs}


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
        feed_id = await database.add_feed(str(feed.url), feed.name, feed.priority, feed.category)
        return {"id": feed_id, "message": "Feed added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/feeds/{feed_id}")
async def update_feed(feed_id: int, feed: FeedCreate, auth: bool = Depends(verify_auth)):
    """Update a feed."""
    try:
        await database.update_feed(feed_id, feed.name, feed.priority, feed.category)
        return {"message": "Feed updated successfully"}
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


@app.get("/api/items/next/{panel}")
async def get_next_item_for_panel(panel: str, auth: bool = Depends(verify_auth)):
    """Get next item for a specific panel (priority1, standard, social)."""
    if panel not in ['priority1', 'standard', 'social']:
        raise HTTPException(status_code=400, detail="Invalid panel name")

    item = await database.get_next_item_for_panel(panel)

    if not item:
        return {"item": None, "remaining": 0}

    remaining = await database.get_pending_count_for_panel(panel)

    return {
        "item": item,
        "remaining": remaining
    }


@app.post("/api/items/{item_id}/triage")
async def triage_item(
    item_id: int,
    action: TriageAction,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Triage an item."""
    # Validate action
    if action.action not in ['alert', 'digest', 'skip']:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Get item to verify it exists
    item = await database.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get username for attribution
    username = user['username']

    # Process based on action
    if action.action == 'alert':
        # Update status and queue webhook
        await database.update_item_status(item_id, 'alerted', username)
        webhook_id = await queue_webhook(item_id, username)

        # Log audit action
        if user['id'] != 0:
            await database.log_action(user['id'], 'triage_alert', item_id)

        return {
            "message": "Item marked for immediate alert",
            "webhook_id": webhook_id,
            "triaged_by": username
        }

    elif action.action == 'digest':
        # Update status (will be included in next digest)
        await database.update_item_status(item_id, 'digested', username)

        # Log audit action
        if user['id'] != 0:
            await database.log_action(user['id'], 'triage_digest', item_id)

        return {"message": "Item added to daily digest", "triaged_by": username}

    elif action.action == 'skip':
        # Update status
        await database.update_item_status(item_id, 'skipped', username)

        # Log audit action
        if user['id'] != 0:
            await database.log_action(user['id'], 'triage_skip', item_id)

        return {"message": "Item skipped", "triaged_by": username}


@app.post("/api/items/{item_id}/undo")
async def undo_triage(
    item_id: int,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Undo a triage action by setting item back to pending."""
    # Get item to verify it exists
    item = await database.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check if item can be undone (not already pending)
    if item['status'] == 'pending':
        raise HTTPException(status_code=400, detail="Item is already pending")

    # Store previous status for audit
    previous_status = item['status']

    # Set back to pending
    await database.update_item_status(item_id, 'pending', None)

    # Log audit action
    if user['id'] != 0:
        await database.log_action(
            user['id'],
            'undo',
            item_id,
            details={'previous_status': previous_status}
        )

    return {"message": "Item restored to pending"}


@app.post("/api/items/skip-all")
async def skip_all_items(user: Dict[str, Any] = Depends(get_current_user)):
    """Skip all pending items."""
    username = user['username']
    count = await database.skip_all_pending(username)

    # Log audit action for bulk skip
    if user['id'] != 0:
        await database.log_action(
            user['id'],
            'skip_all',
            details={'count': count}
        )

    return {
        "message": f"Skipped {count} items",
        "count": count,
        "skipped_by": username
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
