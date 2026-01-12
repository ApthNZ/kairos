# Kairos Multi-User Testing Guide

## Access URLs

| Page | URL |
|------|-----|
| Main App | http://192.168.1.200:8083/ |
| Login Page | http://192.168.1.200:8083/login.html |
| Admin Dashboard | http://192.168.1.200:8083/admin.html |

## Test Credentials

```
Username: admin
Password: admin123
```

## Testing Checklist

### 1. Login Flow
- [x] Go to http://192.168.1.200:8083/login.html
- [x] Enter credentials above
- [x] Should redirect to main triage interface

### 2. Main Interface
- [x] Username displays in header with gold "Admin" badge
- [x] Logout button visible and working
- [x] "Dashboard" button visible (admin users only) - purple button, distinct from badge
- [x] Favicon appears next to "Kairos" title in header
- [x] Buttons show keyboard shortcuts: Alert (A), Digest (D), Skip (S)

### 3. Triage Actions
- [ ] Triage an item (Alert/Digest/Skip)
- [ ] Check that response includes `triaged_by: admin`
- [ ] Undo should work as before

### 4. Admin Dashboard
- [x] Click "Dashboard" button in header
- [ ] View contribution stats (will be empty initially)
- [ ] See user list with admin account
- [ ] View audit log showing login event

### 5. Create New User
- [ ] Use form in admin dashboard to create an analyst:
  - Username: `analyst1`
  - Email: `analyst1@localhost`
  - Password: `analyst123`
  - Role: `analyst`
  - Force password reset: (optional checkbox)
- [ ] Log out and log in as new user
- [ ] Verify analyst cannot access admin dashboard (403 error)
- [ ] If force_password_reset was checked, user should be prompted to change password
- [ ] Triage some items as analyst
- [ ] Log back in as admin, check leaderboard shows both users

### 6. Shared Queue Behavior
- [ ] Log in as admin in one browser
- [ ] Log in as analyst in another browser (or incognito)
- [ ] When one user triages an item, it disappears for both

## API Endpoints (for curl testing)

```bash
# Login
curl -X POST http://localhost:8083/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Get current user (replace TOKEN)
curl http://localhost:8083/api/auth/me \
  -H "Authorization: Bearer TOKEN"

# Get admin stats
curl http://localhost:8083/api/admin/stats \
  -H "Authorization: Bearer TOKEN"

# Get audit log
curl http://localhost:8083/api/admin/audit \
  -H "Authorization: Bearer TOKEN"

# Create new user (admin only)
curl -X POST http://localhost:8083/api/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"username": "analyst1", "email": "analyst1@localhost", "password": "analyst123", "role": "analyst"}'
```

## Notes

- 870 existing pending items preserved
- Legacy single-token auth still works if `AUTH_TOKEN` set in `.env`
- Session tokens expire after 24 hours
- All actions logged to audit trail
- Passwords hashed with bcrypt

## Recent Changes (2025-01-12)

### UI Updates
- **Favicon in header** - Two-headed bird icon now appears next to "Kairos" title
- **Keyboard shortcuts visible** - Buttons now show shortcuts: Alert (A), Digest (D), Skip (S)
- **Admin badge vs button** - Badge is now gold (status indicator), Dashboard button is purple (action)
- **Social media removed** - Only RSS feeds supported now (Priority 1 + Standard panels)

### User Management
- **Force password reset** - Checkbox when creating users to require password change on first login
- **Better error messages** - Fixed "[object Object]" error when creating users

### Backend
- Added `force_password_reset` column to users table
- Login response includes `force_password_reset` flag
- Password change clears the force reset flag

## If Something Goes Wrong

```bash
# Check container status
cd /home/apth/code/kairos
docker-compose ps
docker-compose logs --tail=50

# Restart container
docker-compose restart

# Recreate admin user if needed
docker exec kairos python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app')
import database

async def create_admin():
    await database.init_db()
    user_id = await database.create_user('admin', 'admin@localhost', 'admin123', 'admin')
    print(f'Created admin user with ID {user_id}')

asyncio.run(create_admin())
"
```
