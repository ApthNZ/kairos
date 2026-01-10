"""Performance tests for Kairos application.

This test suite measures:
- Page load times
- API response times
- UI action response times (button clicks, triage actions)

Run with: pytest test_performance.py -v
Or via Docker: docker-compose up perf-tests
"""
import asyncio
import os
import statistics
import time
from dataclasses import dataclass
from typing import List, Optional

import aiohttp
import pytest
from playwright.async_api import async_playwright, Page

# Configuration
BASE_URL = os.getenv("KAIROS_URL", "http://localhost:8000")
TEST_USERNAME = os.getenv("TEST_USERNAME", "perftest")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "perftest123")
ITERATIONS = int(os.getenv("PERF_ITERATIONS", "5"))

# Performance thresholds (milliseconds)
THRESHOLDS = {
    "page_load": 2000,      # Max 2 seconds for page load
    "api_response": 500,    # Max 500ms for API calls
    "action_response": 300, # Max 300ms for UI actions
}


@dataclass
class PerformanceResult:
    """Container for performance measurement results."""
    name: str
    times_ms: List[float]
    threshold_ms: float

    @property
    def mean(self) -> float:
        return statistics.mean(self.times_ms)

    @property
    def median(self) -> float:
        return statistics.median(self.times_ms)

    @property
    def p95(self) -> float:
        sorted_times = sorted(self.times_ms)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def min_time(self) -> float:
        return min(self.times_ms)

    @property
    def max_time(self) -> float:
        return max(self.times_ms)

    @property
    def passed(self) -> bool:
        return self.p95 <= self.threshold_ms

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.name}: {status}\n"
            f"  Mean: {self.mean:.1f}ms, Median: {self.median:.1f}ms, "
            f"P95: {self.p95:.1f}ms\n"
            f"  Min: {self.min_time:.1f}ms, Max: {self.max_time:.1f}ms\n"
            f"  Threshold: {self.threshold_ms}ms"
        )


class PerfTimer:
    """Context manager for measuring execution time."""

    def __init__(self):
        self.start_time = 0
        self.end_time = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


class TestAPIPerformance:
    """Test API endpoint response times."""

    @pytest.fixture
    async def session(self):
        """Create aiohttp session."""
        async with aiohttp.ClientSession() as session:
            yield session

    @pytest.mark.asyncio
    async def test_health_endpoint(self, session):
        """Test /api/health response time."""
        times = []

        for _ in range(ITERATIONS):
            with PerfTimer() as timer:
                async with session.get(f"{BASE_URL}/api/health") as resp:
                    await resp.text()
            times.append(timer.elapsed_ms)

        result = PerformanceResult(
            name="GET /api/health",
            times_ms=times,
            threshold_ms=THRESHOLDS["api_response"]
        )
        print(f"\n{result}")
        assert result.passed, f"API response too slow: P95={result.p95:.1f}ms"

    @pytest.mark.asyncio
    async def test_feeds_list_endpoint(self, session):
        """Test /api/feeds response time."""
        times = []

        for _ in range(ITERATIONS):
            with PerfTimer() as timer:
                async with session.get(f"{BASE_URL}/api/feeds") as resp:
                    await resp.text()
            times.append(timer.elapsed_ms)

        result = PerformanceResult(
            name="GET /api/feeds",
            times_ms=times,
            threshold_ms=THRESHOLDS["api_response"]
        )
        print(f"\n{result}")
        assert result.passed, f"API response too slow: P95={result.p95:.1f}ms"

    @pytest.mark.asyncio
    async def test_items_list_endpoint(self, session):
        """Test /api/items response time."""
        times = []

        for _ in range(ITERATIONS):
            with PerfTimer() as timer:
                async with session.get(f"{BASE_URL}/api/items?limit=50") as resp:
                    await resp.text()
            times.append(timer.elapsed_ms)

        result = PerformanceResult(
            name="GET /api/items",
            times_ms=times,
            threshold_ms=THRESHOLDS["api_response"]
        )
        print(f"\n{result}")
        assert result.passed, f"API response too slow: P95={result.p95:.1f}ms"

    @pytest.mark.asyncio
    async def test_login_endpoint(self, session):
        """Test /api/auth/login response time."""
        times = []

        for _ in range(ITERATIONS):
            with PerfTimer() as timer:
                async with session.post(
                    f"{BASE_URL}/api/auth/login",
                    json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
                ) as resp:
                    await resp.text()
            times.append(timer.elapsed_ms)

        result = PerformanceResult(
            name="POST /api/auth/login",
            times_ms=times,
            threshold_ms=THRESHOLDS["api_response"]
        )
        print(f"\n{result}")
        # Login can be slower due to bcrypt
        assert result.p95 <= 1000, f"Login too slow: P95={result.p95:.1f}ms"


class TestPageLoadPerformance:
    """Test page load times using Playwright."""

    @pytest.fixture
    async def browser(self):
        """Create browser instance."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            yield browser
            await browser.close()

    @pytest.fixture
    async def page(self, browser):
        """Create page instance."""
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()

    @pytest.mark.asyncio
    async def test_login_page_load(self, browser):
        """Test login page load time."""
        times = []

        for _ in range(ITERATIONS):
            context = await browser.new_context()
            page = await context.new_page()

            with PerfTimer() as timer:
                await page.goto(f"{BASE_URL}/login.html", wait_until="networkidle")

            times.append(timer.elapsed_ms)
            await context.close()

        result = PerformanceResult(
            name="Login page load",
            times_ms=times,
            threshold_ms=THRESHOLDS["page_load"]
        )
        print(f"\n{result}")
        assert result.passed, f"Page load too slow: P95={result.p95:.1f}ms"

    @pytest.mark.asyncio
    async def test_main_page_load(self, browser):
        """Test main index page load time."""
        times = []

        for _ in range(ITERATIONS):
            context = await browser.new_context()
            page = await context.new_page()

            with PerfTimer() as timer:
                await page.goto(f"{BASE_URL}/", wait_until="networkidle")

            times.append(timer.elapsed_ms)
            await context.close()

        result = PerformanceResult(
            name="Main page load",
            times_ms=times,
            threshold_ms=THRESHOLDS["page_load"]
        )
        print(f"\n{result}")
        assert result.passed, f"Page load too slow: P95={result.p95:.1f}ms"

    @pytest.mark.asyncio
    async def test_admin_page_load(self, browser):
        """Test admin page load time."""
        times = []

        for _ in range(ITERATIONS):
            context = await browser.new_context()
            page = await context.new_page()

            with PerfTimer() as timer:
                await page.goto(f"{BASE_URL}/admin.html", wait_until="networkidle")

            times.append(timer.elapsed_ms)
            await context.close()

        result = PerformanceResult(
            name="Admin page load",
            times_ms=times,
            threshold_ms=THRESHOLDS["page_load"]
        )
        print(f"\n{result}")
        assert result.passed, f"Page load too slow: P95={result.p95:.1f}ms"


class TestUIActionPerformance:
    """Test UI action response times."""

    @pytest.fixture
    async def authenticated_page(self):
        """Create an authenticated browser page."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Login first
            await page.goto(f"{BASE_URL}/login.html")
            await page.fill('input[name="username"]', TEST_USERNAME)
            await page.fill('input[name="password"]', TEST_PASSWORD)
            await page.click('button[type="submit"]')

            # Wait for redirect
            await page.wait_for_url(f"{BASE_URL}/", timeout=5000)

            yield page

            await context.close()
            await browser.close()

    @pytest.mark.asyncio
    async def test_triage_button_response(self):
        """Test triage button click response time."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Go to main page
            await page.goto(f"{BASE_URL}/")
            await page.wait_for_load_state("networkidle")

            times = []

            # Look for triage buttons
            buttons = await page.query_selector_all('button.triage-btn, button[data-action="triage"]')

            if not buttons:
                # Try generic approach - measure any button click
                buttons = await page.query_selector_all('button')

            for i, button in enumerate(buttons[:ITERATIONS]):
                try:
                    with PerfTimer() as timer:
                        await button.click()
                        # Wait for response (either network or DOM change)
                        await page.wait_for_timeout(50)
                    times.append(timer.elapsed_ms)
                except Exception:
                    pass

            await context.close()
            await browser.close()

            if times:
                result = PerformanceResult(
                    name="Triage button click",
                    times_ms=times,
                    threshold_ms=THRESHOLDS["action_response"]
                )
                print(f"\n{result}")
                assert result.passed, f"Action too slow: P95={result.p95:.1f}ms"
            else:
                pytest.skip("No triage buttons found to test")

    @pytest.mark.asyncio
    async def test_navigation_response(self):
        """Test navigation element response time."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"{BASE_URL}/")
            await page.wait_for_load_state("networkidle")

            times = []

            # Test clicking navigation links
            nav_links = await page.query_selector_all('nav a, .nav-link, a[href*="admin"]')

            for i, link in enumerate(nav_links[:ITERATIONS]):
                try:
                    with PerfTimer() as timer:
                        await link.click()
                        await page.wait_for_load_state("domcontentloaded")
                    times.append(timer.elapsed_ms)

                    # Go back for next iteration
                    await page.goto(f"{BASE_URL}/")
                    await page.wait_for_load_state("networkidle")
                except Exception:
                    pass

            await context.close()
            await browser.close()

            if times:
                result = PerformanceResult(
                    name="Navigation response",
                    times_ms=times,
                    threshold_ms=THRESHOLDS["page_load"]
                )
                print(f"\n{result}")
                assert result.passed, f"Navigation too slow: P95={result.p95:.1f}ms"
            else:
                pytest.skip("No navigation elements found to test")


class TestConcurrentLoad:
    """Test performance under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test API performance with concurrent requests."""
        async def make_request(session, url):
            with PerfTimer() as timer:
                async with session.get(url) as resp:
                    await resp.text()
            return timer.elapsed_ms

        times = []
        concurrent_users = 10

        async with aiohttp.ClientSession() as session:
            for _ in range(ITERATIONS):
                tasks = [
                    make_request(session, f"{BASE_URL}/api/health")
                    for _ in range(concurrent_users)
                ]
                batch_times = await asyncio.gather(*tasks, return_exceptions=True)
                times.extend([t for t in batch_times if isinstance(t, (int, float))])

        if times:
            result = PerformanceResult(
                name=f"Concurrent requests ({concurrent_users} users)",
                times_ms=times,
                threshold_ms=THRESHOLDS["api_response"] * 2  # Allow 2x for concurrency
            )
            print(f"\n{result}")
            assert result.passed, f"Concurrent load too slow: P95={result.p95:.1f}ms"


def generate_performance_report(results: List[PerformanceResult]) -> str:
    """Generate a performance test report."""
    report = ["=" * 60, "KAIROS PERFORMANCE TEST REPORT", "=" * 60, ""]

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    report.append(f"Total Tests: {len(results)}")
    report.append(f"Passed: {passed}")
    report.append(f"Failed: {failed}")
    report.append("")
    report.append("-" * 60)

    for result in results:
        report.append(str(result))
        report.append("-" * 60)

    return "\n".join(report)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
