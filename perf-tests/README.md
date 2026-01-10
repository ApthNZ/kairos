# Kairos Performance Testing

Optional performance testing container for measuring Kairos application performance.

## What It Tests

- **Page Load Times**: Login page, main page, admin page
- **API Response Times**: Health endpoint, feeds list, items list, authentication
- **UI Action Response Times**: Button clicks, navigation, triage actions
- **Concurrent Load**: Multiple simultaneous requests

## Quick Start

### Option 1: Run Against Existing Kairos Instance

```bash
cd perf-tests

# Set your Kairos URL
export KAIROS_URL=http://localhost:8000

# Build and run tests
docker-compose --profile testing up --build
```

### Option 2: Run Locally (Without Docker)

```bash
cd perf-tests

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run tests
KAIROS_URL=http://localhost:8000 pytest test_performance.py -v
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KAIROS_URL` | `http://localhost:8000` | Target Kairos instance URL |
| `TEST_USERNAME` | `perftest` | Username for authenticated tests |
| `TEST_PASSWORD` | `perftest123` | Password for authenticated tests |
| `PERF_ITERATIONS` | `5` | Number of iterations per test |

## Performance Thresholds

Default thresholds (can be adjusted in `test_performance.py`):

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Page Load | 2000ms | Maximum time for full page load |
| API Response | 500ms | Maximum time for API endpoints |
| Action Response | 300ms | Maximum time for UI actions |

## Creating Test User

Before running authenticated tests, create a test user:

```bash
cd /path/to/kairos
python3 scripts/create_admin.py perftest perftest123 analyst
```

## Sample Output

```
test_performance.py::TestAPIPerformance::test_health_endpoint PASSED

GET /api/health: PASS
  Mean: 12.3ms, Median: 11.5ms, P95: 18.2ms
  Min: 8.1ms, Max: 25.4ms
  Threshold: 500ms

test_performance.py::TestPageLoadPerformance::test_main_page_load PASSED

Main page load: PASS
  Mean: 450.2ms, Median: 425.8ms, P95: 680.5ms
  Min: 320.1ms, Max: 850.3ms
  Threshold: 2000ms
```

## Running in CI/CD

Example GitHub Actions workflow:

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
  workflow_dispatch:

jobs:
  perf-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start Kairos
        run: docker-compose up -d kairos

      - name: Wait for Kairos
        run: sleep 10

      - name: Run Performance Tests
        run: |
          cd perf-tests
          docker-compose --profile testing up --exit-code-from perf-tests

      - name: Upload Reports
        uses: actions/upload-artifact@v4
        with:
          name: perf-reports
          path: perf-tests/reports/
```

## Troubleshooting

### Connection Refused

If tests can't connect to Kairos:
- Check `KAIROS_URL` is correct
- Ensure Kairos is running and accessible
- For Docker, use `host.docker.internal` instead of `localhost`

### Playwright Browser Issues

```bash
# Install browser dependencies
playwright install-deps chromium
```

### Slow Test Runs

Reduce iterations for faster feedback:
```bash
PERF_ITERATIONS=2 pytest test_performance.py -v
```

## License

Part of the Kairos project. See main LICENSE file.
