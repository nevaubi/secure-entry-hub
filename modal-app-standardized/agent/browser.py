"""
Browser automation for StockAnalysis.com (Standardized mode).

Uses Playwright to login and extract financial data via screenshots + Gemini vision.
Handles Standardized + Raw + Fiscal.ai settings for all 4 statement types.
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

    def verify_logged_in(self) -> bool:
        """Verify the session is still logged in by checking the current page."""
        try:
            # Check URL is not a login page
            current_url = self.page.url
            if "login" in current_url.lower():
                return False
            # Look for common logged-in indicators (user menu, avatar, account link)
            logged_in_selectors = [
                'a[href="/pro/"]',
                'button[aria-label="User menu"]',
                'a[href="/my/account/"]',
                'nav a[href="/my/"]',
            ]
            for sel in logged_in_selectors:
                try:
                    if self.page.locator(sel).first.is_visible(timeout=2000):
                        return True
                except Exception:
                    continue
            # Fallback: if we're not on login page, assume logged in
            return "login" not in current_url.lower()
        except Exception:
            return False

    def login(self) -> bool:
        """Login to StockAnalysis.com with retry, backoff, and CAPTCHA detection."""
        if self.logged_in and self.verify_logged_in():
            return True
        # Reset flag in case session expired
        self.logged_in = False

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Exponential backoff between retries (skip on first attempt)
                if attempt > 1:
                    backoff = 2 ** attempt  # 4s, 8s
                    print(f"Waiting {backoff}s before retry...")
                    time.sleep(backoff)

                print(f"Login attempt {attempt}/{max_attempts}...")
                self.page.goto("https://stockanalysis.com/login/", timeout=30000)
                # Wait for the login form to appear instead of networkidle
                self.page.wait_for_selector("input#email", timeout=15000)
                time.sleep(1)

                # Check for CAPTCHA before attempting login
                captcha_selectors = [
                    'iframe[src*="captcha"]',
                    'iframe[src*="recaptcha"]',
                    '.g-recaptcha',
                    '#captcha',
                    'iframe[src*="hcaptcha"]',
                    'iframe[src*="challenge"]',
                ]
                for captcha_sel in captcha_selectors:
                    try:
                        if self.page.locator(captcha_sel).first.is_visible(timeout=1000):
                            print(f"⚠️  CAPTCHA detected ({captcha_sel}) — cannot proceed automatically")
                            self.page.screenshot(path=f"/tmp/login_captcha_attempt_{attempt}.png", full_page=True)
                            # Don't burn more retries on CAPTCHA
                            print("All login attempts failed (CAPTCHA)")
                            return False
                    except Exception:
                        continue

                self.page.fill("input#email", self.username)
                self.page.fill("input#password", self.password)
                login_btn = self.page.get_by_role("button", name="Log In")
                login_btn.click()

                # Wait for navigation away from login page (explicit element wait)
                try:
                    self.page.wait_for_url("**/!(login)**", timeout=15000)
                except Exception:
                    pass  # Fallback to URL check below

                time.sleep(2)

                # Verify login succeeded
                if self.verify_logged_in():
                    self.logged_in = True
                    print("Login successful")
                    return True
                else:
                    current_url = self.page.url
                    print(f"Still on login page after attempt {attempt} (URL: {current_url})")
                    self.page.screenshot(path=f"/tmp/login_debug_attempt_{attempt}.png", full_page=True)

            except Exception as e:
                print(f"Login error on attempt {attempt}: {e}")
                try:
                    self.page.screenshot(path=f"/tmp/login_error_attempt_{attempt}.png", full_page=True)
                except Exception:
                    pass

        print("All login attempts failed")
        return False

    def _click_standardized(self):
        """Click the 'Standardized' button to ensure standardized view."""
        try:
            std_btn = self.page.locator('button.rounded-l-md:has-text("Standardized")')
            std_btn.wait_for(timeout=5000)
            std_btn.click()
            time.sleep(0.5)
            print("Clicked 'Standardized' button")
        except Exception as e:
            print(f"Warning: Could not click Standardized button: {e}")

    def _select_raw_units(self):
        """Click the number-units dropdown and select 'Raw' to show full values."""
        try:
            # The dropdown button shows current unit (e.g. "Millions")
            dropdown = self.page.locator('button[title="Change number units"]')
            dropdown.wait_for(timeout=5000)
            dropdown.click()
            time.sleep(0.5)

            raw_btn = self.page.locator('button:has-text("Raw")')
            raw_btn.first.click()
            time.sleep(0.5)
            print("Selected 'Raw' number units")
        except Exception as e:
            print(f"Warning: Could not select Raw units: {e}")

    def _select_fiscal_ai(self):
        """Open Data Source dropdown and select 'Fiscal.ai'."""
        try:
            # Click the Data Source dropdown button
            ds_btn = self.page.locator('button:has-text("Data Source"), button:has-text("data source")')
            if ds_btn.count() == 0:
                # Try alternative: look for a button with "Data" text near source controls
                ds_btn = self.page.get_by_role("button", name="Data Source")
            ds_btn.first.wait_for(timeout=5000)
            ds_btn.first.click()
            time.sleep(0.5)

            fiscal_btn = self.page.locator('button:has-text("Fiscal.ai")')
            fiscal_btn.first.click()
            time.sleep(0.5)
            print("Selected 'Fiscal.ai' data source")
        except Exception as e:
            print(f"Warning: Could not select Fiscal.ai: {e}")

    def _apply_settings(self, is_ratios: bool = False):
        """Apply Standardized + Raw + Fiscal.ai settings after page navigation."""
        self._click_standardized()
        if not is_ratios:
            # Ratios page has no number-units dropdown
            self._select_raw_units()
        self._select_fiscal_ai()

    def _build_url(self, ticker: str, statement_type: str, period: str) -> str:
        """Build the StockAnalysis.com URL for a standardized financial statement."""
        base = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials"

        path_map = {
            "income": "",
            "balance": "/balance-sheet",
            "cashflow": "/cash-flow-statement",
            "ratios": "/ratios",
        }
        path = path_map.get(statement_type, "")

        url = f"{base}{path}/"
        if period == "quarterly":
            url += "?p=quarterly"

        return url

    def navigate_to_financials(
        self, ticker: str, statement_type: str, period: str
    ) -> dict[str, Any]:
        """
        Navigate to a standardized financial statement page and take a screenshot.

        Args:
            ticker: Stock ticker
            statement_type: "income", "balance", "cashflow", or "ratios"
            period: "annual" or "quarterly"

        Returns:
            Dict with success status, URL visited, and screenshot bytes
        """
        # Re-verify session is still valid before navigating
        if self.logged_in and not self.verify_logged_in():
            print("Session expired, re-logging in...")
            self.logged_in = False

        if not self.login():
            return {"success": False, "error": "Failed to login"}

        url = self._build_url(ticker, statement_type, period)
        is_ratios = statement_type == "ratios"

        try:
            print(f"Navigating to: {url}")
            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state("networkidle", timeout=15000)

            try:
                self.page.wait_for_selector("table", timeout=10000)
            except Exception:
                print("Warning: table selector not found, proceeding anyway")

            time.sleep(1)

            # Apply Standardized + Raw + Fiscal.ai settings
            self._apply_settings(is_ratios=is_ratios)

            time.sleep(1)  # Let data reload after settings change

            # Take full-page screenshot
            screenshot_bytes = self.screenshot_full_page()

            # Save debug copy
            debug_name = f"{ticker}_{statement_type}_{period}_standardized"
            self.page.screenshot(path=f"/tmp/{debug_name}.png", full_page=True)

            return {
                "success": True,
                "url": url,
                "ticker": ticker,
                "statement_type": statement_type,
                "period": period,
                "data_type": "standardized",
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
