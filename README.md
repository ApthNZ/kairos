# Kairos

> A threat intelligence triage system for security professionals

## ⚠️ IMPORTANT DISCLAIMER

**THIS PROJECT WAS WRITTEN BY CLAUDE CODE AND IS PROVIDED AS-IS FOR EDUCATIONAL AND EXPERIMENTAL PURPOSES.**

**DO NOT USE THIS IN PRODUCTION WITHOUT THOROUGH SECURITY REVIEW AND TESTING.**

This is an AI-generated project that has not undergone professional security auditing. While functional, it should be treated as a prototype and learning tool. If you choose to deploy this system:

- Review all code thoroughly before deployment
- Perform your own security testing
- Never expose directly to the internet without proper hardening
- Use strong authentication tokens
- Keep all dependencies updated
- Monitor for vulnerabilities in dependencies

**Use at your own risk. The authors assume no liability for security issues, data loss, or any other problems arising from use of this software.**

---

Kairos is a self-hosted RSS feed aggregation and triage platform designed for security researchers, threat analysts, and SOC teams. It helps you efficiently process hundreds of security feeds, triage items with keyboard shortcuts, send immediate alerts via webhooks, and generate daily digest reports.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-required-blue.svg)

## 🚀 Quick Deploy

Deploy Kairos to the cloud in one click:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ApthNZ/kairos)

*After deployment, add your Discord/Slack webhook URL in the Render dashboard environment variables.*

## Features

- **📡 RSS Feed Aggregation** - Monitor 100+ security feeds simultaneously
- **⌨️ Keyboard-Driven Triage** - Review items at lightning speed (A/D/S/U shortcuts)
- **🚨 Instant Alerts** - Send critical items to Discord/Slack via webhooks
- **📋 Daily Digests** - Automated markdown reports of triaged intelligence
- **↶ Undo** - Accidentally hit the wrong key? Undo your last action
- **⏩ Skip All** - Bulk skip all pending items with one click
- **🎯 Priority-Based Queuing** - High-priority feeds surface first
- **🔄 Auto-Deduplication** - Never see the same item twice
- **🐳 Dockerized** - Deploy in minutes with Docker Compose
- **🔒 Optional Authentication** - Bearer token auth for secure deployments

## Quick Start

Choose your deployment method:
- **☁️ Cloud Deploy** - One-click deploy to Render.com (free tier, perfect for demos)
- **🐳 Self-Hosted** - Docker Compose on your own server

### ☁️ Cloud Deployment (Render.com)

**One-Click Deploy:**

1. Click the "Deploy to Render" button above
2. Sign in/up to Render.com
3. Name your service (e.g., `kairos-triage`)
4. Click "Apply"
5. Wait ~2 minutes for deployment

**Post-Deployment Setup:**

1. **Ready to use!** Your instance comes pre-configured with 15 curated threat intelligence feeds:
   - Government CERTs (CISA, UK NCSC, CERT-EU)
   - CVE/Exploit databases (Exploit-DB, Packet Storm, SANS ISC)
   - Threat research labs (Cisco Talos, Check Point, DFIR Report)
   - Security news (The Hacker's News, Bleeping Computer, Krebs, Dark Reading)

2. **Optional configuration** (via Render dashboard → Environment tab):
   - Add `WEBHOOK_URL` - Your Discord/Slack webhook for alerts
   - Update `AUTH_TOKEN` if you want a custom token
   - Change `TIMEZONE` to your timezone (default: UTC)

3. **Add more feeds** (optional):
   - Use the API to add feeds (see API section)
   - Or connect via Shell and edit `/app/feeds-starter.txt`

Your Kairos instance will be live at `https://your-service-name.onrender.com`

**Start triaging immediately!** The curated starter feeds will begin fetching within 5 minutes of deployment.

**⚠️ Free Tier Limitations:**
- **Ephemeral storage** - Database is wiped on each restart/redeploy (demo use only)
- Service sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds (cold start)
- **For persistent data:** Upgrade to Starter tier ($7/month) which includes persistent disks

**Free tier is perfect for:**
- Testing Kairos features
- Demoing to colleagues
- Evaluating before self-hosting

**Not recommended for:**
- Production triage workflows
- Long-term data retention

📖 **See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guides, feed management, and troubleshooting.**

---

### 🐳 Self-Hosted Deployment

**Prerequisites:**

- Docker and Docker Compose
- (Optional) Discord/Slack webhook URL for alerts

**Installation:**

1. **Clone the repository**
   ```bash
   git clone https://github.com/ApthNZ/kairos.git
   cd kairos
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env  # Edit configuration
   ```

   Key settings:
   - `WEBHOOK_URL` - Your Discord/Slack webhook for alerts
   - `AUTH_TOKEN` - Set a secure token (optional but recommended)
   - `TIMEZONE` - Your timezone for digest scheduling

3. **Add your feeds**

   Edit `feeds.txt` with your RSS feeds:
   ```
   https://example.com/feed.xml|Feed Name|9
   ```
   Format: `URL|Name|Priority` (priority 0-10, higher shown first)

4. **Start Kairos**
   ```bash
   docker-compose up -d
   ```

5. **Access the interface**

   Open http://localhost:8083 in your browser

---

### 🌐 Alternative Cloud Platforms

Kairos works on any Docker-capable platform. Here are other recommended options:

**Railway.app**
- $5/month free credits
- Beautiful UI, GitHub integration
- Deploy: Connect repo → Auto-detects Dockerfile → Add volume for `/app/data`
- [railway.app](https://railway.app)

**Fly.io**
- Free tier (3 shared VMs)
- Docker-native platform
- Deploy: `flyctl launch` → `flyctl volumes create` → `flyctl deploy`
- [fly.io](https://fly.io)

**DigitalOcean App Platform**
- Pay-as-you-go ($5/month basic plan)
- GitHub integration, managed platform
- [digitalocean.com/products/app-platform](https://www.digitalocean.com/products/app-platform)

All platforms support:
- Direct Dockerfile deployment
- Environment variables for configuration
- Persistent volumes for database storage
- Auto-deploy from GitHub

## Usage

### Web Interface

Once running, you'll see a clean triage interface showing one item at a time.

**Keyboard Shortcuts:**
- `A` - Send immediate alert (webhook)
- `D` - Add to daily digest
- `S` - Skip (mark reviewed, no action)
- `U` - Undo last action
- `?` - Show help

**Bulk Actions:**
- **Skip All** button - Quickly skip all remaining pending items (useful for clearing old feeds)

### Feed Management

**Cloud Deployments (Render, Railway, Fly.io):**

Kairos ships with 15 curated starter feeds pre-configured. You can add more feeds using:

**Option 1: Use the API** (Recommended)
```bash
curl -X POST http://localhost:8083/api/feeds \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/feed.xml", "name": "Example", "priority": 8}'
```

**Self-Hosted Deployments (Docker Compose):**

**Option 1: Edit feeds.txt** (for custom feed lists)
```
# Format: URL|Name|Priority (0-10)
https://feeds.feedburner.com/TheHackersNews|The Hacker's News|9
https://www.bleepingcomputer.com/feed/|Bleeping Computer|9
https://krebsonsecurity.com/feed/|Krebs on Security|8
```

Then restart: `docker-compose restart`

**Option 2: Use the API** (same as above)

### Webhook Integration

Kairos sends rich Discord embeds when you hit `A` on an item:

```json
{
  "embeds": [{
    "title": "Critical Vulnerability Announced",
    "url": "https://...",
    "description": "Summary...",
    "color": 15158332,
    "fields": [
      {"name": "Source", "value": "CISA", "inline": true},
      {"name": "Triaged By", "value": "analyst", "inline": true}
    ],
    "footer": {"text": "Kairos Threat Intelligence"},
    "timestamp": "2025-01-20T10:00:00Z"
  }]
}
```

Works with:
- Discord webhooks
- Slack incoming webhooks
- Any service accepting JSON POST

### Daily Digests

Digests auto-generate daily at the configured time (default: 09:00).

Manual generation:
- Click "Generate Digest Now" in footer
- Or via API: `POST /api/digest/generate`

Output: `./digests/YYYY-MM-DD-digest.md`

## API Documentation

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth) |
| `/api/metrics` | GET | System metrics |
| `/api/items/next` | GET | Get next item to triage |
| `/api/items/{id}/triage` | POST | Triage an item |
| `/api/items/{id}/undo` | POST | Undo triage action |
| `/api/items/skip-all` | POST | Skip all pending items |
| `/api/feeds` | GET | List all feeds |
| `/api/feeds` | POST | Add new feed |
| `/api/feeds/{id}` | DELETE | Remove feed |
| `/api/digest/generate` | POST | Generate digest now |
| `/api/digest/latest` | GET | Download latest digest |

### Authentication

If `AUTH_TOKEN` is set in `.env`, include it in requests:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8083/api/items/next
```

The web interface will prompt for the token and save it in localStorage.

## Configuration

All configuration via environment variables in `.env`:

```bash
# Feed fetching
FEED_REFRESH_MINUTES=15        # How often to fetch feeds
MAX_ITEMS_PER_FEED=50          # Max items per feed
FEED_PARALLEL_WORKERS=5        # Concurrent feed fetches
FEED_TIMEOUT_SECONDS=30        # Timeout per feed

# Webhook
WEBHOOK_URL=https://...        # Discord/Slack webhook
WEBHOOK_RETRY_COUNT=3          # Retry attempts

# Digest
DIGEST_GENERATION_TIME=09:00   # Daily digest time (HH:MM)
TIMEZONE=UTC                   # Timezone for scheduling

# Security
AUTH_TOKEN=                    # Bearer token (optional)
USER_IDENTIFIER=analyst        # Your username for audit trail

# Web
PORT=8083                      # Web interface port
```

## Architecture

```
kairos/
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # SQLite with aiosqlite
│   ├── feed_fetcher.py      # Async RSS fetching
│   ├── webhook_handler.py   # Webhook queue processor
│   ├── digest_generator.py  # Markdown digest generator
│   └── static/              # Web UI (HTML/CSS/JS)
├── data/                    # SQLite database (volume)
├── digests/                 # Generated digests (volume)
├── feeds.txt               # Your feed list
├── docker-compose.yml
└── Dockerfile
```

**Tech Stack:**
- Backend: FastAPI + Python 3.11
- Database: SQLite (aiosqlite)
- Frontend: Vanilla HTML/CSS/JavaScript
- Scheduler: APScheduler
- Container: Docker

## Performance

- Handles 200+ feeds efficiently
- Async parallel fetching (configurable workers)
- Indexed database queries for fast triage
- Minimal resource usage (~100MB RAM)

**Example Performance:**
- 144 feeds fetched in ~2 minutes
- 2600+ items loaded
- Success rate: ~98%

## Monitoring

```bash
# Health check
curl http://localhost:8083/health

# Metrics
curl http://localhost:8083/api/metrics

# Logs
docker-compose logs -f kairos

# Container status
docker ps | grep kairos
```

## Backup

All data in two directories:

```bash
# Backup
tar -czf kairos-backup.tar.gz data/ digests/

# Restore
tar -xzf kairos-backup.tar.gz
```

## Troubleshooting

### Container won't start
```bash
docker-compose logs kairos
# Check port availability
sudo netstat -tlnp | grep 8083
```

### Feeds not updating
```bash
# Manual refresh
curl -X POST http://localhost:8083/api/feeds/refresh

# Check logs for errors
docker-compose logs kairos | grep ERROR
```

### Webhook failures
- Verify webhook URL is accessible
- Check logs for retry attempts
- Webhooks retry 3 times with exponential backoff

## Security Considerations

1. **Set AUTH_TOKEN** - Generate with: `openssl rand -hex 32`
2. **Use HTTPS** - Put behind reverse proxy (nginx/Caddy)
3. **Keep secrets safe** - Never commit `.env` to git
4. **Regular updates** - Keep Docker image and dependencies updated

## Development

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run locally
cd app
python -m uvicorn main:app --reload --port 8083
```

### Building

```bash
docker-compose build
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file

## Acknowledgments

- Built for security professionals by security professionals
- Inspired by the need for efficient threat intelligence triage
- Named after Kairos, the ancient Greek concept of the opportune moment

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: This README and inline code docs

---

**Made with ☕ for the security community**
