"""
Agent orchestrator using Anthropic Claude.

Coordinates the agentic workflow:
1. Process Excel files one at a time (12 sequential sub-runs)
2. Inject full cell data for only the current file
3. Browse StockAnalysis.com (persistent browser session)
4. Extract data via Gemini vision
5. Track findings in scratchpad (re-injected each iteration)
6. Update files with dual-source validated data
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
from .schema import analyze_excel_file_full, format_full_schema_for_llm
from .browser import StockAnalysisBrowser
from .updater import ExcelUpdater


# Ordered list of files to process sequentially
FILE_ORDER = [
    "standardized-annual-income",
    "standardized-annual-balance",
    "standardized-annual-cashflow",
    "standardized-quarterly-income",
    "standardized-quarterly-balance",
    "standardized-quarterly-cashflow",
    "financials-annual-income",
    "financials-annual-balance",
    "financials-annual-cashflow",
    "financials-quarterly-income",
    "financials-quarterly-balance",
    "financials-quarterly-cashflow",
]

# Maps file names to browse_stockanalysis parameters
FILE_TO_BROWSE_PARAMS = {
    "standardized-annual-income": {"statement_type": "income", "period": "annual", "data_type": "standardized"},
    "standardized-annual-balance": {"statement_type": "balance", "period": "annual", "data_type": "standardized"},
    "standardized-annual-cashflow": {"statement_type": "cashflow", "period": "annual", "data_type": "standardized"},
    "standardized-quarterly-income": {"statement_type": "income", "period": "quarterly", "data_type": "standardized"},
    "standardized-quarterly-balance": {"statement_type": "balance", "period": "quarterly", "data_type": "standardized"},
    "standardized-quarterly-cashflow": {"statement_type": "cashflow", "period": "quarterly", "data_type": "standardized"},
    "financials-annual-income": {"statement_type": "income", "period": "annual", "data_type": "as-reported"},
    "financials-annual-balance": {"statement_type": "balance", "period": "annual", "data_type": "as-reported"},
    "financials-annual-cashflow": {"statement_type": "cashflow", "period": "annual", "data_type": "as-reported"},
    "financials-quarterly-income": {"statement_type": "income", "period": "quarterly", "data_type": "as-reported"},
    "financials-quarterly-balance": {"statement_type": "balance", "period": "quarterly", "data_type": "as-reported"},
    "financials-quarterly-cashflow": {"statement_type": "cashflow", "period": "quarterly", "data_type": "as-reported"},
}

# Tools available to the agent (per-file context — no analyze_excel needed)
TOOLS = [
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
        "description": "Record a finding or intermediate result to your scratchpad. Use this to track what data you've gathered, what cells are empty, what values you plan to insert, and validation results. Your notes persist across iterations AND across files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["data_gathered", "empty_cells", "validation", "decision", "error", "file_complete"],
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
        "description": "Update a specific cell in the CURRENT Excel file with a new value. The bucket_name is pre-set to the current file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the Excel sheet"
                },
                "cell_ref": {
                    "type": "string",
                    "description": "Cell reference like 'B2' or 'C5'"
                },
                "value": {
                    "type": ["string", "number"],
                    "description": "The value to set"
                }
            },
            "required": ["sheet_name", "cell_ref", "value"]
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


def build_scratchpad_summary(notes: list[dict]) -> str:
    """Build a summary of all scratchpad notes for context re-injection."""
    if not notes:
        return ""

    summary = "## YOUR SCRATCHPAD (from previous work)\n"
    for note in notes:
        summary += f"- [{note['category']}] {note['content']}\n"
    return summary


def build_file_system_prompt(
    ticker: str,
    file_name: str,
    file_index: int,
    total_files: int,
    full_schema: str,
    empty_cells: list[str],
    browse_params: dict,
    scratchpad_summary: str,
) -> str:
    """Build a focused system prompt for processing a single file."""
    prompt = f"""You are a financial data agent. You are processing file {file_index}/{total_files} for ticker {ticker}.

CURRENT FILE: {file_name}
This is the ONLY file you need to work on right now. Focus entirely on filling empty cells in this file.

MATCHING StockAnalysis.com PAGE:
- statement_type: {browse_params['statement_type']}
- period: {browse_params['period']}
- data_type: {browse_params['data_type']}
Call browse_stockanalysis with these exact parameters to get the data.

COMPLETE FILE DATA:
{full_schema}

EMPTY CELLS NEEDING DATA ({len(empty_cells)} total):
{', '.join(empty_cells) if empty_cells else 'None — this file is already complete.'}

{scratchpad_summary}

WORKFLOW:
1. If there are no empty cells, respond with "FILE COMPLETE" immediately
2. Call browse_stockanalysis with the parameters above to navigate to the matching page
3. Call extract_page_with_vision to read the financial data from the screenshot
4. Call web_search to cross-reference values from a second source (Perplexity)
5. Use note_finding to record gathered data and validation results
6. Use update_excel_cell to fill ONLY empty cells with dual-source verified values
7. When done filling all cells you can verify, respond with "FILE COMPLETE"

DUAL-SOURCE VALIDATION:
- For every data point, gather it from BOTH StockAnalysis (via vision) AND Perplexity web_search
- If both sources agree, use the value
- If they disagree, investigate further or leave the cell empty
- Record your validation reasoning with note_finding

CRITICAL RULES:
- NEVER modify cells that already contain values — ONLY fill empty cells
- All numeric values must be fully written out (e.g., 394328000000 not 394.33B)
- If you cannot confirm a value from two sources, leave the cell empty
- Match row labels and column headers carefully to the correct fiscal periods
- The update_excel_cell tool is pre-configured for the current file — just provide sheet_name, cell_ref, and value
"""
    return prompt


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

        # Scratchpad for agent notes — persists across ALL files
        self.notes: list[dict] = []

        # Track which file is currently being processed
        self.current_file: str | None = None

        # Persistent browser (initialized lazily on first browse call)
        self.browser: StockAnalysisBrowser | None = None

        # Latest screenshot bytes from browser
        self.latest_screenshot: bytes | None = None

        # Track completed files
        self.completed_files: list[str] = []

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

    if tool_name == "browse_stockanalysis":
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
        note = {
            "category": category,
            "content": content,
            "file": context.current_file or "global",
            "timestamp": time.time(),
        }
        context.notes.append(note)
        print(f"  📝 [{category}] {content[:200]}")
        return json.dumps({"recorded": True, "total_notes": len(context.notes)})

    elif tool_name == "update_excel_cell":
        # Pre-set bucket_name to the current file
        bucket_name = context.current_file
        if not bucket_name:
            return json.dumps({"error": "No current file set"})

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


def save_single_file(context: AgentContext, storage: StorageClient, bucket_name: str) -> bool:
    """Save and upload a single modified file."""
    if bucket_name not in context.files_modified:
        return False

    updater = context.updaters.get(bucket_name)
    if updater:
        updater.save()
        updater.close()
        # Remove from updaters so it won't be closed again
        del context.updaters[bucket_name]

    if bucket_name in context.files:
        return storage.upload_file(
            bucket_name,
            f"{context.ticker}.xlsx",
            context.files[bucket_name]
        )
    return False


def run_agent(ticker: str, report_date: str, timing: str) -> dict[str, Any]:
    """
    Run the agentic workflow for a ticker, processing one file at a time.

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

        # Initialize agent context
        context = AgentContext(ticker, work_dir, files)
        start_time = time.time()
        total_iterations = 0
        files_updated = 0

        try:
            # Process files one at a time
            for file_idx, file_name in enumerate(FILE_ORDER, 1):
                if file_name not in files:
                    print(f"\n⏭️  Skipping {file_name} (not downloaded)")
                    continue

                context.current_file = file_name
                browse_params = FILE_TO_BROWSE_PARAMS[file_name]

                # Build rich schema for ONLY this file
                print(f"\n{'='*60}")
                print(f"📁 Processing file {file_idx}/{len(FILE_ORDER)}: {file_name}")
                print(f"{'='*60}")

                file_analysis = analyze_excel_file_full(files[file_name])
                full_schema = format_full_schema_for_llm(file_analysis)

                # Collect empty cells list
                empty_cells = []
                for sheet in file_analysis.get("sheets", []):
                    empty_cells.extend(sheet.get("empty_cells", []))

                # Skip files with no empty cells
                if not empty_cells:
                    print(f"  ✅ No empty cells — skipping")
                    context.completed_files.append(file_name)
                    context.notes.append({
                        "category": "file_complete",
                        "content": f"{file_name}: No empty cells, skipped.",
                        "file": file_name,
                        "timestamp": time.time(),
                    })
                    continue

                print(f"  📊 {len(empty_cells)} empty cells to fill")

                # Build scratchpad summary from all previous work
                scratchpad_summary = build_scratchpad_summary(context.notes)

                # Build focused system prompt for this file
                system_prompt = build_file_system_prompt(
                    ticker=ticker,
                    file_name=file_name,
                    file_index=file_idx,
                    total_files=len(FILE_ORDER),
                    full_schema=full_schema,
                    empty_cells=empty_cells,
                    browse_params=browse_params,
                    scratchpad_summary=scratchpad_summary,
                )

                # Fresh message history for each file
                messages = [{"role": "user", "content": f"Begin processing {file_name} for {ticker}. Report date: {report_date}, timing: {timing}."}]

                # Sub-loop for this file (up to 10 iterations)
                max_file_iterations = 10
                for iteration in range(1, max_file_iterations + 1):
                    total_iterations += 1
                    iter_start = time.time()
                    print(f"\n  --- {file_name} iteration {iteration}/{max_file_iterations} ---")

                    response = client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=8192,
                        system=system_prompt,
                        tools=TOOLS,
                        messages=messages,
                    )

                    # Print agent reasoning
                    for block in response.content:
                        if hasattr(block, "text"):
                            print(f"\n  💭 Agent: {block.text[:500]}")
                            if len(block.text) > 500:
                                print(f"    ... ({len(block.text)} chars total)")

                    # Check if agent is done with this file
                    if response.stop_reason == "end_turn":
                        elapsed = time.time() - iter_start
                        print(f"  ✅ File complete ({elapsed:.1f}s)")
                        break

                    if response.stop_reason == "tool_use":
                        assistant_content = response.content
                        tool_results = []

                        for block in assistant_content:
                            if block.type == "tool_use":
                                print(f"  🔧 Tool: {block.name}")
                                print(f"     Input: {json.dumps(block.input)[:200]}")

                                result = handle_tool_call(context, block.name, block.input)

                                result_preview = result[:300] if len(result) <= 300 else result[:300] + "..."
                                print(f"     Result: {result_preview}")

                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result,
                                })

                        messages.append({"role": "assistant", "content": assistant_content})
                        messages.append({"role": "user", "content": tool_results})

                        elapsed = time.time() - iter_start
                        print(f"  ⏱️  Iteration took {elapsed:.1f}s")
                    else:
                        print(f"  Unexpected stop reason: {response.stop_reason}")
                        break

                # Save this file immediately after processing
                context.completed_files.append(file_name)
                if file_name in context.files_modified:
                    if save_single_file(context, storage, file_name):
                        files_updated += 1
                        print(f"  📤 Uploaded {file_name}")
                    else:
                        print(f"  ⚠️  Failed to upload {file_name}")

                print(f"\n  Progress: {len(context.completed_files)}/{len(FILE_ORDER)} files processed")

            # Final summary
            total_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"AGENT COMPLETE — {total_iterations} total iterations in {total_time:.1f}s")
            print(f"Files updated: {files_updated}/{len(FILE_ORDER)}")
            print(f"{'='*60}")

            # Print all scratchpad notes
            if context.notes:
                print(f"\n📋 Scratchpad ({len(context.notes)} notes):")
                for i, note in enumerate(context.notes, 1):
                    print(f"  {i}. [{note['category']}] ({note.get('file', '?')}) {note['content'][:200]}")

            context.close_all()

            return {
                "success": True,
                "files_updated": files_updated,
                "data_sources": list(set(context.data_sources)),
                "iterations": total_iterations,
                "notes_count": len(context.notes),
                "completed_files": context.completed_files,
            }

        except Exception as e:
            context.close_all()
            return {
                "success": False,
                "error": str(e),
                "files_updated": files_updated,
                "completed_files": context.completed_files,
            }
