"""Database models and initialization for RSS Triage System."""
import aiosqlite
import json
from datetime import datetime
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

        if panel == 'priority1':
            where_clause = "i.status = 'pending' AND f.priority = 1 AND f.category = 'RSS'"
        elif panel == 'standard':
            where_clause = "i.status = 'pending' AND f.priority > 1 AND f.category = 'RSS'"
        elif panel == 'social':
            where_clause = "i.status = 'pending' AND f.category = 'Social'"
        else:
            return None

        async with db.execute(
            f"""SELECT i.*, f.name as feed_name, f.priority as feed_priority, f.category as feed_category
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE {where_clause}
            ORDER BY f.priority ASC, i.published_date DESC
            LIMIT 1"""
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_pending_count_for_panel(panel: str) -> int:
    """Get count of pending items for a specific panel."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        if panel == 'priority1':
            where_clause = "i.status = 'pending' AND f.priority = 1 AND f.category = 'RSS'"
        elif panel == 'standard':
            where_clause = "i.status = 'pending' AND f.priority > 1 AND f.category = 'RSS'"
        elif panel == 'social':
            where_clause = "i.status = 'pending' AND f.category = 'Social'"
        else:
            return 0

        async with db.execute(
            f"""SELECT COUNT(*) FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE {where_clause}"""
        ) as cursor:
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
