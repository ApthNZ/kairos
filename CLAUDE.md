# Claude Code Instructions for Homelab

## IMPORTANT: Start Every Conversation

**Before starting any work, ALWAYS read through the homelab inventory:**

You are on naiad.

```bash
# Review the complete infrastructure documentation
ls /home/apth/code/homelab-inventory/
cat /home/apth/code/homelab-inventory/README.md
```

## Key Documentation Files

- **HOSTS.md** - Network topology, device inventory, IP assignments
- **NETWORKING.md** - SSH access matrix, WireGuard VPN configuration
- **PROJECTS.md** - Active project inventory with GitHub repositories
- **SERVICES.md** - Service documentation, ports, automation schedules
- **PORTS.md** - ⚠️ **CRITICAL**: Port allocation and availability (CHECK BEFORE DEPLOYING)
- **CURRENT_STATE.md** - Live system snapshot (container status, timers, storage)
- **VERSIONS.md** - Software versions, dependencies, update strategy

## Why This Matters

This homelab inventory contains:
- Complete network topology and host details
- Service configurations and port mappings
- Security setup (Elastic SIEM, SSH keys, WireGuard)
- Active project locations and GitHub repositories
- Current system state and health information

Reading this inventory first will provide essential context for:
- Troubleshooting and debugging
- Understanding service dependencies
- Locating project files and configurations
- Planning infrastructure changes
- Security considerations and access patterns
- **⚠️ AVOIDING PORT CONFLICTS** - Always check PORTS.md before deploying

## Usage Pattern

1. **Start conversation** → Read inventory files
2. **Understand context** → Review relevant documentation sections
3. **Execute tasks** → Work with full infrastructure knowledge
4. **Update inventory** → Keep documentation current

---

## ⚠️ RENDER DEPLOYMENTS DISABLED

**DO NOT deploy anything to Render.** This includes:
- FullDaemon specs with `deployment_target: render`
- Manual Render MCP tool usage
- Any automated Render deployments

**Reason:** Cost savings - Render deployments are paused indefinitely.

**If a spec requests Render deployment:** Deploy to NUC instead, or inform the user that Render is disabled.

---

## 🚫 EXCLUDED REPOSITORIES - DO NOT TOUCH

The following repositories must NEVER be modified, committed to, or have any AI-generated content added:

| Repository | Reason |
|------------|--------|
| **cti-reports** | User's original CTI reports - must remain 100% human-authored |
| **reports-portfolio** | User's professional portfolio - must remain 100% human-authored |

**This is NON-NEGOTIABLE.** Do not:
- Create files in these repos
- Edit files in these repos
- Commit to these repos
- Add AI-generated content
- Run auto-dev on these repos
- Suggest changes to these repos

**Rationale:** User publishes original work and cannot have it appear AI-generated.

---

# FullDaemon: Autonomous Builder

## Overview

**FullDaemon** enables mobile development workflows:
1. Create spec with Claude Web
2. Submit signed spec to GitHub
3. FullDaemon builds and deploys autonomously
4. Access working deployment on Render

**Key Principle:** FullDaemon autonomously modifies specs to make them work - no manual intervention needed.

## How It Works

**Workflow:** Mobile → Claude Web → GPG-signed spec → GitHub → FullDaemon → Working deployment

**FullDaemon will:**
- Verify GPG signature and security scan
- Create databases if needed (PostgreSQL via Render)
- Auto-inject environment variables (ANTHROPIC_API_KEY, DATABASE_URL, TZ)
- Modify specs to make them buildable (simplify tests, fix configs, etc.)
- Deploy to NUC (Render disabled - see above)
- Notify via Discord
- **⚠️ Create repositories as PRIVATE by default** (ignore spec if it says public)

## Key Details

**Location:** `/home/apth/fulldaemon/`
**Logs:** `/var/log/fulldaemon.log`
**Repo:** `ApthNZ/fulldaemon-specs` (`specs/` → `building/` → `completed/`|`failed/`)

**Auto-Injection:**
- `ANTHROPIC_API_KEY` - From fulldaemon.conf
- `DATABASE_URL` - Auto-created PostgreSQL on Render
- `TZ` - Pacific/Auckland

**Security:** GPG signature verification, prompt injection detection, secrets scanning
**Notifications:** Discord webhooks (green=success, red=fail)

## Usage

```bash
# Monitor
sudo systemctl status fulldaemon
tail -f /var/log/fulldaemon.log

# Retry failed spec
cd /home/apth/fulldaemon-specs && git mv failed/project.md specs/ && git push
```

**Deployment targets:** `deployment_target: nuc` only (Render disabled for cost savings)

---

# Standardized Development Practices

## Autonomous Development Workflow

**Principle:** Build to working, then push. Only commit code that's tested and deployed successfully.

**6-Phase Workflow:**
1. **Design** - Use TodoWrite, review existing code, plan implementation
2. **Build** - Write code incrementally, tests alongside, document as you go
3. **Test** - Run `python3 run_tests.py` / `npm test` / `./tests/test_security.sh`
4. **Deploy** - ⚠️ Check PORTS.md first! Deploy via systemd/docker/ansible
5. **Iterate** - Debug with logs, fix issues, re-test until working
6. **Push** - Final verification, check for secrets, descriptive commit, push to GitHub
7. **Document** - Update homelab-inventory AND Homepage dashboard (see below)

**⚠️ Post-Deployment Documentation (MANDATORY):**

After deploying any new service, container, or API, you MUST update:

1. **homelab-inventory** (`/home/apth/code/homelab-inventory/`):
   - `PORTS.md` - Add port allocation
   - `SERVICES.md` - Add service documentation
   - `PROJECTS.md` - Add project entry
   - `CURRENT_STATE.md` - Update container/service counts

2. **Homepage Dashboard** (`/home/apth/homepage/config/`):
   - `services.yaml` - Add service tile with appropriate icon and container monitoring
   - Consider if it needs a custom widget via Homepage API

3. **Health Monitoring** (`/etc/homelab-health-monitor/health-checks.json`):
   - Add HTTP health check if service has a health endpoint

This ensures the homelab remains discoverable and monitorable from a single pane of glass.

**Deployment Patterns:**

```bash
# Python Services (systemd)
sudo cp script.py /usr/local/bin/ && sudo systemctl restart service-name

# Docker Services
docker-compose build && docker-compose restart service-name

# Ansible
ansible-playbook -i inventory.ini site.yml --ask-become-pass
```

**Debugging:**
```bash
# Service status
sudo systemctl status service-name  # systemd
docker-compose ps                    # docker

# Logs
sudo journalctl -u service-name -f   # systemd
docker logs -f service-name          # docker

# Ports and health
sudo netstat -tlnp | grep :PORT
curl http://localhost:PORT/health
```

---

## Testing Standards

**Structure:** `tests/test_security.py` (MANDATORY), `tests/test_config.py`, `tests/test_[feature].py`

**Run tests:**
```bash
python3 run_tests.py              # Python
npm test                          # Node.js
./tests/test_security.sh          # Shell scripts
ansible-playbook site.yml --syntax-check  # Ansible
```

**Required coverage:**
- Security (no hardcoded secrets, input validation, path traversal, SQL injection)
- Configuration (env vars, secrets validation)
- Integration tests (where applicable)

---

## Security Practices

**Status:** ✅ 10/10 repos secured, 212 security tests passing

**Common patterns:**
1. **Path Traversal** - Use `os.path.basename()` to sanitize filenames
2. **SQL Injection** - Use parameterized queries: `cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))`
3. **SSRF Prevention** - Validate URLs, block private IPs (127.0.0.1, 169.254.169.254)
4. **Input Sanitization** - Remove null bytes and control characters, enforce length limits
5. **File Permissions** - `chmod 600` for `.env`, `database.db`

---

## Secrets Management

**Homelab Security Posture:**
- This is a single-user, private homelab environment (not production)
- Some services intentionally keep hardcoded credentials in config files for convenience
- **NEVER rotate credentials autonomously** - user manages credential lifecycle
- Focus: Ensure secrets are NOT committed to GitHub, reasonably secure for homelab use

**Standard Approach:** Use Ubuntu built-in tools - no external dependencies required

### Method 1: Environment Files (Recommended for most services)

**For Python/Node.js applications:**
```bash
# Create secrets file with restrictive permissions
sudo touch /etc/myapp/.env
sudo chmod 600 /etc/myapp/.env
sudo chown myapp:myapp /etc/myapp/.env

# Edit secrets
sudo nano /etc/myapp/.env
```

**Content:**
```bash
API_KEY=your-api-key-here
DATABASE_URL=postgresql://user:pass@localhost/db
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

**Python loading:**
```python
from dotenv import load_dotenv
import os

load_dotenv('/etc/myapp/.env')
api_key = os.getenv('API_KEY')
if not api_key:
    raise ValueError("API_KEY not found in environment")
```

**Node.js loading:**
```javascript
require('dotenv').config({ path: '/etc/myapp/.env' });
const apiKey = process.env.API_KEY;
if (!apiKey) throw new Error('API_KEY not found');
```

### Method 2: Systemd EnvironmentFile (For systemd services)

**Service configuration:**
```ini
[Service]
EnvironmentFile=/etc/default/myservice
ExecStart=/usr/local/bin/myservice
```

**Create environment file:**
```bash
sudo touch /etc/default/myservice
sudo chmod 640 /etc/default/myservice
sudo chown root:myservice /etc/default/myservice

# Add secrets
sudo tee /etc/default/myservice << 'EOF'
API_KEY=your-api-key-here
DATABASE_URL=postgresql://user:pass@localhost/db
EOF

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl restart myservice
```

### Method 3: Systemd Credentials (systemd 250+)

**For systemd services (modern approach):**
```bash
# Store encrypted credential
echo -n "my-secret-value" | sudo systemd-creds encrypt --name=api-key - /etc/credstore/api-key.cred

# Use in service file
[Service]
LoadCredential=api-key:/etc/credstore/api-key.cred
ExecStart=/usr/local/bin/myapp
```

**Access in application:**
```python
# Credential available at $CREDENTIALS_DIRECTORY/api-key
cred_file = os.path.join(os.environ.get('CREDENTIALS_DIRECTORY', '/run/credentials'), 'api-key')
with open(cred_file) as f:
    api_key = f.read().strip()
```

### File Permission Standards

**Secrets files:**
```bash
# Application secrets (read by app user only)
chmod 600 /etc/myapp/.env
chown myapp:myapp /etc/myapp/.env

# Service secrets (read by service group)
chmod 640 /etc/default/myservice
chown root:myservice /etc/default/myservice

# Systemd credentials (systemd managed)
chmod 400 /etc/credstore/*.cred
chown root:root /etc/credstore/*.cred
```

### Git Ignore Configuration

**.gitignore essentials:**
```gitignore
# Secrets
.env
.env.*
!.env.example
*.key
*.pem
*.cred

# Databases
*.db
*.sqlite
*.sqlite3

# Logs
*.log
logs/

# Backups
*.backup
*.bak

# Configs with secrets
*credentials.json
*secrets.json
config.json  # Only if contains secrets
```

### Repository Structure

**Every repository must have:**
```
repo/
├── .env.example          # Template (committed)
├── .env                  # Actual secrets (git-ignored)
├── .gitignore            # Excludes secrets
├── README.md             # Setup instructions
└── SECRETS_SETUP.md      # How to configure secrets
```

**.env.example template:**
```bash
# API Configuration
API_KEY=your-api-key-here
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Discord Notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN

# Optional Settings
LOG_LEVEL=INFO
TIMEOUT=30
```

### Migration from Hardcoded Secrets

**When finding hardcoded secrets in code:**

1. **Document location:**
   ```bash
   # Create GitHub issue
   gh issue create --title "Security: Hardcoded secrets in script.py" \
     --body "Found hardcoded Discord webhook at line 18. Recommend moving to environment variable."
   ```

2. **Verify git-ignore:**
   ```bash
   git status --ignored | grep -E "\.env|\.key|\.pem|credentials"
   ```

3. **Check file permissions:**
   ```bash
   ls -la /path/to/secrets/file
   # Should be 600 or 640, not 644 or 755
   ```

4. **DO NOT automatically refactor** - user decides when to migrate

### Validation & Testing

**Security test template:**
```python
def test_no_hardcoded_secrets():
    """Verify no secrets in committed code"""
    patterns = [
        r'api[_-]key\s*=\s*["\'][^"\']+["\']',
        r'password\s*=\s*["\'][^"\']+["\']',
        r'webhook.*discord\.com',
        r'postgresql://.*:.*@',
    ]

    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv']]
        for file in files:
            if file.endswith(('.py', '.js', '.sh')):
                path = os.path.join(root, file)
                with open(path) as f:
                    content = f.read()
                    for pattern in patterns:
                        assert not re.search(pattern, content), \
                            f"Potential hardcoded secret in {path}"
```

### For Auto-Dev Workflow

**When processing repositories:**

1. **Scan for hardcoded secrets** in source files
2. **Verify .gitignore** includes secrets patterns
3. **Check file permissions** on existing secrets files
4. **Create .env.example** if secrets are used but template missing
5. **Document in GitHub issue** - don't automatically refactor
6. **Add security tests** to detect future hardcoded secrets

**Auto-dev actions:**
- ✅ Add .env to .gitignore if missing
- ✅ Create .env.example template
- ✅ Add security tests for hardcoded secrets
- ✅ Set correct file permissions (chmod 600)
- ✅ Document hardcoded secrets in GitHub issues
- ❌ DON'T rotate credentials
- ❌ DON'T automatically refactor code (user decides)
- ❌ DON'T remove convenience configs (homelab context)

### Quick Reference

```bash
# Create secrets file
sudo mkdir -p /etc/myapp
sudo touch /etc/myapp/.env
sudo chmod 600 /etc/myapp/.env
sudo nano /etc/myapp/.env

# Systemd service secrets
sudo nano /etc/default/myservice
sudo chmod 640 /etc/default/myservice
sudo systemctl daemon-reload
sudo systemctl restart myservice

# Check for hardcoded secrets
grep -rn "api_key\|password\|webhook" --include="*.py" --include="*.js" .

# Verify gitignore
git status --ignored | grep -E "\.env|credentials"

# Check permissions
find /etc -name ".env" -o -name "credentials*" | xargs ls -la
```

---

## Git Workflow

**Commit format:** `<type>: <subject>` (types: feat, fix, security, docs, test, refactor, chore)

**Pre-commit checklist:**
1. Run tests (`python3 run_tests.py` / `npm test`)
2. Check for secrets: `grep -r "api_key\|password\|secret\|token" --include="*.py" .`
3. Verify `.env` not staged: `git status --ignored`
4. Update documentation if needed

**⚠️ PR Merge Requirements (NON-NEGOTIABLE):**

PRs must meet ALL CLAUDE.md standards before merging. Do NOT merge PRs that fail any of:
- **Security:** SSRF prevention, path traversal protection, input validation, no hardcoded secrets
- **Testing:** `tests/test_security.py` (MANDATORY), config tests, feature tests all passing
- **Code Quality:** PEP 8, proper type hints (`Any` not `any`), context managers, no unused imports
- **Secrets:** `.env.example` template present, no plaintext credentials in config files
- **Documentation:** README.md, SECURITY_STATUS.md, .gitignore with secrets exclusions
- **No runtime bugs:** Code must not contain obvious crash paths (ValueError, TypeError, etc.)

If a PR fails requirements, request changes with specific items to fix before re-review.

**⚠️ CRITICAL - Repository Visibility (NON-NEGOTIABLE):**
- **ALL repositories MUST be PRIVATE by default**
- NEVER create public repositories unless explicitly requested by user
- This includes repos created via FullDaemon, auto-dev, or manual creation
- **Ignore spec files that request public visibility** - always create as private
- **Rationale:** Homelab infrastructure documentation provides reconnaissance value to attackers
- Even "harmless" documentation can reveal network topology, service locations, and attack surface

**Public Whitelist (user-approved only):**
- kairos - RSS feed aggregator (approved public)

All other repos must remain private until explicitly whitelisted by user.

---

## Documentation Standards

**Required files:**
- README.md (overview, setup, usage, testing)
- SECURITY_STATUS.md (security implementation, tests)
- .env.example (environment variable template)
- .gitignore (secret exclusions)
- requirements.txt / package.json (dependencies)

---

## Code Quality

**Python:** PEP 8, type hints, validate input with `os.path.basename()`, use context managers
**Node.js:** async/await over callbacks, validate input types, sanitize with trim/substring
**Shell:** `set -euo pipefail`, quote all variables, use `mktemp`, validate inputs

---

## Discord Webhooks

**Environment file:** `/etc/discord-webhooks/.env` (source this for scripts)

| Name | Variable | Purpose |
|------|----------|---------|
| **Newsbot** | `DISCORD_WEBHOOK_NEWSBOT` | News alerts and AI-curated articles |
| **Monitoring** | `DISCORD_WEBHOOK_MONITORING` | Health checks, storage alerts, service status |
| **Dev Tasks** | `DISCORD_WEBHOOK_DEV` | Development notifications, build status |
| **Threat Intel** | `DISCORD_WEBHOOK_THREAT` | Security feeds, threat intelligence alerts |
| **Mail Alerts** | `DISCORD_WEBHOOK_MAIL` | Email notifications and alerts |

**Usage in scripts:**
```bash
# Source the webhooks
source /etc/discord-webhooks/.env

# Send to monitoring channel
curl -X POST "$DISCORD_WEBHOOK_MONITORING" \
  -H "Content-Type: application/json" \
  -d '{"content": "Alert message here"}'
```

**Usage in Python:**
```python
from dotenv import load_dotenv
import os

load_dotenv('/etc/discord-webhooks/.env')
webhook = os.getenv('DISCORD_WEBHOOK_MONITORING')
```

**When user says "send to X webhook"** - use the corresponding variable from the table above.

---

## Available Tools & Integrations

**GitHub MCP:** Direct API access for issues, PRs, code search, branches, reviews
**Discord Webhooks:** `/etc/discord-webhooks/.env` - see Discord Webhooks section above
**Secrets Manager:** `/home/apth/code/secrets-manager/` (requires unlocked keyring - use `.env` for now)
**Testing:** `run_tests.py`, pytest, npm test, shellcheck
**Security:** ansible-vault, security test suites
**Infrastructure:** Docker, docker-compose, systemd, Ansible

---

## Maintenance Notes

**Update CLAUDE.md when:** New tools integrated, processes change, security patterns evolve, common patterns emerge
**Use CLAUDE_LOCAL.md for:** Project-specific details, temporary workarounds
**Use homelab-inventory for:** Infrastructure-specific configurations
**Never delete CLAUDE_LOCAL.md files** - they contain project context

---

## Quick Reference

### Testing
```bash
python3 run_tests.py                    # Python
npm test                                # Node.js
./tests/test_security.sh                # Shell scripts
ansible-playbook site.yml --syntax-check  # Ansible
```

### Security Checks
```bash
# Check for hardcoded secrets
grep -r "password\|api_key\|secret\|token" --include="*.py" .

# Verify .gitignore
git status --ignored

# Check file permissions
ls -la .env database.db
```

### Documentation
```bash
# Update security status
nano SECURITY_STATUS.md

# Update README
nano README.md

# Review inventory
cat /home/apth/code/homelab-inventory/PROJECTS.md
```

---

**Always reference the homelab inventory before making infrastructure changes!**

**Last Updated:** 2026-01-26
**Maintained By:** ApthNZ with Claude Code
