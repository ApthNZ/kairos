# Kairos Deployment Guide

This guide covers deploying Kairos to various platforms and managing feeds post-deployment.

## Quick Deploy to Render.com

### Initial Setup

1. **Deploy**
   - Click "Deploy to Render" button in README
   - Sign up/in to Render.com
   - Name your service
   - Click "Apply"

2. **Wait for Build**
   - First build takes ~2-3 minutes
   - Watch the logs in real-time
   - Service goes live automatically

3. **Get Your URL**
   - Your instance: `https://your-service-name.onrender.com`
   - Health check: `https://your-service-name.onrender.com/health`

### ⚠️ Important: Free Tier Storage Limitations

**Render's free tier uses ephemeral storage:**
- Database stored in `/app/data/triage.db`
- **Data is LOST on every restart or redeploy**
- Service restarts happen on code changes, manual restarts, or platform maintenance
- This makes free tier suitable ONLY for demos and testing

**For persistent data (production use):**

1. Upgrade to Starter tier ($7/month):
   - Go to service Settings → Plan
   - Upgrade to "Starter"
   - Add persistent disk:
     - Dashboard → Disks → "Add Disk"
     - Name: `kairos-data`
     - Mount Path: `/app/data`
     - Size: 1GB (sufficient for most use cases)
   - Redeploy service

2. Or self-host with Docker Compose (see below)

**Free Tier Best Use Cases:**
- Quick feature testing
- Showing Kairos to colleagues
- Evaluating before committing to paid tier or self-hosting
- Short-term triage sessions (cleared on restart)

### Post-Deployment Configuration

#### Add Webhook (Optional)

1. Go to your service in Render dashboard
2. Click "Environment" tab
3. Add new environment variable:
   - **Key**: `WEBHOOK_URL`
   - **Value**: Your Discord/Slack webhook URL
4. Save changes (service auto-redeploys)

#### Update Authentication Token

The deployment auto-generates a secure `AUTH_TOKEN`. To view or change it:

1. Go to "Environment" tab
2. Find `AUTH_TOKEN`
3. Click "Reveal" to see the token
4. Copy it for API access
5. Or regenerate: Delete and add new value

#### Change Timezone

Default is UTC. To change:

1. "Environment" tab
2. Edit `TIMEZONE`
3. Use format: `America/New_York`, `Europe/London`, `Asia/Tokyo`
4. [Full timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

### Adding RSS Feeds

You have three options for adding feeds to your deployed instance:

#### Option 1: Shell Access (Recommended for Bulk)

1. In Render dashboard, go to "Shell" tab
2. Connect to shell
3. Edit feeds file:
   ```bash
   nano /app/feeds.txt
   ```
4. Add your feeds (one per line):
   ```
   https://feeds.feedburner.com/TheHackersNews|The Hacker's News|9
   https://www.bleepingcomputer.com/feed/|Bleeping Computer|8
   ```
5. Save (`Ctrl+O`, `Enter`, `Ctrl+X`)
6. Restart service or wait for next fetch cycle (5 minutes)

**Feed Format:** `URL|Display Name|Priority`
- Priority: 0-10 (higher = shown first)
- 10 = CERTs/Critical alerts
- 9 = CVEs/Exploits
- 7-8 = Vendor blogs
- 5-6 = General security news

#### Option 2: API (Recommended for Single Feeds)

Add feeds via the API:

```bash
curl -X POST https://your-service.onrender.com/api/feeds \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/feed.xml",
    "name": "Example Feed",
    "priority": 8
  }'
```

List all feeds:
```bash
curl https://your-service.onrender.com/api/feeds \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

#### Option 3: Pre-Populate Before Deploy

1. Fork the Kairos repository
2. Edit `feeds.txt` in your fork
3. Commit changes
4. Deploy from your fork instead

### Example Feed Collections

**Security Research Starter Pack** (20 feeds):
```
https://feeds.feedburner.com/TheHackersNews|The Hacker's News|9
https://www.bleepingcomputer.com/feed/|Bleeping Computer|8
https://krebsonsecurity.com/feed/|Krebs on Security|8
https://www.schneier.com/blog/atom.xml|Schneier on Security|7
https://threatpost.com/feed/|Threatpost|7
https://www.darkreading.com/rss.xml|Dark Reading|7
https://www.securityweek.com/feed/|SecurityWeek|7
```

**CERT/Government Alerts** (Priority 10):
```
https://www.cisa.gov/cybersecurity-advisories/all.xml|US-CERT|10
https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml|UK NCSC|10
https://www.cert.europa.eu/publications/threat-intelligence-rss|CERT-EU|10
```

**CVE/Exploit Tracking** (Priority 9):
```
https://www.exploit-db.com/rss.xml|Exploit Database|9
https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml|NVD Recent CVEs|9
```

## Railway.app Deployment

### Deploy Steps

1. **Connect GitHub**
   - Go to [railway.app](https://railway.app)
   - "New Project" → "Deploy from GitHub"
   - Select your Kairos fork

2. **Configure**
   - Railway auto-detects Dockerfile
   - Add environment variables in "Variables" tab
   - Add volume:
     - Mount Path: `/app/data`
     - Size: 1GB

3. **Deploy**
   - Click "Deploy"
   - Get your URL: `https://yourapp.up.railway.app`

### Feed Management

Same as Render - use Shell access or API.

## Fly.io Deployment

### Prerequisites

Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

### Deploy Steps

1. **Launch App**
   ```bash
   cd kairos
   flyctl launch
   ```
   - Follow prompts
   - Choose region
   - Don't deploy yet

2. **Create Volume**
   ```bash
   flyctl volumes create kairos_data --size 1
   ```

3. **Update fly.toml**
   Add mount configuration:
   ```toml
   [mounts]
     source = "kairos_data"
     destination = "/app/data"
   ```

4. **Set Secrets**
   ```bash
   flyctl secrets set AUTH_TOKEN=$(openssl rand -hex 32)
   flyctl secrets set WEBHOOK_URL=your_webhook_url
   ```

5. **Deploy**
   ```bash
   flyctl deploy
   ```

6. **Get URL**
   ```bash
   flyctl status
   ```

### Feed Management

SSH into instance:
```bash
flyctl ssh console
nano /app/feeds.txt
```

## Managing Your Deployed Instance

### Health Monitoring

Check if your instance is running:
```bash
curl https://your-service.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": true,
  "pending_items": 42
}
```

### View Metrics

```bash
curl https://your-service.onrender.com/api/metrics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Shows:
- Pending items count
- Items by status
- Active feeds
- Next scheduled tasks

### Manual Feed Refresh

Force immediate feed refresh:
```bash
curl -X POST https://your-service.onrender.com/api/feeds/refresh \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Generate Digest On-Demand

```bash
curl -X POST https://your-service.onrender.com/api/digest/generate \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Download latest digest:
```bash
curl https://your-service.onrender.com/api/digest/latest \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o digest.md
```

## Troubleshooting

### Service Won't Start

1. Check logs in platform dashboard
2. Common issues:
   - Missing environment variables
   - Port configuration (should be 8083)
   - Volume mount path incorrect

### No Items Showing Up

1. Check feeds are configured:
   ```bash
   curl https://your-service.onrender.com/api/feeds \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

2. Manually trigger refresh:
   ```bash
   curl -X POST https://your-service.onrender.com/api/feeds/refresh \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. Check logs for feed fetch errors

### Webhook Not Working

1. Verify `WEBHOOK_URL` is set correctly
2. Test webhook URL independently (send test POST)
3. Check logs for retry attempts
4. Webhooks retry 3 times with exponential backoff

### Free Tier Cold Starts (Render)

- Service sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds
- This is normal for free tier
- Upgrade to paid tier for always-on service

## Performance Tips

### Feed Refresh Interval

Default: 5 minutes. Adjust in environment:
```
FEED_REFRESH_MINUTES=10
```

Lower = more API calls but fresher data
Higher = fewer resources but older data

### Feed Limits

Control items per feed:
```
MAX_ITEMS_PER_FEED=50
```

Lower value = less database growth
Higher value = more history

### Parallel Workers

Control concurrent feed fetches:
```
FEED_PARALLEL_WORKERS=5
```

Increase for faster fetching (if platform allows)
Decrease if hitting rate limits

## Security Best Practices

1. **Always set AUTH_TOKEN** in production
   ```bash
   openssl rand -hex 32
   ```

2. **Use HTTPS** - All platforms provide this automatically

3. **Rotate tokens** periodically via environment variables

4. **Don't commit** `.env` file to git (already in `.gitignore`)

5. **Monitor logs** for unauthorized access attempts

6. **Keep dependencies updated** - rebuild regularly

## Cost Estimates

### Render.com Free Tier
- **Cost**: $0/month
- **Limits**: Sleeps after 15 min inactivity, 750 hours/month
- **Storage**: ⚠️ **Ephemeral only** (data wiped on restart)
- **Best for**: Demos, testing only (NOT for persistent use)

### Render.com Starter Tier
- **Cost**: $7/month
- **Limits**: Always-on, no sleep
- **Storage**: Persistent disk (1GB+ available)
- **Best for**: Production use with data persistence

### Railway.app
- **Cost**: $0-$5/month (free credits)
- **Limits**: ~$5/month usage typically free
- **Best for**: Always-on personal instances

### Fly.io Free Tier
- **Cost**: $0/month
- **Limits**: 3 shared VMs, 3GB storage
- **Best for**: Multiple small apps

### Paid Tiers (if scaling)
- Render: $7/month (always-on)
- Railway: Pay-as-you-go (~$5-10/month)
- Fly.io: ~$5-10/month for production

## Backup & Recovery

### Export Database

On Render (via Shell):
```bash
cp /app/data/triage.db /tmp/backup.db
# Download via Render dashboard file browser
```

### Export Digests

All digests stored in `/app/data/digests/` on Render deployments.

Download via API:
```bash
curl https://your-service.onrender.com/api/digest/latest \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o latest-digest.md
```

### Restore from Backup

1. Stop service
2. Upload backup database via Shell
3. Copy to `/app/data/triage.db`
4. Restart service

## Support

- **Issues**: GitHub Issues
- **Docs**: README.md
- **Platform Support**:
  - Render: [render.com/docs](https://render.com/docs)
  - Railway: [docs.railway.app](https://docs.railway.app)
  - Fly.io: [fly.io/docs](https://fly.io/docs)
