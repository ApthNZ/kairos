"""Integration tests for authentication and multi-user system."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    import database

    # Create temp file for database
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Override database path
    original_path = database.DATABASE_PATH
    database.DATABASE_PATH = Path(temp_path)

    yield temp_path

    # Restore original path and cleanup
    database.DATABASE_PATH = original_path
    try:
        os.unlink(temp_path)
    except OSError:
        pass


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a valid bcrypt hash."""
        import database

        password = "testpassword123"
        hashed = database.hash_password(password)

        assert hashed.startswith('$2')
        assert len(hashed) == 60  # bcrypt hash length

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        import database

        password = "correctpassword"
        hashed = database.hash_password(password)

        assert database.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        import database

        password = "correctpassword"
        hashed = database.hash_password(password)

        assert database.verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (salting)."""
        import database

        password = "samepassword"
        hash1 = database.hash_password(password)
        hash2 = database.hash_password(password)

        assert hash1 != hash2
        assert database.verify_password(password, hash1) is True
        assert database.verify_password(password, hash2) is True

    def test_empty_password_hashes(self):
        """Test that empty passwords can be hashed."""
        import database

        hashed = database.hash_password("")
        assert database.verify_password("", hashed) is True
        assert database.verify_password("notempty", hashed) is False

    def test_unicode_password(self):
        """Test hashing passwords with unicode characters."""
        import database

        password = "pässwörd123日本語"
        hashed = database.hash_password(password)

        assert database.verify_password(password, hashed) is True
        assert database.verify_password("password123", hashed) is False


class TestUserManagement:
    """Tests for user management database functions."""

    @pytest.mark.asyncio
    async def test_create_user(self, temp_db):
        """Test creating a new user."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            role="analyst"
        )

        assert user_id is not None
        assert user_id > 0

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, temp_db):
        """Test getting user by ID."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            role="analyst"
        )

        user = await database.get_user_by_id(user_id)

        assert user is not None
        assert user['username'] == "testuser"
        assert user['email'] == "test@example.com"
        assert user['role'] == "analyst"
        assert user['active'] == 1

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, temp_db):
        """Test getting user by username."""
        import database

        await database.init_db()

        await database.create_user(
            username="findme",
            email="findme@example.com",
            password="password123",
            role="admin"
        )

        user = await database.get_user_by_username("findme")

        assert user is not None
        assert user['username'] == "findme"
        assert user['role'] == "admin"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, temp_db):
        """Test getting a user that doesn't exist."""
        import database

        await database.init_db()

        user = await database.get_user_by_username("doesnotexist")
        assert user is None

        user = await database.get_user_by_id(99999)
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, temp_db):
        """Test successful user authentication."""
        import database

        await database.init_db()

        await database.create_user(
            username="authtest",
            email="auth@example.com",
            password="mypassword123",
            role="analyst"
        )

        user = await database.authenticate_user("authtest", "mypassword123")

        assert user is not None
        assert user['username'] == "authtest"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, temp_db):
        """Test authentication with wrong password."""
        import database

        await database.init_db()

        await database.create_user(
            username="authtest",
            email="auth@example.com",
            password="mypassword123",
            role="analyst"
        )

        user = await database.authenticate_user("authtest", "wrongpassword")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, temp_db):
        """Test that inactive users cannot authenticate."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="password123",
            role="analyst"
        )

        # Deactivate user
        await database.update_user(user_id, active=False)

        user = await database.authenticate_user("inactiveuser", "password123")
        assert user is None

    @pytest.mark.asyncio
    async def test_update_user(self, temp_db):
        """Test updating user properties."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="updateme",
            email="update@example.com",
            password="password123",
            role="analyst"
        )

        # Update username and role
        result = await database.update_user(
            user_id,
            username="updated",
            role="admin"
        )

        assert result is True

        user = await database.get_user_by_id(user_id)
        assert user['username'] == "updated"
        assert user['role'] == "admin"

    @pytest.mark.asyncio
    async def test_update_user_password(self, temp_db):
        """Test updating user password."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="pwchange",
            email="pw@example.com",
            password="oldpassword",
            role="analyst"
        )

        # Change password
        result = await database.update_user_password(user_id, "newpassword123")
        assert result is True

        # Old password should fail
        user = await database.authenticate_user("pwchange", "oldpassword")
        assert user is None

        # New password should work
        user = await database.authenticate_user("pwchange", "newpassword123")
        assert user is not None

    @pytest.mark.asyncio
    async def test_get_all_users(self, temp_db):
        """Test getting all users."""
        import database

        await database.init_db()

        await database.create_user("user1", "user1@example.com", "password", "analyst")
        await database.create_user("user2", "user2@example.com", "password", "admin")
        await database.create_user("user3", "user3@example.com", "password", "analyst")

        users = await database.get_all_users()

        assert len(users) == 3
        usernames = [u['username'] for u in users]
        assert "user1" in usernames
        assert "user2" in usernames
        assert "user3" in usernames


class TestSessionManagement:
    """Tests for session management functions."""

    @pytest.mark.asyncio
    async def test_create_session(self, temp_db):
        """Test creating a session."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="sessiontest",
            email="session@example.com",
            password="password123",
            role="analyst"
        )

        token = await database.create_session(user_id, expiry_hours=24)

        assert token is not None
        assert len(token) == 64  # 32 bytes * 2 for hex

    @pytest.mark.asyncio
    async def test_get_session_by_token(self, temp_db):
        """Test getting session by token."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="sessiontest",
            email="session@example.com",
            password="password123",
            role="analyst"
        )

        token = await database.create_session(user_id, expiry_hours=24)
        session = await database.get_session_by_token(token)

        assert session is not None
        assert session['user_id'] == user_id
        assert session['token'] == token

    @pytest.mark.asyncio
    async def test_session_with_metadata(self, temp_db):
        """Test creating session with IP and user agent."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="sessiontest",
            email="session@example.com",
            password="password123",
            role="analyst"
        )

        token = await database.create_session(
            user_id,
            expiry_hours=24,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0"
        )

        session = await database.get_session_by_token(token)

        assert session['ip_address'] == "192.168.1.100"
        assert session['user_agent'] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_delete_session(self, temp_db):
        """Test deleting a session."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="sessiontest",
            email="session@example.com",
            password="password123",
            role="analyst"
        )

        token = await database.create_session(user_id)

        # Verify session exists
        session = await database.get_session_by_token(token)
        assert session is not None

        # Delete session
        await database.delete_session(token)

        # Verify session is gone
        session = await database.get_session_by_token(token)
        assert session is None

    @pytest.mark.asyncio
    async def test_delete_all_user_sessions(self, temp_db):
        """Test deleting all sessions for a user."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="sessiontest",
            email="session@example.com",
            password="password123",
            role="analyst"
        )

        # Create multiple sessions
        token1 = await database.create_session(user_id)
        token2 = await database.create_session(user_id)
        token3 = await database.create_session(user_id)

        # Delete all sessions
        await database.delete_user_sessions(user_id)

        # Verify all sessions are gone
        assert await database.get_session_by_token(token1) is None
        assert await database.get_session_by_token(token2) is None
        assert await database.get_session_by_token(token3) is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self, temp_db):
        """Test that invalid token returns None."""
        import database

        await database.init_db()

        session = await database.get_session_by_token("invalidtoken12345")
        assert session is None


class TestAuditLog:
    """Tests for audit log functions."""

    @pytest.mark.asyncio
    async def test_log_action(self, temp_db):
        """Test logging an action."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="audituser",
            email="audit@example.com",
            password="password123",
            role="analyst"
        )

        await database.log_action(
            user_id=user_id,
            action="triage_alert",
            item_id=123,
            details={"source": "test"}
        )

        logs = await database.get_recent_audit_logs(limit=10)

        assert len(logs) == 1
        assert logs[0]['user_id'] == user_id
        assert logs[0]['action'] == "triage_alert"
        assert logs[0]['item_id'] == 123

    @pytest.mark.asyncio
    async def test_get_user_audit_logs(self, temp_db):
        """Test getting audit logs for a specific user."""
        import database

        await database.init_db()

        user1 = await database.create_user("user1", "u1@test.com", "password", "analyst")
        user2 = await database.create_user("user2", "u2@test.com", "password", "analyst")

        await database.log_action(user1, "login")
        await database.log_action(user1, "triage_skip")
        await database.log_action(user2, "login")

        user1_logs = await database.get_user_audit_logs(user1)

        assert len(user1_logs) == 2
        assert all(log['user_id'] == user1 for log in user1_logs)

    @pytest.mark.asyncio
    async def test_get_user_stats(self, temp_db):
        """Test getting user statistics."""
        import database

        await database.init_db()

        user_id = await database.create_user(
            username="statsuser",
            email="stats@example.com",
            password="password123",
            role="analyst"
        )

        # Log various triage actions
        await database.log_action(user_id, "triage_alert")
        await database.log_action(user_id, "triage_alert")
        await database.log_action(user_id, "triage_digest")
        await database.log_action(user_id, "triage_skip")
        await database.log_action(user_id, "triage_skip")
        await database.log_action(user_id, "triage_skip")

        stats = await database.get_user_stats(user_id, days=30)

        assert stats['alerted'] == 2
        assert stats['digested'] == 1
        assert stats['skipped'] == 3
        assert stats['total'] == 6


class TestDatabaseInit:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, temp_db):
        """Test that init_db creates required tables."""
        import database
        import aiosqlite

        await database.init_db()

        async with aiosqlite.connect(temp_db) as db:
            # Check tables exist
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cursor:
                tables = [row[0] for row in await cursor.fetchall()]

        assert 'users' in tables
        assert 'sessions' in tables
        assert 'audit_log' in tables
        assert 'feeds' in tables
        assert 'items' in tables

    @pytest.mark.asyncio
    async def test_init_db_idempotent(self, temp_db):
        """Test that init_db can be called multiple times."""
        import database

        # Call init_db multiple times
        await database.init_db()
        await database.init_db()
        await database.init_db()

        # Should not raise any errors
        users = await database.get_all_users()
        assert users is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
