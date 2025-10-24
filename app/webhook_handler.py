"""Webhook handler with retry logic and exponential backoff."""
import asyncio
import httpx
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database import (
    add_to_webhook_queue,
    get_pending_webhooks,
    update_webhook_status,
    get_item_by_id
)
from config import settings

logger = logging.getLogger(__name__)


async def queue_webhook(item_id: int, triaged_by: str) -> int:
    """Queue a webhook for an item."""
    # Get item details
    item = await get_item_by_id(item_id)
    if not item:
        raise ValueError(f"Item {item_id} not found")

    # Build Discord-formatted payload
    summary_text = item['summary'][:500] + "..." if len(item['summary']) > 500 else item['summary']

    payload = {
        "embeds": [{
            "title": item['title'],
            "url": item['url'],
            "description": summary_text,
            "color": 15158332,  # Red color for alerts
            "fields": [
                {
                    "name": "Source",
                    "value": item['feed_name'],
                    "inline": True
                },
                {
                    "name": "Triaged By",
                    "value": triaged_by,
                    "inline": True
                }
            ],
            "footer": {
                "text": "Kairos Threat Intelligence"
            },
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    # Add to queue
    webhook_id = await add_to_webhook_queue(item_id, payload)
    logger.info(f"Queued webhook {webhook_id} for item {item_id}")

    return webhook_id


async def send_webhook(webhook_id: int, payload: Dict[str, Any], attempts: int) -> bool:
    """Send a webhook with exponential backoff retry."""
    if not settings.WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured, skipping webhook")
        await update_webhook_status(webhook_id, 'skipped', 'WEBHOOK_URL not configured')
        return False

    # Calculate backoff delay (exponential: 1s, 2s, 4s, etc.)
    if attempts > 0:
        delay = 2 ** (attempts - 1)
        logger.info(f"Retry attempt {attempts}, waiting {delay}s")
        await asyncio.sleep(delay)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.WEBHOOK_URL,
                json=payload,
                timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

        logger.info(f"Webhook {webhook_id} sent successfully (attempt {attempts + 1})")
        await update_webhook_status(webhook_id, 'sent', None)
        return True

    except httpx.TimeoutException:
        error_msg = f"Timeout after {settings.WEBHOOK_TIMEOUT_SECONDS}s"
        logger.error(f"Webhook {webhook_id} timeout (attempt {attempts + 1}): {error_msg}")
        await update_webhook_status(webhook_id, 'pending', error_msg)
        return False

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        logger.error(f"Webhook {webhook_id} HTTP error (attempt {attempts + 1}): {error_msg}")
        await update_webhook_status(webhook_id, 'pending', error_msg)
        return False

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(f"Webhook {webhook_id} error (attempt {attempts + 1}): {error_msg}")
        await update_webhook_status(webhook_id, 'pending', error_msg)
        return False


async def process_webhook_queue():
    """Process pending webhooks in the queue."""
    logger.info("Processing webhook queue")

    pending = await get_pending_webhooks(limit=20)

    if not pending:
        logger.debug("No pending webhooks")
        return {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'retry_pending': 0
        }

    successful = 0
    failed = 0
    retry_pending = 0

    for webhook in pending:
        webhook_id = webhook['id']
        payload = json.loads(webhook['payload'])
        attempts = webhook['attempts']

        # Send webhook
        success = await send_webhook(webhook_id, payload, attempts)

        if success:
            successful += 1
        else:
            # Check if we've exhausted retries
            if attempts + 1 >= settings.WEBHOOK_RETRY_COUNT:
                logger.error(f"Webhook {webhook_id} failed after {settings.WEBHOOK_RETRY_COUNT} attempts")
                await update_webhook_status(webhook_id, 'failed', 'Max retries exceeded')
                failed += 1
            else:
                retry_pending += 1

    logger.info(
        f"Webhook processing complete: {successful} sent, {failed} failed, {retry_pending} pending retry"
    )

    return {
        'processed': len(pending),
        'successful': successful,
        'failed': failed,
        'retry_pending': retry_pending
    }


async def process_webhooks_background():
    """Background task to continuously process webhook queue."""
    logger.info("Starting webhook background processor")

    while True:
        try:
            await process_webhook_queue()
        except Exception as e:
            logger.error(f"Error in webhook processor: {e}")

        # Wait before next iteration
        await asyncio.sleep(30)  # Process every 30 seconds
