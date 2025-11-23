"""Security tests for kairos application."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest


def test_env_file_ignored():
    """Test that .env file is in .gitignore."""
    gitignore_path = os.path.join(os.path.dirname(__file__), '..', '.gitignore')
    assert os.path.exists(gitignore_path), ".gitignore file must exist"

    with open(gitignore_path, 'r') as f:
        gitignore_content = f.read()

    assert '.env' in gitignore_content, ".env must be in .gitignore"


def test_env_example_exists():
    """Test that .env.example exists for documentation."""
    env_example_path = os.path.join(os.path.dirname(__file__), '..', '.env.example')
    assert os.path.exists(env_example_path), ".env.example must exist"


def test_env_example_no_secrets():
    """Test that .env.example doesn't contain real secrets."""
    env_example_path = os.path.join(os.path.dirname(__file__), '..', '.env.example')

    with open(env_example_path, 'r') as f:
        content = f.read()

    # Check for common secret patterns
    forbidden_patterns = [
        'xoxb-',  # Slack tokens
        'ghp_',   # GitHub tokens
        'sk_',    # Stripe keys
        'AIza',   # Google API keys
    ]

    for pattern in forbidden_patterns:
        assert pattern not in content, f"Found potential secret pattern '{pattern}' in .env.example"


def test_requirements_updated():
    """Test that requirements.txt has been updated from 2023 versions."""
    requirements_path = os.path.join(os.path.dirname(__file__), '..', 'requirements.txt')

    with open(requirements_path, 'r') as f:
        content = f.read()

    # Check that we're not using the old vulnerable versions
    old_versions = [
        'fastapi==0.104.1',
        'uvicorn==0.24.0',
        'httpx==0.25.1',
        'pydantic==2.5.0',
    ]

    for old_ver in old_versions:
        assert old_ver not in content, f"Old vulnerable version {old_ver} still in requirements.txt"


def test_url_validator_exists():
    """Test that URL validator module exists."""
    validator_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'url_validator.py')
    assert os.path.exists(validator_path), "url_validator.py must exist for SSRF protection"


def test_imports_url_validator():
    """Test that feed_fetcher imports url_validator."""
    feed_fetcher_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'feed_fetcher.py')

    with open(feed_fetcher_path, 'r') as f:
        content = f.read()

    assert 'from url_validator import' in content, "feed_fetcher.py must import url_validator"
    assert 'URLValidationError' in content, "feed_fetcher.py must use URLValidationError"


def test_webhook_handler_validates():
    """Test that webhook_handler validates URLs."""
    webhook_handler_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'webhook_handler.py')

    with open(webhook_handler_path, 'r') as f:
        content = f.read()

    assert 'from url_validator import' in content, "webhook_handler.py must import url_validator"
    assert 'validate_url' in content, "webhook_handler.py must validate webhook URLs"


def test_no_hardcoded_secrets():
    """Test that there are no hardcoded secrets in code."""
    app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')

    # Patterns that might indicate hardcoded secrets
    secret_patterns = [
        b'password = "',
        b"password = '",
        b'token = "',
        b"token = '",
        b'api_key = "',
        b"api_key = '",
        b'secret = "',
        b"secret = '",
    ]

    for root, dirs, files in os.walk(app_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'rb') as f:
                    content = f.read()

                for pattern in secret_patterns:
                    if pattern in content:
                        # Check if it's actually a hardcoded value (not None, empty, or variable)
                        lines_with_pattern = [line for line in content.split(b'\n') if pattern in line]
                        for line in lines_with_pattern:
                            # Skip if it's setting to None or empty string or variable
                            if b'= None' in line or b'= ""' in line or b"= ''" in line:
                                continue
                            if b'settings.' in line or b'os.getenv' in line or b'os.environ' in line:
                                continue

                            pytest.fail(f"Potential hardcoded secret in {filepath}: {line.decode('utf-8', errors='ignore')}")


def test_follow_redirects_disabled():
    """Test that follow_redirects is disabled in feed fetching."""
    feed_fetcher_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'feed_fetcher.py')

    with open(feed_fetcher_path, 'r') as f:
        content = f.read()

    # Check that redirects are disabled for security
    assert 'follow_redirects=False' in content, "feed_fetcher must disable follow_redirects to prevent redirect-based SSRF"


if __name__ == "__main__":
    print("Running security tests...")
    pytest.main([__file__, "-v"])
