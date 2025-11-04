"""RSS feed fetching with async parallel processing."""
import asyncio
import feedparser
import httpx
from datetime import datetime, timezone
from dateutil import parser as date_parser
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

from database import (
    get_feeds,
    add_item,
    update_feed_status,
    get_stats
)
from config import settings

logger = logging.getLogger(__name__)


def parse_published_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """Parse published date from feed entry."""
    # Try various date fields
    date_fields = ['published', 'updated', 'created']

    for field in date_fields:
        if field in entry:
            try:
                # feedparser provides parsed date tuples
                parsed_field = f"{field}_parsed"
                if parsed_field in entry and entry[parsed_field]:
                    # Convert time.struct_time to datetime
                    import time
                    dt = datetime(*entry[parsed_field][:6])
                    # Make timezone-aware (assume UTC if not specified)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                # Fallback to string parsing
                elif isinstance(entry[field], str):
                    dt = date_parser.parse(entry[field])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse date from {field}: {e}")
                continue

    # Return current time if no date found
    return datetime.now(timezone.utc)


def sanitize_html(text: str) -> str:
    """Remove HTML tags and sanitize text."""
    import bleach
    # Strip all HTML tags but preserve text
    clean_text = bleach.clean(text, tags=[], strip=True)
    # Normalize whitespace
    return ' '.join(clean_text.split())


async def fetch_single_feed(feed: Dict[str, Any], client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch a single RSS feed."""
    feed_id = feed['id']
    feed_url = feed['url']
    feed_name = feed['name'] or feed_url

    logger.info(f"Fetching feed: {feed_name}")

    try:
        # Fetch with timeout
        response = await client.get(
            feed_url,
            timeout=settings.FEED_TIMEOUT_SECONDS,
            follow_redirects=True
        )
        response.raise_for_status()

        # Parse feed
        parsed = feedparser.parse(response.content)

        if parsed.bozo and not parsed.entries:
            # Feed has errors and no entries
            error_msg = str(getattr(parsed, 'bozo_exception', 'Parse error'))
            logger.error(f"Feed parse error for {feed_name}: {error_msg}")
            await update_feed_status(feed_id, datetime.now(timezone.utc), error_msg)
            return {
                'feed_id': feed_id,
                'feed_name': feed_name,
                'items_added': 0,
                'error': error_msg
            }

        # Process entries
        items_added = 0
        items_processed = 0

        for entry in parsed.entries[:settings.MAX_ITEMS_PER_FEED]:
            items_processed += 1

            # Extract entry data
            guid = entry.get('id') or entry.get('link') or f"{feed_id}_{items_processed}"
            title = entry.get('title', 'Untitled')
            url = entry.get('link', '')

            # Get summary/description
            summary = entry.get('summary', entry.get('description', ''))
            if summary:
                summary = sanitize_html(summary)
                # Truncate very long summaries
                if len(summary) > 2000:
                    summary = summary[:1997] + "..."

            published_date = parse_published_date(entry)

            # Add to database (will skip if duplicate)
            item_id = await add_item(
                feed_id=feed_id,
                guid=guid,
                title=title,
                url=url,
                summary=summary,
                published_date=published_date
            )

            if item_id:
                items_added += 1
                logger.debug(f"Added item: {title[:50]}")

        # Update feed status
        await update_feed_status(feed_id, datetime.now(timezone.utc), None)

        logger.info(f"Feed {feed_name}: {items_added} new items (processed {items_processed})")

        return {
            'feed_id': feed_id,
            'feed_name': feed_name,
            'items_added': items_added,
            'items_processed': items_processed,
            'error': None
        }

    except httpx.TimeoutException:
        error_msg = f"Timeout after {settings.FEED_TIMEOUT_SECONDS}s"
        logger.error(f"Feed timeout for {feed_name}")
        await update_feed_status(feed_id, datetime.now(timezone.utc), error_msg)
        return {
            'feed_id': feed_id,
            'feed_name': feed_name,
            'items_added': 0,
            'error': error_msg
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error fetching {feed_name}: {error_msg}")
        await update_feed_status(feed_id, datetime.now(timezone.utc), error_msg)
        return {
            'feed_id': feed_id,
            'feed_name': feed_name,
            'items_added': 0,
            'error': error_msg
        }


async def fetch_all_feeds() -> Dict[str, Any]:
    """Fetch all active feeds in parallel."""
    logger.info("Starting feed fetch cycle")

    # Get active feeds
    feeds = await get_feeds(active_only=True)

    if not feeds:
        logger.warning("No active feeds to fetch")
        return {
            'total_feeds': 0,
            'total_items_added': 0,
            'successful': 0,
            'failed': 0,
            'results': []
        }

    # Create HTTP client with connection pooling
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=settings.FEED_PARALLEL_WORKERS),
        headers={'User-Agent': 'RSS-Triage-System/1.0'}
    ) as client:
        # Fetch feeds in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(settings.FEED_PARALLEL_WORKERS)

        async def fetch_with_semaphore(feed):
            async with semaphore:
                return await fetch_single_feed(feed, client)

        results = await asyncio.gather(
            *[fetch_with_semaphore(feed) for feed in feeds],
            return_exceptions=False
        )

    # Aggregate results
    total_items_added = sum(r['items_added'] for r in results)
    successful = sum(1 for r in results if r['error'] is None)
    failed = sum(1 for r in results if r['error'] is not None)

    logger.info(
        f"Feed fetch complete: {total_items_added} items from {successful}/{len(feeds)} feeds"
    )

    return {
        'total_feeds': len(feeds),
        'total_items_added': total_items_added,
        'successful': successful,
        'failed': failed,
        'results': results
    }


async def load_feeds_from_file(file_path: str):
    """Load initial feeds from a text file (one URL per line)."""
    from database import add_feed

    feeds_file = Path(file_path)
    if not feeds_file.exists():
        logger.warning(f"Feeds file not found: {file_path}")
        return

    logger.info(f"Loading feeds from {file_path}")

    with open(feeds_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse line (format: URL or URL|Name or URL|Name|Priority or URL|Name|Priority|Category)
            parts = line.split('|')
            url = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else None
            priority = int(parts[2].strip()) if len(parts) > 2 else 5
            category = parts[3].strip() if len(parts) > 3 else 'RSS'

            try:
                await add_feed(url, name, priority, category)
                logger.info(f"Added feed: {name or url}")
            except Exception as e:
                logger.error(f"Failed to add feed {url}: {e}")
