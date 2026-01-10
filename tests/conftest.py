"""Pytest configuration and fixtures for Kairos tests."""
import os
import sys
import tempfile
from pathlib import Path

import pytest_asyncio

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    import database

    # Create temp file for database
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Override database path
    original_path = database.DATABASE_PATH
    database.DATABASE_PATH = Path(temp_path)

    # Initialize the database
    await database.init_db()

    yield temp_path

    # Restore original path and cleanup
    database.DATABASE_PATH = original_path
    try:
        os.unlink(temp_path)
    except OSError:
        pass


@pytest_asyncio.fixture
async def test_user(temp_db):
    """Create a test user and return their info."""
    import database

    user_id = await database.create_user(
        username="testuser",
        email="test@example.com",
        password="testpassword123",
        role="analyst"
    )

    user = await database.get_user_by_id(user_id)
    return {
        'id': user_id,
        'username': user['username'],
        'email': user['email'],
        'role': user['role'],
        'password': 'testpassword123'  # Keep plain password for login tests
    }


@pytest_asyncio.fixture
async def admin_user(temp_db):
    """Create an admin user and return their info."""
    import database

    user_id = await database.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpass123",
        role="admin"
    )

    user = await database.get_user_by_id(user_id)
    return {
        'id': user_id,
        'username': user['username'],
        'email': user['email'],
        'role': user['role'],
        'password': 'adminpass123'
    }


@pytest_asyncio.fixture
async def test_session(temp_db, test_user):
    """Create a test session and return the token."""
    import database

    token = await database.create_session(
        test_user['id'],
        expiry_hours=24,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    return {
        'token': token,
        'user': test_user
    }


@pytest_asyncio.fixture
async def admin_session(temp_db, admin_user):
    """Create an admin session and return the token."""
    import database

    token = await database.create_session(
        admin_user['id'],
        expiry_hours=24,
        ip_address="127.0.0.1",
        user_agent="pytest"
    )

    return {
        'token': token,
        'user': admin_user
    }
