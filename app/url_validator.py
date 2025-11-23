"""URL validation to prevent SSRF and other injection attacks."""
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class URLValidationError(Exception):
    """Raised when URL validation fails."""
    pass


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        ip = ipaddress.ip_address(ip_str)

        # Check for private, loopback, link-local, and other reserved ranges
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_multicast or
            ip.is_reserved or
            ip.is_unspecified
        )
    except ValueError:
        # Not a valid IP address
        return False


def validate_url(url: str, purpose: str = "feed") -> str:
    """
    Validate a URL for SSRF protection.

    Args:
        url: The URL to validate
        purpose: Purpose of the URL ('feed' or 'webhook')

    Returns:
        The validated URL (normalized)

    Raises:
        URLValidationError: If the URL is invalid or unsafe
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")

    url = url.strip()

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}")

    # Check scheme - only allow http/https
    if parsed.scheme not in ('http', 'https'):
        raise URLValidationError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http:// and https:// are allowed"
        )

    # Check that hostname exists
    if not parsed.netloc:
        raise URLValidationError("URL must have a hostname")

    # Extract hostname (without port)
    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must have a valid hostname")

    # Check for localhost aliases
    localhost_names = {
        'localhost', '127.0.0.1', '::1', '0.0.0.0',
        '127.0.0.0', '0', 'localhost.localdomain'
    }
    if hostname.lower() in localhost_names:
        raise URLValidationError(
            f"Access to localhost is not allowed for {purpose} URLs"
        )

    # Resolve hostname to IP and check for private ranges
    try:
        # Get all IP addresses for this hostname
        addr_info = socket.getaddrinfo(hostname, None)

        for info in addr_info:
            ip_str = info[4][0]

            # Check if this resolves to a private/reserved IP
            if is_private_ip(ip_str):
                raise URLValidationError(
                    f"URL resolves to private/reserved IP address ({ip_str}). "
                    f"Access to internal networks is not allowed for {purpose} URLs"
                )

    except socket.gaierror as e:
        raise URLValidationError(f"Cannot resolve hostname '{hostname}': {e}")
    except URLValidationError:
        # Re-raise our validation errors
        raise
    except Exception as e:
        logger.warning(f"Error during IP validation for {hostname}: {e}")
        # Continue - don't block on DNS resolution issues

    # Additional webhook-specific validation
    if purpose == "webhook":
        # Ensure webhook URLs are HTTPS in production (allow HTTP for testing)
        if parsed.scheme == 'http':
            logger.warning(
                f"Webhook URL uses insecure HTTP protocol. "
                f"HTTPS is recommended for production use."
            )

    return url


def validate_webhook_url_on_startup(webhook_url: Optional[str]) -> bool:
    """
    Validate webhook URL during application startup.

    Returns:
        True if valid or None, False if invalid
    """
    if not webhook_url:
        logger.info("No webhook URL configured")
        return True

    try:
        validate_url(webhook_url, purpose="webhook")
        logger.info(f"Webhook URL validated: {webhook_url}")
        return True
    except URLValidationError as e:
        logger.error(f"Invalid webhook URL: {e}")
        logger.error("Application will continue but webhooks will be disabled")
        return False


def validate_feed_url(feed_url: str) -> str:
    """
    Validate a feed URL before fetching.

    Returns:
        The validated URL

    Raises:
        URLValidationError: If the URL is invalid or unsafe
    """
    return validate_url(feed_url, purpose="feed")
