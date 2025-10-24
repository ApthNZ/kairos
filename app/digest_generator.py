"""Daily digest generation and management."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from database import (
    get_digest_items,
    clear_digest_items,
    get_stats
)
from config import settings

logger = logging.getLogger(__name__)


def format_digest_markdown(items: list, stats: Dict[str, Any], date: datetime) -> str:
    """Format digest items as markdown."""
    date_str = date.strftime("%Y-%m-%d")

    markdown = f"""# Daily Security Digest - {date_str}

## Summary
- **Items Reviewed Today**: {stats.get('triaged_today', 0)}
- **Items in Digest**: {len(items)}
- **Pending Review**: {stats['by_status'].get('pending', 0)}
- **Total Feeds**: {stats.get('active_feeds', 0)}

---

"""

    if not items:
        markdown += "_No items were marked for digest today._\n"
        return markdown

    for item in items:
        title = item['title']
        url = item['url']
        feed_name = item['feed_name']
        published = item['published_date']
        summary = item['summary']

        # Parse published date
        try:
            if isinstance(published, str):
                pub_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                pub_str = pub_dt.strftime("%Y-%m-%d %H:%M UTC")
            else:
                pub_str = "Unknown date"
        except:
            pub_str = str(published) if published else "Unknown date"

        markdown += f"""### [{title}]({url})
**Source:** {feed_name} | **Published:** {pub_str}

{summary}

---

"""

    return markdown


async def generate_digest(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """Generate daily digest file."""
    logger.info("Generating daily digest")

    # Get current time in configured timezone
    now = datetime.now(timezone.utc)

    # Get items and stats
    items = await get_digest_items()
    stats = await get_stats()

    # Generate markdown
    markdown = format_digest_markdown(items, stats, now)

    # Determine output path
    if output_path is None:
        output_path = Path(settings.DIGEST_OUTPUT_PATH)

    output_path.mkdir(parents=True, exist_ok=True)

    date_str = now.strftime("%Y-%m-%d")
    file_path = output_path / f"{date_str}-digest.md"

    # Write file
    with open(file_path, 'w') as f:
        f.write(markdown)

    logger.info(f"Digest written to {file_path} ({len(items)} items)")

    # Clear digest items (mark as archived)
    if items:
        await clear_digest_items()
        logger.info(f"Cleared {len(items)} items from digest queue")

    return {
        'file_path': str(file_path),
        'items_count': len(items),
        'date': date_str,
        'stats': stats
    }


async def get_latest_digest() -> Optional[Path]:
    """Get path to the latest digest file."""
    digest_dir = Path(settings.DIGEST_OUTPUT_PATH)

    if not digest_dir.exists():
        return None

    # Find all digest files
    digest_files = sorted(digest_dir.glob("*-digest.md"), reverse=True)

    return digest_files[0] if digest_files else None
