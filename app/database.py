"""Database models and initialization for RSS Triage System."""
import aiosqlite
import bcrypt
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

DATABASE_PATH = Path("/app/data/triage.db")


async def init_db():
    """Initialize database with schema."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Feeds table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                last_fetched DATETIME,
                last_error TEXT,
                active BOOLEAN DEFAULT 1,
                priority INTEGER DEFAULT 5,
                category TEXT DEFAULT 'RSS',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: Add category column if it doesn't exist
        try:
            await db.execute("ALTER TABLE feeds ADD COLUMN category TEXT DEFAULT 'RSS'")
            await db.commit()
        except aiosqlite.OperationalError:
            # Column already exists
            pass

        # Items table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER NOT NULL,
                guid TEXT UNIQUE NOT NULL,
                title TEXT,
                url TEXT,
                summary TEXT,
                published_date DATETIME,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                triaged_at DATETIME,
                triaged_by TEXT,
                FOREIGN KEY (feed_id) REFERENCES feeds(id) ON DELETE CASCADE
            )
        """)

        # Webhook queue table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS webhook_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                last_attempt DATETIME,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            )
        """)

        # Users table for multi-user support
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'analyst',
                active INTEGER DEFAULT 1,
                force_password_reset INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        """)

        # Migration: Add force_password_reset column if it doesn't exist
        try:
            await db.execute("ALTER TABLE users ADD COLUMN force_password_reset INTEGER DEFAULT 0")
            await db.commit()
        except aiosqlite.OperationalError:
            # Column already exists
            pass

        # Sessions table for server-side session management
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Audit log for tracking all user actions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        """)

        # Create indexes for performance
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_status
            ON items(status, published_date DESC)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_feed_status
            ON items(feed_id, status)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_webhook_status
            ON webhook_queue(status, created_at)
        """)

        # Indexes for multi-user tables
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_triaged_by
            ON items(triaged_by)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token
            ON sessions(token)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_expires
            ON sessions(expires_at)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_log(user_id, timestamp DESC)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action
            ON audit_log(action, timestamp DESC)
        """)

        await db.commit()


async def get_db():
    """Get database connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


# Feed management functions
async def add_feed(url: str, name: Optional[str] = None, priority: int = 5, category: str = 'RSS') -> int:
    """Add a new RSS feed."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO feeds (url, name, priority, category) VALUES (?, ?, ?, ?)",
            (url, name, priority, category)
        )
        await db.commit()
        return cursor.lastrowid


async def get_feeds(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all feeds."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM feeds"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY priority DESC, name ASC"

        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_feed_status(feed_id: int, last_fetched: datetime, error: Optional[str] = None):
    """Update feed fetch status."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE feeds SET last_fetched = ?, last_error = ? WHERE id = ?",
            (last_fetched.isoformat(), error, feed_id)
        )
        await db.commit()


async def update_feed(feed_id: int, name: Optional[str] = None, priority: Optional[int] = None, category: Optional[str] = None):
    """Update feed properties."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Build update query dynamically based on what's being updated
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if not updates:
            return  # Nothing to update

        params.append(feed_id)
        query = f"UPDATE feeds SET {', '.join(updates)} WHERE id = ?"

        await db.execute(query, params)
        await db.commit()


async def delete_feed(feed_id: int):
    """Delete a feed and its items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        await db.commit()


# Item management functions
async def add_item(
    feed_id: int,
    guid: str,
    title: str,
    url: str,
    summary: str,
    published_date: Optional[datetime] = None
) -> Optional[int]:
    """Add a new item. Returns item_id or None if duplicate."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                """INSERT INTO items
                (feed_id, guid, title, url, summary, published_date)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (feed_id, guid, title, url, summary,
                 published_date.isoformat() if published_date else None)
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            # Duplicate GUID
            return None


async def get_next_item() -> Optional[Dict[str, Any]]:
    """Get next pending item for review, ordered by priority and date."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT i.*, f.name as feed_name, f.priority as feed_priority, f.category as feed_category
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE i.status = 'pending'
            ORDER BY f.priority ASC, i.published_date DESC
            LIMIT 1"""
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_next_item_for_panel(panel: str) -> Optional[Dict[str, Any]]:
    """Get next pending item for a specific panel.

    Panels:
    - 'priority1': Priority 1 RSS feeds only
    - 'standard': Priority 2-5, RSS category
    - 'social': Social category (all priorities)
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Use parameterized queries to prevent SQL injection
        if panel == 'priority1':
            query = """SELECT i.*, f.name as feed_name, f.priority as feed_priority, f.category as feed_category
                FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.priority = ? AND f.category = ?
                ORDER BY f.priority ASC, i.published_date DESC
                LIMIT 1"""
            params = ('pending', 1, 'RSS')
        elif panel == 'standard':
            query = """SELECT i.*, f.name as feed_name, f.priority as feed_priority, f.category as feed_category
                FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.priority > ? AND f.category = ?
                ORDER BY f.priority ASC, i.published_date DESC
                LIMIT 1"""
            params = ('pending', 1, 'RSS')
        elif panel == 'social':
            query = """SELECT i.*, f.name as feed_name, f.priority as feed_priority, f.category as feed_category
                FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.category = ?
                ORDER BY f.priority ASC, i.published_date DESC
                LIMIT 1"""
            params = ('pending', 'Social')
        else:
            return None

        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_pending_count_for_panel(panel: str) -> int:
    """Get count of pending items for a specific panel."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Use parameterized queries to prevent SQL injection
        if panel == 'priority1':
            query = """SELECT COUNT(*) FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.priority = ? AND f.category = ?"""
            params = ('pending', 1, 'RSS')
        elif panel == 'standard':
            query = """SELECT COUNT(*) FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.priority > ? AND f.category = ?"""
            params = ('pending', 1, 'RSS')
        elif panel == 'social':
            query = """SELECT COUNT(*) FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.status = ? AND f.category = ?"""
            params = ('pending', 'Social')
        else:
            return 0

        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def get_item_by_id(item_id: int) -> Optional[Dict[str, Any]]:
    """Get item by ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT i.*, f.name as feed_name
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE i.id = ?""",
            (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_item_status(
    item_id: int,
    status: str,
    triaged_by: Optional[str] = None
):
    """Update item status after triage."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """UPDATE items
            SET status = ?, triaged_at = ?, triaged_by = ?
            WHERE id = ?""",
            (status, datetime.utcnow().isoformat(), triaged_by, item_id)
        )
        await db.commit()


async def get_pending_count() -> int:
    """Get count of pending items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def skip_all_pending(user_identifier: str) -> int:
    """Skip all pending items. Returns count of items skipped."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # First get the count
        async with db.execute(
            "SELECT COUNT(*) FROM items WHERE status = 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            count = row[0]

        # Update all pending items to skipped
        await db.execute(
            """UPDATE items
            SET status = 'skipped',
                triaged_at = ?,
                triaged_by = ?
            WHERE status = 'pending'""",
            (datetime.utcnow().isoformat(), user_identifier)
        )
        await db.commit()
        return count


async def get_stats() -> Dict[str, Any]:
    """Get statistics about items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        stats = {}

        # Count by status
        async with db.execute(
            """SELECT status, COUNT(*) as count
            FROM items
            GROUP BY status"""
        ) as cursor:
            stats['by_status'] = {row['status']: row['count']
                                 for row in await cursor.fetchall()}

        # Total feeds
        async with db.execute("SELECT COUNT(*) FROM feeds WHERE active = 1") as cursor:
            row = await cursor.fetchone()
            stats['active_feeds'] = row[0]

        # Items triaged today
        async with db.execute(
            """SELECT COUNT(*) FROM items
            WHERE DATE(triaged_at) = DATE('now')"""
        ) as cursor:
            row = await cursor.fetchone()
            stats['triaged_today'] = row[0]

        return stats


# Webhook queue functions
async def add_to_webhook_queue(item_id: int, payload: Dict[str, Any]) -> int:
    """Add item to webhook queue."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO webhook_queue (item_id, payload) VALUES (?, ?)",
            (item_id, json.dumps(payload))
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_webhooks(limit: int = 10) -> List[Dict[str, Any]]:
    """Get pending webhooks to send."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM webhook_queue
            WHERE status = 'pending' AND attempts < 3
            ORDER BY created_at ASC
            LIMIT ?""",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_webhook_status(
    webhook_id: int,
    status: str,
    error_message: Optional[str] = None
):
    """Update webhook delivery status."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """UPDATE webhook_queue
            SET status = ?, attempts = attempts + 1,
                last_attempt = ?, error_message = ?
            WHERE id = ?""",
            (status, datetime.utcnow().isoformat(), error_message, webhook_id)
        )
        await db.commit()


# Digest functions
async def get_digest_items() -> List[Dict[str, Any]]:
    """Get items marked for digest."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT i.*, f.name as feed_name
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE i.status = 'digested'
            ORDER BY i.published_date DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def clear_digest_items():
    """Clear items from digest after generation."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE items SET status = 'archived' WHERE status = 'digested'"
        )
        await db.commit()


# Password hashing functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# User management functions
async def create_user(
    username: str,
    email: str,
    password: str,
    role: str = 'analyst',
    force_password_reset: bool = False
) -> int:
    """Create a new user. Returns user_id."""
    password_hash = hash_password(password)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO users (username, email, password_hash, role, force_password_reset)
            VALUES (?, ?, ?, ?, ?)""",
            (username, email, password_hash, role, 1 if force_password_reset else 0)
        )
        await db.commit()
        return cursor.lastrowid


async def clear_force_password_reset(user_id: int):
    """Clear the force_password_reset flag after user changes password."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET force_password_reset = 0 WHERE id = ?",
            (user_id,)
        )
        await db.commit()


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_users() -> List[Dict[str, Any]]:
    """Get all users."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, username, email, role, active, created_at, last_login FROM users ORDER BY username"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_user(
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    active: Optional[bool] = None
) -> bool:
    """Update user properties. Returns True if user was found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        updates = []
        params = []

        if username is not None:
            updates.append("username = ?")
            params.append(username)
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if active is not None:
            updates.append("active = ?")
            params.append(1 if active else 0)

        if not updates:
            return False

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount > 0


async def update_user_password(user_id: int, new_password: str) -> bool:
    """Update user password. Returns True if successful."""
    password_hash = hash_password(new_password)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_user_last_login(user_id: int):
    """Update user's last login timestamp."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user_id)
        )
        await db.commit()


async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user by username and password. Returns user dict if valid."""
    user = await get_user_by_username(username)
    if not user:
        return None
    if not user['active']:
        return None
    if not verify_password(password, user['password_hash']):
        return None
    return user


# Session management functions
async def create_session(
    user_id: int,
    expiry_hours: int = 24,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """Create a new session. Returns session token."""
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)""",
            (user_id, token, expires_at.isoformat(), ip_address, user_agent)
        )
        await db.commit()
    return token


async def get_session_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Get session by token."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE token = ?", (token,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            session = dict(row)
            # Convert expires_at string to datetime for comparison
            session['expires_at'] = datetime.fromisoformat(session['expires_at'])
            return session


async def delete_session(token: str):
    """Delete a session (logout)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()


async def delete_user_sessions(user_id: int):
    """Delete all sessions for a user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await db.commit()


async def cleanup_expired_sessions():
    """Remove expired sessions."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.utcnow().isoformat(),)
        )
        await db.commit()


# Audit log functions
async def log_action(
    user_id: int,
    action: str,
    item_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log an audit action."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO audit_log (user_id, item_id, action, details)
            VALUES (?, ?, ?, ?)""",
            (user_id, item_id, action, json.dumps(details) if details else None)
        )
        await db.commit()


async def get_recent_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent audit log entries."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT a.*, u.username
            FROM audit_log a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT ?""",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_user_audit_logs(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Get audit logs for a specific user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM audit_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?""",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_user_stats(user_id: int, days: int = 30) -> Dict[str, Any]:
    """Get triage statistics for a user over the specified period."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT action, COUNT(*) as count
            FROM audit_log
            WHERE user_id = ? AND timestamp >= ?
            AND action IN ('triage_alert', 'triage_digest', 'triage_skip')
            GROUP BY action""",
            (user_id, cutoff)
        ) as cursor:
            rows = await cursor.fetchall()
            stats = {row['action']: row['count'] for row in rows}

        return {
            'alerted': stats.get('triage_alert', 0),
            'digested': stats.get('triage_digest', 0),
            'skipped': stats.get('triage_skip', 0),
            'total': sum(stats.values())
        }


async def get_all_user_stats(days: int = 30) -> List[Dict[str, Any]]:
    """Get triage statistics for all users (admin dashboard)."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get all users with their stats
        async with db.execute(
            """SELECT u.id, u.username, u.last_login,
                SUM(CASE WHEN a.action = 'triage_alert' THEN 1 ELSE 0 END) as alerted,
                SUM(CASE WHEN a.action = 'triage_digest' THEN 1 ELSE 0 END) as digested,
                SUM(CASE WHEN a.action = 'triage_skip' THEN 1 ELSE 0 END) as skipped
            FROM users u
            LEFT JOIN audit_log a ON u.id = a.user_id
                AND a.timestamp >= ?
                AND a.action IN ('triage_alert', 'triage_digest', 'triage_skip')
            WHERE u.active = 1
            GROUP BY u.id
            ORDER BY (COALESCE(alerted, 0) + COALESCE(digested, 0) + COALESCE(skipped, 0)) DESC""",
            (cutoff,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{
                'user_id': row['id'],
                'username': row['username'],
                'last_active': row['last_login'],
                'stats': {
                    'alerted': row['alerted'] or 0,
                    'digested': row['digested'] or 0,
                    'skipped': row['skipped'] or 0,
                    'total': (row['alerted'] or 0) + (row['digested'] or 0) + (row['skipped'] or 0)
                }
            } for row in rows]


async def get_daily_stats(days: int = 30) -> List[Dict[str, Any]]:
    """Get daily triage statistics for all users."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT DATE(timestamp) as date,
                u.username,
                SUM(CASE WHEN action = 'triage_alert' THEN 1 ELSE 0 END) as alerted,
                SUM(CASE WHEN action = 'triage_digest' THEN 1 ELSE 0 END) as digested,
                SUM(CASE WHEN action = 'triage_skip' THEN 1 ELSE 0 END) as skipped
            FROM audit_log a
            JOIN users u ON a.user_id = u.id
            WHERE timestamp >= ?
            AND action IN ('triage_alert', 'triage_digest', 'triage_skip')
            GROUP BY DATE(timestamp), u.id
            ORDER BY date DESC, username""",
            (cutoff,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
