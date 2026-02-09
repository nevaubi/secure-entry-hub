"""
Modal Application for Agentic Excel Processing

This application processes financial Excel files by:
1. Downloading files from external Supabase storage
2. Using Claude to understand file schemas dynamically
3. Browsing StockAnalysis.com to gather financial data
4. Updating Excel files with verified data
5. Uploading files back to storage

Deploy with: modal deploy app.py
Test with: modal run app.py::test_single_ticker --ticker AAPL
"""

import modal
import os
from datetime import datetime

# Define the Modal app
app = modal.App("excel-agent")

# Create image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "anthropic>=0.40.0",
        "openpyxl>=3.1.2",
        "playwright>=1.40.0",
        "httpx>=0.27.0",
        "fastapi[standard]>=0.115.0",
    )
    .run_commands("playwright install chromium", "playwright install-deps chromium")
)

# Secrets for API access
secrets = [
    modal.Secret.from_name("anthropic-secret"),  # ANTHROPIC_API_KEY
    modal.Secret.from_name("stockanalysis-secret"),  # STOCKANALYSIS_USERNAME, STOCKANALYSIS_PASSWORD
    modal.Secret.from_name("supabase-external-secret"),  # EXTERNAL_SUPABASE_URL, EXTERNAL_SUPABASE_SERVICE_KEY
    modal.Secret.from_name("modal-webhook-secret"),  # MODAL_WEBHOOK_SECRET
    modal.Secret.from_name("perplexity-secret"),  # PERPLEXITY_API_KEY
]


@app.function(image=image, secrets=secrets, timeout=600)
def process_ticker(
    ticker: str,
    report_date: str,
    timing: str,
    callback_url: str | None = None,
) -> dict:
    """
    Process a single ticker's Excel files.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        report_date: Earnings report date (YYYY-MM-DD)
        timing: Either "premarket" or "afterhours"
        callback_url: URL to POST results back to Lovable

    Returns:
        dict with status, files_updated count, and any errors
    """
    import httpx
    from agent.orchestrator import run_agent

    print(f"Processing ticker: {ticker} for {report_date} ({timing})")

    try:
        result = run_agent(ticker, report_date, timing)

        # Report back to Lovable if callback URL provided
        if callback_url:
            webhook_secret = os.environ.get("MODAL_WEBHOOK_SECRET", "")
            httpx.post(
                callback_url,
                json={
                    "ticker": ticker,
                    "report_date": report_date,
                    "timing": timing,
                    "status": "completed" if result["success"] else "failed",
                    "files_updated": result.get("files_updated", 0),
                    "data_sources_used": result.get("data_sources", []),
                    "error_message": result.get("error"),
                },
                headers={"Authorization": f"Bearer {webhook_secret}"},
                timeout=30,
            )

        return result

    except Exception as e:
        error_msg = str(e)
        print(f"Error processing {ticker}: {error_msg}")

        # Report failure back to Lovable
        if callback_url:
            webhook_secret = os.environ.get("MODAL_WEBHOOK_SECRET", "")
            try:
                httpx.post(
                    callback_url,
                    json={
                        "ticker": ticker,
                        "report_date": report_date,
                        "timing": timing,
                        "status": "failed",
                        "error_message": error_msg,
                    },
                    headers={"Authorization": f"Bearer {webhook_secret}"},
                    timeout=30,
                )
            except Exception:
                pass  # Don't fail on callback error

        return {"success": False, "error": error_msg}


@app.function(image=image, secrets=secrets, timeout=60)
@modal.fastapi_endpoint(method="POST")
def webhook(data: dict) -> dict:
    """
    Webhook endpoint called by Lovable's trigger-excel-agent function.

    Expects payload:
    {
        "tickers": [
            {"ticker": "AAPL", "report_date": "2024-01-15", "timing": "afterhours"},
            ...
        ],
        "callback_url": "https://..."
    }
    """
    import os
    from fastapi import Request, HTTPException

    # Note: In production, verify the webhook secret from Authorization header
    # For now, we trust the caller

    tickers = data.get("tickers", [])
    callback_url = data.get("callback_url")

    if not tickers:
        return {"success": False, "error": "No tickers provided"}

    print(f"Received webhook with {len(tickers)} tickers")

    # Spawn parallel processing for all tickers
    # Using .map() for efficient parallel execution
    futures = []
    for t in tickers:
        futures.append(
            process_ticker.spawn(
                ticker=t["ticker"],
                report_date=t["report_date"],
                timing=t["timing"],
                callback_url=callback_url,
            )
        )

    return {
        "success": True,
        "message": f"Spawned processing for {len(tickers)} tickers",
        "tickers": [t["ticker"] for t in tickers],
    }


@app.local_entrypoint()
def test_single_ticker(ticker: str = "AAPL"):
    """Test processing a single ticker locally."""
    result = process_ticker.remote(
        ticker=ticker,
        report_date=datetime.now().strftime("%Y-%m-%d"),
        timing="afterhours",
        callback_url=None,
    )
    print(f"Result: {result}")
