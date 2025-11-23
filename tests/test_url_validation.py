"""Test URL validation for SSRF protection."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from url_validator import validate_url, validate_feed_url, URLValidationError, is_private_ip


def test_valid_http_url():
    """Test that valid HTTP URLs are accepted."""
    url = validate_url("http://example.com/feed.xml", "feed")
    assert url == "http://example.com/feed.xml"


def test_valid_https_url():
    """Test that valid HTTPS URLs are accepted."""
    url = validate_url("https://example.com/feed.xml", "feed")
    assert url == "https://example.com/feed.xml"


def test_reject_localhost():
    """Test that localhost URLs are rejected."""
    with pytest.raises(URLValidationError, match="localhost"):
        validate_url("http://localhost:8080/feed", "feed")


def test_reject_127_0_0_1():
    """Test that 127.0.0.1 URLs are rejected."""
    with pytest.raises(URLValidationError, match="localhost"):
        validate_url("http://127.0.0.1:8080/feed", "feed")


def test_reject_private_ip_10():
    """Test that 10.x.x.x private IPs are rejected."""
    with pytest.raises(URLValidationError, match="private/reserved IP"):
        validate_url("http://10.0.0.1/feed", "feed")


def test_reject_private_ip_192():
    """Test that 192.168.x.x private IPs are rejected."""
    with pytest.raises(URLValidationError, match="private/reserved IP"):
        validate_url("http://192.168.1.1/feed", "feed")


def test_reject_private_ip_172():
    """Test that 172.16.x.x private IPs are rejected."""
    with pytest.raises(URLValidationError, match="private/reserved IP"):
        validate_url("http://172.16.0.1/feed", "feed")


def test_reject_link_local():
    """Test that link-local IPs are rejected."""
    with pytest.raises(URLValidationError, match="private/reserved IP"):
        validate_url("http://169.254.1.1/feed", "feed")


def test_reject_invalid_scheme_ftp():
    """Test that FTP URLs are rejected."""
    with pytest.raises(URLValidationError, match="scheme"):
        validate_url("ftp://example.com/file", "feed")


def test_reject_invalid_scheme_file():
    """Test that file:// URLs are rejected."""
    with pytest.raises(URLValidationError, match="scheme"):
        validate_url("file:///etc/passwd", "feed")


def test_reject_invalid_scheme_gopher():
    """Test that gopher URLs are rejected."""
    with pytest.raises(URLValidationError, match="scheme"):
        validate_url("gopher://example.com", "feed")


def test_reject_empty_url():
    """Test that empty URLs are rejected."""
    with pytest.raises(URLValidationError, match="non-empty string"):
        validate_url("", "feed")


def test_reject_none_url():
    """Test that None URLs are rejected."""
    with pytest.raises(URLValidationError, match="non-empty string"):
        validate_url(None, "feed")


def test_reject_no_hostname():
    """Test that URLs without hostname are rejected."""
    with pytest.raises(URLValidationError, match="hostname"):
        validate_url("http://", "feed")


def test_is_private_ip_detection():
    """Test private IP detection function."""
    # Private IPs
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("172.16.0.1") is True
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("169.254.1.1") is True

    # Public IPs
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False


def test_valid_webhook_url():
    """Test that valid webhook URLs are accepted."""
    url = validate_url("https://discord.com/api/webhooks/123/token", "webhook")
    assert "discord.com" in url


def test_feed_url_wrapper():
    """Test the feed URL validation wrapper."""
    url = validate_feed_url("https://example.com/rss")
    assert url == "https://example.com/rss"


def test_url_normalization():
    """Test that URLs are properly normalized."""
    url = validate_url("  https://example.com/feed  ", "feed")
    assert url == "https://example.com/feed"


if __name__ == "__main__":
    # Run tests
    print("Running URL validation tests...")
    pytest.main([__file__, "-v"])
