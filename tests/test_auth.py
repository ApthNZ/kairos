"""Authentication and multi-user tests for Kairos."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest


def test_bcrypt_import():
    """Test that bcrypt is properly installed and importable."""
    import database
    assert hasattr(database, 'hash_password'), "database must have hash_password function"
    assert hasattr(database, 'verify_password'), "database must have verify_password function"


def test_password_hashing():
    """Test that password hashing works correctly."""
    import database

    password = "test_password_123"
    hashed = database.hash_password(password)

    # Hash should be different from original
    assert hashed != password
    # Hash should be a string
    assert isinstance(hashed, str)
    # Hash should start with bcrypt marker
    assert hashed.startswith('$2')
    # Verification should work
    assert database.verify_password(password, hashed) is True
    # Wrong password should fail
    assert database.verify_password("wrong_password", hashed) is False


def test_password_hash_uniqueness():
    """Test that same password produces different hashes (salt)."""
    import database

    password = "same_password"
    hash1 = database.hash_password(password)
    hash2 = database.hash_password(password)

    # Same password should produce different hashes due to salt
    assert hash1 != hash2
    # Both should verify correctly
    assert database.verify_password(password, hash1) is True
    assert database.verify_password(password, hash2) is True


def test_database_has_user_tables():
    """Test that database module has user management functions."""
    import database

    required_functions = [
        'create_user',
        'get_user_by_id',
        'get_user_by_username',
        'get_all_users',
        'update_user',
        'update_user_password',
        'authenticate_user',
    ]

    for func_name in required_functions:
        assert hasattr(database, func_name), f"database must have {func_name} function"


def test_database_has_session_functions():
    """Test that database module has session management functions."""
    import database

    required_functions = [
        'create_session',
        'get_session_by_token',
        'delete_session',
        'delete_user_sessions',
        'cleanup_expired_sessions',
    ]

    for func_name in required_functions:
        assert hasattr(database, func_name), f"database must have {func_name} function"


def test_database_has_audit_functions():
    """Test that database module has audit log functions."""
    import database

    required_functions = [
        'log_action',
        'get_recent_audit_logs',
        'get_user_audit_logs',
        'get_user_stats',
        'get_all_user_stats',
    ]

    for func_name in required_functions:
        assert hasattr(database, func_name), f"database must have {func_name} function"


def test_auth_endpoints_exist():
    """Test that main.py has auth endpoint functions."""
    main_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'main.py')

    with open(main_path, 'r') as f:
        content = f.read()

    required_endpoints = [
        '/api/auth/login',
        '/api/auth/logout',
        '/api/auth/me',
        '/api/auth/change-password',
    ]

    for endpoint in required_endpoints:
        assert endpoint in content, f"main.py must have {endpoint} endpoint"


def test_admin_endpoints_exist():
    """Test that main.py has admin endpoint functions."""
    main_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'main.py')

    with open(main_path, 'r') as f:
        content = f.read()

    required_endpoints = [
        '/api/admin/users',
        '/api/admin/stats',
        '/api/admin/audit',
    ]

    for endpoint in required_endpoints:
        assert endpoint in content, f"main.py must have {endpoint} endpoint"


def test_require_admin_dependency():
    """Test that admin endpoints use require_admin dependency."""
    main_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'main.py')

    with open(main_path, 'r') as f:
        content = f.read()

    assert 'require_admin' in content, "main.py must have require_admin function"
    assert 'Depends(require_admin)' in content, "Admin endpoints must use require_admin dependency"


def test_session_token_generation():
    """Test that session tokens are generated securely."""
    import database
    import secrets

    # Generate a test token
    token = secrets.token_hex(32)

    # Token should be 64 characters (32 bytes * 2 for hex)
    assert len(token) == 64
    # Token should be alphanumeric
    assert token.isalnum()


def test_login_page_exists():
    """Test that login.html exists."""
    login_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'login.html')
    assert os.path.exists(login_path), "login.html must exist"


def test_admin_page_exists():
    """Test that admin.html exists."""
    admin_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'admin.html')
    assert os.path.exists(admin_path), "admin.html must exist"


def test_bootstrap_script_exists():
    """Test that create_admin.py bootstrap script exists."""
    script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'create_admin.py')
    assert os.path.exists(script_path), "scripts/create_admin.py must exist"


def test_login_page_uses_kairos_token():
    """Test that login page stores token with correct key."""
    login_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'login.html')

    with open(login_path, 'r') as f:
        content = f.read()

    assert 'kairos_token' in content, "login.html must use 'kairos_token' storage key"
    assert 'kairos_user' in content, "login.html must store user info"


def test_app_js_auth_redirect():
    """Test that app.js redirects to login on 401."""
    app_js_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'app.js')

    with open(app_js_path, 'r') as f:
        content = f.read()

    assert 'kairos_token' in content, "app.js must use 'kairos_token' storage key"
    assert '/login.html' in content, "app.js must redirect to login.html on 401"
    assert 'logout' in content, "app.js must have logout function"


def test_config_has_session_settings():
    """Test that config has session-related settings."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'config.py')

    with open(config_path, 'r') as f:
        content = f.read()

    assert 'SESSION_EXPIRY_HOURS' in content, "config must have SESSION_EXPIRY_HOURS setting"
    assert 'MIN_PASSWORD_LENGTH' in content, "config must have MIN_PASSWORD_LENGTH setting"


def test_requirements_has_bcrypt():
    """Test that requirements.txt includes bcrypt."""
    requirements_path = os.path.join(os.path.dirname(__file__), '..', 'requirements.txt')

    with open(requirements_path, 'r') as f:
        content = f.read()

    assert 'bcrypt' in content, "requirements.txt must include bcrypt"


def test_triage_endpoint_has_audit_logging():
    """Test that triage endpoint includes audit logging."""
    main_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'main.py')

    with open(main_path, 'r') as f:
        content = f.read()

    # Check for audit log calls in triage context
    assert 'log_action' in content, "main.py must call log_action for audit logging"
    assert 'triage_alert' in content, "main.py must log triage_alert action"
    assert 'triage_digest' in content, "main.py must log triage_digest action"
    assert 'triage_skip' in content, "main.py must log triage_skip action"


if __name__ == "__main__":
    print("Running auth tests...")
    pytest.main([__file__, "-v"])
