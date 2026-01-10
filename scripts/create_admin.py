#!/usr/bin/env python3
"""Bootstrap script to create initial admin user for Kairos multi-user system."""
import asyncio
import getpass
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

import database


async def create_admin():
    """Interactive admin user creation."""
    print("\n=== Kairos Admin Bootstrap ===\n")

    # Initialize database (creates tables if needed)
    await database.init_db()
    print("Database initialized.\n")

    # Check if any users exist
    users = await database.get_all_users()
    if users:
        print(f"Found {len(users)} existing user(s):")
        for user in users:
            role_str = "[ADMIN]" if user['role'] == 'admin' else "[analyst]"
            status = "active" if user['active'] else "inactive"
            print(f"  - {user['username']} {role_str} ({status})")
        print()

        response = input("Create another admin user? [y/N]: ").strip().lower()
        if response != 'y':
            print("Exiting.")
            return

    print("Creating new admin user...\n")

    # Get username
    while True:
        username = input("Username (min 3 chars): ").strip()
        if len(username) < 3:
            print("Username must be at least 3 characters.")
            continue

        existing = await database.get_user_by_username(username)
        if existing:
            print(f"Username '{username}' already exists.")
            continue
        break

    # Get email
    while True:
        email = input("Email: ").strip()
        if not email or '@' not in email:
            print("Please enter a valid email address.")
            continue
        break

    # Get password
    while True:
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Passwords do not match.")
            continue
        break

    # Create the admin user
    try:
        user_id = await database.create_user(
            username=username,
            email=email,
            password=password,
            role='admin'
        )
        print(f"\nAdmin user '{username}' created successfully! (ID: {user_id})")
        print("\nYou can now log in at /login.html")
    except Exception as e:
        print(f"\nError creating user: {e}")
        sys.exit(1)


def main():
    """Entry point."""
    try:
        asyncio.run(create_admin())
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)


if __name__ == '__main__':
    main()
