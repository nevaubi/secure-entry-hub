"""
Agent orchestrator using Anthropic Claude.

Coordinates the agentic workflow:
1. Analyze Excel schemas
2. Browse StockAnalysis.com (persistent browser session)
3. Extract data via Gemini vision
4. Track findings in scratchpad
5. Update files with dual-source validated data
"""

import os
import json
import time
import base64
import tempfile
from pathlib import Path
from typing import Any
import anthropic
import httpx

from .storage import StorageClient
from .schema import analyze_all_files, format_schema_for_llm
from .browser import StockAnalysisBrowser
from .updater import ExcelUpdater


# Tools available to the agent
TOOLS = [
    {
        "name": "analyze_excel",
        "description": "Analyze the structure and contents of an Excel file. Returns sheet names, headers, sample data, and empty cells that might need to be filled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bucket_name": {
                    "type": "string",
                    "description": "The bucket/file identifier (e.g., 'financials-annual-income')"
                }
            },
            "required": ["bucket_name"]
        }
    },
    {
        "name": "browse_stockanalysis",
        "description": "Navigate to a specific financial statement page on StockAnalysis.com and take a full-page screenshot. The browser session persists across calls (login only happens once). After calling this, use extract_page_with_vision to read the data from the screenshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "statement_type": {
                    "type": "string",
                    "enum": ["income", "balance", "cashflow"],
                    "description": "Type of financial statement"
                },
                "period": {
                    "type": "string",
                    "enum": ["annual", "quarterly"],
                    "description": "Annual or quarterly data"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["standardized", "as-reported"],
                    "description": "Whether to view standardized or as-reported data"
                }
            },
            "required": ["statement_type", "period", "data_type"]
        }
    },
    {
        "name": "extract_page_with_vision",
        "description": "Send the latest page screenshot to Gemini Flash to extract financial data as structured markdown. Call this after browse_stockanalysis to read the table data from the screenshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "What to extract from the page, e.g. 'Extract the full financial table with all rows and columns as a markdown table. Include all numeric values exactly as shown.'"
                }
            },
            "required": ["instruction"]
        }
    },
    {
        "name": "note_finding",
        "description": "Record a finding or intermediate result to your scratchpad. Use this to track what data you've gathered, what cells are empty, what values you plan to insert, and validation results. Your notes persist across iterations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["data_gathered", "empty_cells", "validation", "decision", "error"],
                    "description": "Category of the note"
                },
                "content": {
                    "type": "string",
                    "description": "The finding or observation to record"
                }
            },
            "required": ["category", "content"]
        }
    },
    {
        "name": "update_excel_cell",
        "description": "Update a specific cell in an Excel file with a new value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bucket_name": {
                    "type": "string",
                    "description": "The bucket/file identifier (e.g., 'financials-annual-income')"
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the Excel sheet"
                },
                "cell_ref": {
                    "type": "string",
                    "description": "Cell reference like 'A1' or 'B5'"
                },
                "value": {
                    "type": ["string", "number"],
                    "description": "The value to set"
                }
            },
            "required": ["bucket_name", "sheet_name", "cell_ref", "value"]
        }
    },
    {
        "name": "save_all_files",
        "description": "Save all modified Excel files and upload them back to storage. Call this when you're done making updates.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for financial data using Perplexity AI. Use this alongside browse_stockanalysis to cross-reference and validate values before inserting them. Returns AI-generated answers grounded in real web sources with citations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Specific financial query, e.g. 'Apple Inc Q4 2025 quarterly revenue net income total assets'"
                }
            },
            "required": ["query"]
        }
    }
]


SYSTEM_PROMPT = """You are a financial data agent. Your task is to update Excel files containing financial statements with accurate, up-to-date data.

WORKFLOW:
1. Use analyze_excel to understand the structure of each file you need to update
2. Use note_finding to record which cells are empty and need data
3. Use browse_stockanalysis to navigate to the correct financial page, then extract_page_with_vision to read the data
4. Use web_search to cross-reference values from a second source
5. Use note_finding to record gathered data and validation results
6. Use update_excel_cell to fill in ONLY empty cells with dual-source verified values
7. Call save_all_files when done

TOOL USAGE TIPS:
- browse_stockanalysis navigates and screenshots the page. It does NOT return table data.
- After browse_stockanalysis, ALWAYS call extract_page_with_vision to actually read the financial data from the screenshot.
- Use note_finding liberally to track your progress, data gathered, and decisions made.
- Your notes persist across iterations so you can refer back to them.

URL MAPPING (handled automatically by browse_stockanalysis):
- statement_type "income" + period "quarterly" + data_type "as-reported" => /financials/?p=quarterly&type=as-reported
- statement_type "balance" + period "annual" + data_type "standardized" => /financials/balance-sheet/
- etc.

DUAL-SOURCE VALIDATION:
- For every data point, gather it from BOTH StockAnalysis (via vision) AND Perplexity web_search
- If both sources agree, use the value
- If they disagree, investigate further or leave the cell empty
- Record your validation reasoning with note_finding

CRITICAL RULES:
- NEVER modify cells that already contain values — ONLY fill empty cells
- All numeric values must be fully written out (e.g., 394328000000 not 394.33B)
- If you cannot confirm a value, leave the cell empty
- Match row labels and column headers carefully to the correct fiscal periods

FILES AVAILABLE:
- financials-annual-income, financials-annual-balance, financials-annual-cashflow
- financials-quarterly-income, financials-quarterly-balance, financials-quarterly-cashflow
- standardized-annual-income, standardized-annual-balance, standardized-annual-cashflow
- standardized-quarterly-income, standardized-quarterly-balance, standardized-quarterly-cashflow
"""


class AgentContext:
    """Context for the running agent, including persistent browser and scratchpad."""

    def __init__(self, ticker: str, work_dir: Path, files: dict[str, Path]):
        self.ticker = ticker
        self.work_dir = work_dir
        self.files = files
        self.analyses: dict[str, dict] = {}
        self.financial_data: dict[str, dict] = {}
        self.updaters: dict[str, ExcelUpdater] = {}
        self.data_sources: list[str] = []
        self.files_modified: set[str] = set()

        # Scratchpad for agent notes
        self.notes: list[dict] = []

        # Persistent browser (initialized lazily on first browse call)
        self.browser: StockAnalysisBrowser | None = None

        # Latest screenshot bytes from browser
        self.latest_screenshot: bytes | None = None

    def get_browser(self) -> StockAnalysisBrowser:
        """Get or create the persistent browser instance."""
        if self.browser is None:
            print("Initializing persistent browser session...")
            self.browser = StockAnalysisBrowser()
            self.browser.__enter__()
            print("Browser session started")
        return self.browser

    def get_updater(self, bucket_name: str) -> ExcelUpdater | None:
        """Get or create an updater for a file."""
        if bucket_name not in self.updaters:
            if bucket_name in self.files:
                self.updaters[bucket_name] = ExcelUpdater(self.files[bucket_name])
        return self.updaters.get(bucket_name)

    def close_all(self):
        """Close all open workbooks and browser."""
        for updater in self.updaters.values():
            updater.close()
        if self.browser:
            try:
                self.browser.__exit__(None, None, None)
                print("Browser session closed")
            except Exception as e:
                print(f"Error closing browser: {e}")
            self.browser = None


def handle_tool_call(context: AgentContext, tool_name: str, tool_input: dict) -> str:
    """Handle a tool call from the agent."""

    if tool_name == "analyze_excel":
        bucket_name = tool_input["bucket_name"]
        if bucket_name not in context.files:
            return json.dumps({"error": f"File {bucket_name} not found"})

        if bucket_name not in context.analyses:
            from .schema import analyze_excel_file
            context.analyses[bucket_name] = analyze_excel_file(context.files[bucket_name])

        return json.dumps(context.analyses[bucket_name], indent=2)

    elif tool_name == "browse_stockanalysis":
        statement_type = tool_input["statement_type"]
        period = tool_input["period"]
        data_type = tool_input["data_type"]

        browser = context.get_browser()
        result = browser.navigate_to_financials(
            context.ticker, statement_type, period, data_type
        )

        # Store screenshot for vision extraction
        if result.get("success") and result.get("screenshot_bytes"):
            context.latest_screenshot = result.pop("screenshot_bytes")
            context.data_sources.append(f"stockanalysis.com/{statement_type}/{period}/{data_type}")
            result["screenshot_available"] = True
            result["message"] = "Screenshot captured. Use extract_page_with_vision to read the financial data."
        else:
            context.latest_screenshot = None

        return json.dumps(result, indent=2)

    elif tool_name == "extract_page_with_vision":
        instruction = tool_input["instruction"]

        if not context.latest_screenshot:
            return json.dumps({"error": "No screenshot available. Call browse_stockanalysis first."})

        # Call Gemini API directly with the screenshot
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            return json.dumps({"error": "GEMINI_API_KEY not configured"})

        try:
            img_b64 = base64.b64encode(context.latest_screenshot).decode("utf-8")

            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": instruction},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": img_b64,
                                    }
                                },
                            ]
                        }
                    ],
                    "generationConfig": {
                        "maxOutputTokens": 8192,
                        "temperature": 0.1,
                    },
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.dumps({"success": True, "extracted_data": text})
            else:
                return json.dumps({"error": f"Gemini API error {response.status_code}: {response.text[:500]}"})

        except Exception as e:
            return json.dumps({"error": f"Vision extraction failed: {str(e)}"})

    elif tool_name == "note_finding":
        category = tool_input["category"]
        content = tool_input["content"]
        note = {"category": category, "content": content, "timestamp": time.time()}
        context.notes.append(note)
        print(f"  📝 [{category}] {content[:200]}")
        return json.dumps({"recorded": True, "total_notes": len(context.notes)})

    elif tool_name == "update_excel_cell":
        bucket_name = tool_input["bucket_name"]
        updater = context.get_updater(bucket_name)

        if not updater:
            return json.dumps({"error": f"Cannot open file {bucket_name}"})

        success = updater.update_cell(
            tool_input["sheet_name"],
            tool_input["cell_ref"],
            tool_input["value"]
        )

        if success:
            context.files_modified.add(bucket_name)

        return json.dumps({"success": success})

    elif tool_name == "save_all_files":
        saved = 0
        for bucket_name, updater in context.updaters.items():
            if bucket_name in context.files_modified:
                if updater.save():
                    saved += 1

        return json.dumps({
            "files_saved": saved,
            "files_modified": list(context.files_modified)
        })

    elif tool_name == "web_search":
        query = tool_input["query"]
        api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        if not api_key:
            return json.dumps({"error": "PERPLEXITY_API_KEY not configured"})

        response = httpx.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar-pro",
                "messages": [
                    {"role": "system", "content": "You are a financial data assistant. Provide precise numerical financial data. Always give fully written out absolute numbers (e.g., 394328000000 not 394.33B). Cite your sources."},
                    {"role": "user", "content": query},
                ],
            },
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            context.data_sources.append("perplexity-web-search")
            return json.dumps({"answer": answer, "citations": citations})
        else:
            return json.dumps({"error": f"Perplexity API error: {response.status_code}"})

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run_agent(ticker: str, report_date: str, timing: str) -> dict[str, Any]:
    """
    Run the agentic workflow for a ticker.

    Args:
        ticker: Stock ticker symbol
        report_date: Earnings report date
        timing: Either "premarket" or "afterhours"

    Returns:
        Dict with success status, files updated count, etc.
    """
    client = anthropic.Anthropic()
    storage = StorageClient()

    # Create working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)

        # Download all files
        print(f"Downloading files for {ticker}...")
        files = storage.download_all_files(ticker, work_dir)

        if not files:
            return {
                "success": False,
                "error": "No files found for ticker",
                "files_updated": 0,
            }

        print(f"Downloaded {len(files)} files")

        # Analyze all files upfront for context
        analyses = analyze_all_files(files)
        schema_context = format_schema_for_llm(analyses)

        # Initialize agent context
        context = AgentContext(ticker, work_dir, files)
        context.analyses = analyses

        # Prepare initial message
        user_message = f"""Process the financial files for ticker: {ticker}
Report date: {report_date}
Market timing: {timing}

Here is an overview of the file schemas:
{schema_context}

Please:
1. Review the file structures above
2. Use note_finding to record which cells are empty and need data
3. Use browse_stockanalysis + extract_page_with_vision to get financial data from StockAnalysis.com
4. Use web_search to cross-reference values
5. Use note_finding to track your validation results
6. Fill in ONLY empty cells with dual-source verified values
7. Save all files when done

IMPORTANT: Only fill empty cells. Do NOT edit, overwrite, or modify any pre-existing data. All numeric values must be fully written out (e.g., 394328000000 not 394.33B)."""

        messages = [{"role": "user", "content": user_message}]

        # Run the agent loop
        max_iterations = 30
        iteration = 0
        start_time = time.time()

        try:
            while iteration < max_iterations:
                iteration += 1
                iter_start = time.time()
                print(f"\n{'='*60}")
                print(f"--- Agent iteration {iteration}/{max_iterations} ---")
                print(f"{'='*60}")

                response = client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=8192,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                # Print agent reasoning (text blocks)
                for block in response.content:
                    if hasattr(block, "text"):
                        print(f"\n💭 Agent reasoning:\n{block.text[:500]}")
                        if len(block.text) > 500:
                            print(f"  ... ({len(block.text)} chars total)")

                # Process response
                if response.stop_reason == "end_turn":
                    elapsed = time.time() - iter_start
                    print(f"\n✅ Agent finished (iteration took {elapsed:.1f}s)")
                    break

                if response.stop_reason == "tool_use":
                    # Handle tool calls
                    assistant_content = response.content
                    tool_results = []

                    for block in assistant_content:
                        if block.type == "tool_use":
                            print(f"\n🔧 Tool: {block.name}")
                            print(f"   Input: {json.dumps(block.input)[:200]}")

                            result = handle_tool_call(context, block.name, block.input)

                            # Print result summary
                            result_preview = result[:300] if len(result) <= 300 else result[:300] + "..."
                            print(f"   Result: {result_preview}")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    # Add assistant response and tool results to messages
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": tool_results})

                    elapsed = time.time() - iter_start
                    print(f"\n⏱️  Iteration {iteration} took {elapsed:.1f}s")

                else:
                    print(f"Unexpected stop reason: {response.stop_reason}")
                    break

            # Print final summary
            total_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"AGENT COMPLETE — {iteration} iterations in {total_time:.1f}s")
            print(f"{'='*60}")

            # Print all scratchpad notes
            if context.notes:
                print(f"\n📋 Scratchpad ({len(context.notes)} notes):")
                for i, note in enumerate(context.notes, 1):
                    print(f"  {i}. [{note['category']}] {note['content'][:200]}")

            # Upload modified files back to storage
            files_updated = 0
            if context.files_modified:
                # Close all workbooks first
                context.close_all()

                # Upload only modified files
                for bucket_name in context.files_modified:
                    if bucket_name in context.files:
                        if storage.upload_file(
                            bucket_name,
                            f"{ticker}.xlsx",
                            context.files[bucket_name]
                        ):
                            files_updated += 1
            else:
                context.close_all()

            return {
                "success": True,
                "files_updated": files_updated,
                "data_sources": list(set(context.data_sources)),
                "iterations": iteration,
                "notes_count": len(context.notes),
            }

        except Exception as e:
            context.close_all()
            return {
                "success": False,
                "error": str(e),
                "files_updated": 0,
            }
