"""
Browser automation for StockAnalysis.com.

Uses Playwright to login and extract financial data.
"""

import os
from typing import Any
from playwright.sync_api import sync_playwright, Page, Browser


class StockAnalysisBrowser:
    """Browser automation for StockAnalysis.com."""

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
        self.page = self.browser.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self) -> bool:
        """
        Login to StockAnalysis.com.

        Returns:
            True if login successful, False otherwise
        """
        if self.logged_in:
            return True

        try:
            print("Logging in to StockAnalysis.com...")
            self.page.goto("https://stockanalysis.com/login/", timeout=30000)

            # Wait for login form
            self.page.wait_for_selector('input[type="email"]', timeout=10000)

            # Fill credentials
            self.page.fill('input[type="email"]', self.username)
            self.page.fill('input[type="password"]', self.password)

            # Submit
            self.page.click('button[type="submit"]')

            # Wait for redirect or dashboard
            self.page.wait_for_load_state("networkidle", timeout=15000)

            # Check if logged in (look for user menu or dashboard element)
            if "login" not in self.page.url.lower():
                self.logged_in = True
                print("Login successful")
                return True
            else:
                print("Login may have failed - still on login page")
                return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def extract_financial_table(self, ticker: str, statement_type: str, period: str) -> dict[str, Any]:
        """
        Extract a financial statement table.

        Args:
            ticker: Stock ticker symbol
            statement_type: One of "income-statement", "balance-sheet", "cash-flow-statement"
            period: Either "annual" or "quarterly"

        Returns:
            Dict with column headers and row data
        """
        url = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials/{statement_type}/?p={period}"

        try:
            print(f"Extracting {statement_type} ({period}) for {ticker}...")
            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state("networkidle", timeout=15000)

            # Wait for the table to load
            self.page.wait_for_selector("table", timeout=10000)

            # Extract table data using JavaScript
            table_data = self.page.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return null;

                    const headers = [];
                    const headerCells = table.querySelectorAll('thead th');
                    headerCells.forEach(th => headers.push(th.textContent?.trim() || ''));

                    const rows = [];
                    const bodyRows = table.querySelectorAll('tbody tr');
                    bodyRows.forEach(tr => {
                        const cells = tr.querySelectorAll('td');
                        const rowData = {};
                        cells.forEach((td, i) => {
                            const header = headers[i] || `col_${i}`;
                            rowData[header] = td.textContent?.trim() || '';
                        });
                        // Get the row label from first cell
                        const label = tr.querySelector('td')?.textContent?.trim() || '';
                        if (label) {
                            rowData['_label'] = label;
                            rows.push(rowData);
                        }
                    });

                    return { headers, rows };
                }
            """)

            if table_data:
                print(f"Extracted {len(table_data.get('rows', []))} rows")
                return {
                    "success": True,
                    "statement_type": statement_type,
                    "period": period,
                    "ticker": ticker,
                    **table_data,
                }
            else:
                return {
                    "success": False,
                    "error": "Could not find table",
                    "statement_type": statement_type,
                    "period": period,
                    "ticker": ticker,
                }

        except Exception as e:
            print(f"Error extracting {statement_type}: {e}")
            return {
                "success": False,
                "error": str(e),
                "statement_type": statement_type,
                "period": period,
                "ticker": ticker,
            }

    def extract_all_financials(self, ticker: str) -> dict[str, dict]:
        """
        Extract all financial statements for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with all extracted financial data
        """
        if not self.login():
            return {"error": "Failed to login to StockAnalysis.com"}

        results = {}

        statement_types = ["income-statement", "balance-sheet", "cash-flow-statement"]
        periods = ["annual", "quarterly"]

        for statement in statement_types:
            for period in periods:
                key = f"{statement}_{period}"
                results[key] = self.extract_financial_table(ticker, statement, period)

        return results


def extract_financials(ticker: str) -> dict[str, dict]:
    """
    Convenience function to extract all financials for a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with all extracted financial data
    """
    with StockAnalysisBrowser() as browser:
        return browser.extract_all_financials(ticker)
