"""
Browser automation for StockAnalysis.com.

Uses Playwright to login and extract financial data via screenshots + Gemini vision.
"""

import os
import time
from typing import Any
from playwright.sync_api import sync_playwright, Page, Browser


class StockAnalysisBrowser:
    """Browser automation for StockAnalysis.com with persistent session."""

    def __init__(self):
        self.username = os.environ.get("STOCKANALYSIS_USERNAME")
        self.password = os.environ.get("STOCKANALYSIS_PASSWORD")

        if not self.username or not self.password:
            raise ValueError("StockAnalysis credentials not configured")

        self.playwright = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.logged_in = False

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page(viewport={"width": 1920, "height": 1080})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self) -> bool:
        """
        Login to StockAnalysis.com using exact UI selectors.
        Retries up to 2 times on failure. Saves debug screenshot on failure.

        Returns:
            True if login successful, False otherwise
        """
        if self.logged_in:
            return True

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Login attempt {attempt}/{max_attempts}...")
                self.page.goto("https://stockanalysis.com/login/", timeout=30000)
                self.page.wait_for_load_state("networkidle", timeout=15000)

                # Wait for email input by id
                self.page.wait_for_selector("input#email", timeout=10000)

                # Fill credentials using exact id selectors
                self.page.fill("input#email", self.username)
                self.page.fill("input#password", self.password)

                # Click the Log In button (no type="submit", use role/text)
                login_btn = self.page.get_by_role("button", name="Log In")
                login_btn.click()

                # Wait for navigation away from /login/
                self.page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)  # Extra settle time

                current_url = self.page.url
                print(f"Post-login URL: {current_url}")

                if "login" not in current_url.lower():
                    self.logged_in = True
                    print("Login successful")
                    return True
                else:
                    print(f"Still on login page after attempt {attempt}")
                    # Save debug screenshot
                    self.page.screenshot(path=f"/tmp/login_debug_attempt_{attempt}.png", full_page=True)

            except Exception as e:
                print(f"Login error on attempt {attempt}: {e}")
                try:
                    self.page.screenshot(path=f"/tmp/login_error_attempt_{attempt}.png", full_page=True)
                except Exception:
                    pass

        print("All login attempts failed")
        return False

    def _select_raw_units(self):
        """Click the number-units dropdown and select 'Raw' to show full values."""
        try:
            dropdown = self.page.locator('button[title="Change number units"]')
            dropdown.wait_for(timeout=5000)
            dropdown.click()
            time.sleep(0.5)

            raw_btn = self.page.locator('button.active:has-text("Raw"), button:has-text("Raw")')
            raw_btn.first.click()
            time.sleep(0.5)

            print("Selected 'Raw' number units")
        except Exception as e:
            print(f"Warning: Could not select Raw units: {e}")

    def _build_url(self, ticker: str, statement_type: str, period: str, data_type: str) -> str:
        """
        Build the correct StockAnalysis.com URL for a financial statement.

        Args:
            ticker: Stock ticker (e.g., "PLTR")
            statement_type: One of "income", "balance", "cashflow"
            period: "annual" or "quarterly"
            data_type: "standardized" or "as-reported"

        Returns:
            The full URL string
        """
        base = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials"

        # Income statement has NO extra path segment
        path_map = {
            "income": "",
            "balance": "/balance-sheet",
            "cashflow": "/cash-flow-statement",
        }
        path = path_map.get(statement_type, "")

        params = []
        if period == "quarterly":
            params.append("p=quarterly")
        if data_type == "as-reported":
            params.append("type=as-reported")

        url = f"{base}{path}/"
        if params:
            url += "?" + "&".join(params)

        return url

    def navigate_to_financials(self, ticker: str, statement_type: str, period: str, data_type: str) -> dict[str, Any]:
        """
        Navigate to a financial statement page and take a full-page screenshot.

        Args:
            ticker: Stock ticker
            statement_type: "income", "balance", or "cashflow"
            period: "annual" or "quarterly"
            data_type: "standardized" or "as-reported"

        Returns:
            Dict with success status, URL visited, and screenshot bytes
        """
        if not self.login():
            return {"success": False, "error": "Failed to login"}

        url = self._build_url(ticker, statement_type, period, data_type)

        try:
            print(f"Navigating to: {url}")
            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state("networkidle", timeout=15000)

            # Wait for the financial table to appear
            try:
                self.page.wait_for_selector("table", timeout=10000)
            except Exception:
                print("Warning: table selector not found, proceeding with screenshot anyway")

            time.sleep(1)  # Let any lazy-loaded content settle

            # Select "Raw" number format before taking screenshot
            self._select_raw_units()

            # Take full-page screenshot
            screenshot_bytes = self.screenshot_full_page()

            # Save debug copy
            debug_name = f"{ticker}_{statement_type}_{period}_{data_type}".replace("-", "_")
            self.page.screenshot(path=f"/tmp/{debug_name}.png", full_page=True)

            return {
                "success": True,
                "url": url,
                "ticker": ticker,
                "statement_type": statement_type,
                "period": period,
                "data_type": data_type,
                "screenshot_bytes": screenshot_bytes,
                "page_title": self.page.title(),
            }

        except Exception as e:
            print(f"Error navigating to {url}: {e}")
            try:
                self.page.screenshot(path=f"/tmp/nav_error_{ticker}_{statement_type}.png", full_page=True)
            except Exception:
                pass
            return {
                "success": False,
                "error": str(e),
                "url": url,
            }

    def screenshot_full_page(self) -> bytes:
        """Take a full-page screenshot and return the bytes."""
        return self.page.screenshot(full_page=True, type="png")
