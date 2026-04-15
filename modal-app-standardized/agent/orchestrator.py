"""
Agent orchestrator for standardized financial data.

Coordinates the agentic workflow for 8 standardized Excel files:
1. Process Excel files one at a time (8 sequential sub-runs)
2. Inject full cell data for only the current file
3. Browse StockAnalysis.com (Standardized + Raw + Fiscal.ai)
4. Extract data via Gemini vision
5. Track findings in scratchpad
6. Update files with data
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


# 8 files: quarterly income/balance/cashflow/ratios, then annual
FILE_ORDER = [
    "standardized-quarterly-income",
    "standardized-quarterly-balance",
    "standardized-quarterly-cashflows",
    "standardized-quarterly-ratios",
    "standardized-annual-income",
    "standardized-annual-balance",
    "standardized-annual-cashflows",
    "standardized-annual-ratios",
]

# Maps file names to browse_stockanalysis parameters
FILE_TO_BROWSE_PARAMS = {
    "standardized-quarterly-income": {"statement_type": "income", "period": "quarterly"},
    "standardized-quarterly-balance": {"statement_type": "balance", "period": "quarterly"},
    "standardized-quarterly-cashflows": {"statement_type": "cashflow", "period": "quarterly"},
    "standardized-quarterly-ratios": {"statement_type": "ratios", "period": "quarterly"},
    "standardized-annual-income": {"statement_type": "income", "period": "annual"},
    "standardized-annual-balance": {"statement_type": "balance", "period": "annual"},
    "standardized-annual-cashflows": {"statement_type": "cashflow", "period": "annual"},
    "standardized-annual-ratios": {"statement_type": "ratios", "period": "annual"},
}

# Tools available to the agent (no web_search for standardized)
TOOLS = [
    {
        "name": "browse_stockanalysis",
        "description": "Navigate to a specific financial statement page on StockAnalysis.com (Standardized + Raw + Fiscal.ai settings are applied automatically). After calling this, use extract_page_with_vision to read the data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "statement_type": {
                    "type": "string",
                    "enum": ["income", "balance", "cashflow", "ratios"],
                    "description": "Type of financial statement"
                },
                "period": {
                    "type": "string",
                    "enum": ["annual", "quarterly"],
                    "description": "Annual or quarterly data"
                }
            },
            "required": ["statement_type", "period"]
        }
    },
    {
        "name": "extract_page_with_vision",
        "description": "Extract financial data from the latest screenshot using Gemini vision. Returns a markdown table. No parameters needed -- just call it after browse_stockanalysis.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "note_finding",
        "description": "Record a finding or intermediate result to your scratchpad. Persists across iterations AND across files.",
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
        "description": "Update a specific cell in the CURRENT Excel file with a new value.",
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
        "name": "insert_new_period_column",
        "description": "Insert a new column B into the current Excel file for a new fiscal period. Shifts ALL existing data one column right, then sets date/period headers. Returns row_map of cells needing data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the Excel sheet"
                },
                "date_header": {
                    "type": "string",
                    "description": "Date for the new period, e.g. '2026-01-31'"
                },
                "period_header": {
                    "type": "string",
                    "description": "Fiscal period label, e.g. 'Q4 2026' or 'FY 2026'"
                }
            },
            "required": ["sheet_name", "date_header", "period_header"]
        }
    },
    {
        "name": "update_excel_cells_batch",
        "description": "Update multiple cells at once in the current Excel file. Much more efficient than calling update_excel_cell repeatedly. Use this as the preferred method for filling data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the Excel sheet"
                },
                "updates": {
                    "type": "array",
                    "description": "Array of cell updates to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cell_ref": {
                                "type": "string",
                                "description": "Cell reference like 'B3' or 'B15'"
                            },
                            "value": {
                                "type": ["string", "number"],
                                "description": "The value to set"
                            }
                        },
                        "required": ["cell_ref", "value"]
                    }
                }
            },
            "required": ["sheet_name", "updates"]
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
    browse_params: dict,
    scratchpad_summary: str,
    leftmost_date: str | None = None,
    leftmost_period: str | None = None,
    data_rows: list[int] | None = None,
) -> str:
    """Build a focused system prompt for processing a single standardized file."""

    # Determine if a new column needs to be inserted
    # For standardized, we always check leftmost date vs current data on StockAnalysis
    new_column_section = ""
    if leftmost_date:
        new_column_section = f"""
CURRENT LEFTMOST COLUMN: {leftmost_date} / {leftmost_period}
- After browsing StockAnalysis, compare the FIRST data column date from the extracted markdown table with the leftmost date above
- If the StockAnalysis data has a NEWER date than {leftmost_date}, you MUST call insert_new_period_column to create a new column B
- If the dates match or StockAnalysis is older, no new column is needed
"""

    prompt = f"""You are a financial data agent processing STANDARDIZED financial data. You are processing file {file_index}/{total_files} for ticker {ticker}.

CURRENT FILE: {file_name}
This is the ONLY file you need to work on right now.

DATA SOURCE: StockAnalysis.com with Standardized + Raw + Fiscal.ai settings (applied automatically).

MATCHING StockAnalysis.com PAGE:
- statement_type: {browse_params['statement_type']}
- period: {browse_params['period']}
Call browse_stockanalysis with these exact parameters to get the data.

{scratchpad_summary}

{new_column_section}

WORKFLOW:
1. Call browse_stockanalysis with the parameters above to navigate to the matching page
2. Call extract_page_with_vision (no parameters needed) to extract structured data
3. Compare the FIRST data column date from the markdown table with the file's leftmost date ({leftmost_date})
4. If a new column is needed:
   - Call insert_new_period_column with the date from the StockAnalysis markdown table
   - For annual files, ALWAYS use "Q4 YYYY" as the period_header
   - For quarterly files, use the specific quarter (e.g. "Q1 2026")
   - Then batch-fill ALL cells using update_excel_cells_batch (preferred) or update_excel_cell
5. If no new column is needed and there are no empty cells, respond with "FILE COMPLETE"
6. When done filling cells, respond with "FILE COMPLETE"

CRITICAL RULES:
- The Gemini-extracted StockAnalysis data is your PRIMARY and COMPLETE data source
- When inserting a new column, ONLY fill rows listed in the row_map
- When a new column is being inserted, IGNORE all empty cells in columns C, D, E, etc.
  Your ONLY job is to fill the NEW column B with the latest period's data.
- After gathering financial data, you MUST call update_excel_cell for every target row.
  Do NOT simply stop after browsing or extracting — the file is not complete until cells are written.
- Always use fully written-out absolute numbers (e.g., 394328000000 not 394.3B).
  For ratios, use decimal values as shown (e.g., 0.45 not 45%).
- Match row labels and column headers carefully to the correct fiscal periods.
- The update_excel_cell tool is pre-configured for the current file.
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
        self.cells_written: dict[str, int] = {}
        self.notes: list[dict] = []
        self.current_file: str | None = None
        self.browser: StockAnalysisBrowser | None = None
        self.latest_screenshot: bytes | None = None
        self.completed_files: list[str] = []
        self.detected_quarter: str | None = None

    def get_browser(self) -> StockAnalysisBrowser:
        if self.browser is None:
            print("Initializing persistent browser session...")
            self.browser = StockAnalysisBrowser()
            self.browser.__enter__()
            print("Browser session started")
        return self.browser

    def get_updater(self, bucket_name: str) -> ExcelUpdater | None:
        if bucket_name not in self.updaters:
            if bucket_name in self.files:
                self.updaters[bucket_name] = ExcelUpdater(self.files[bucket_name])
        return self.updaters.get(bucket_name)

    def close_all(self):
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

        browser = context.get_browser()
        result = browser.navigate_to_financials(
            context.ticker, statement_type, period
        )

        if result.get("success") and result.get("screenshot_bytes"):
            context.latest_screenshot = result.pop("screenshot_bytes")
            context.data_sources.append(f"stockanalysis.com/{statement_type}/{period}/standardized")
            result["screenshot_available"] = True
            result["message"] = "Screenshot captured. Use extract_page_with_vision to read the financial data."
        else:
            context.latest_screenshot = None

        return json.dumps(result, indent=2)

    elif tool_name == "extract_page_with_vision":
        if not context.latest_screenshot:
            return json.dumps({"error": "No screenshot available. Call browse_stockanalysis first."})

        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            return json.dumps({"error": "GEMINI_API_KEY not configured"})

        try:
            img_b64 = base64.b64encode(context.latest_screenshot).decode("utf-8")

            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={gemini_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": """You are a financial data extraction specialist. Analyze this screenshot of a web page which also contains a financial statement table.

TASK: Focus on only the financial statement table. Extract ONLY the first 4 columns from the LEFT most side of the table. Start from the leftmost column (row labels) and include the next 3 data columns to the right.

OUTPUT FORMAT: A markdown table with:
- Row 1: Column headers exactly as shown (dates or period labels)
- All subsequent rows: Row labels in column 1, numeric values in columns 2-4
- Reproduce ALL numeric values EXACTLY as displayed (do not round, convert, or abbreviate)
- Reproduce ALL row labels EXACTLY as displayed
- Reproduce ALL column headers/dates EXACTLY as displayed
- If a cell is empty or shows a dash, use an empty cell in the markdown
- Date accuracy is absolutely crucial, all values, labels, data in the generated markdown table should be 100% accurate based on the provided screenshot of the financial table

CRITICAL ACCURACY RULES:
- Do NOT guess or infer any values — only extract what is visually present
- Do NOT skip any rows — include every row visible in the table
- Preserve the exact formatting of numbers (commas, parentheses for negatives, etc.)
- The column headers typically contain dates (e.g., "12/31/2025") or period labels (e.g., "Q4 2025") — reproduce them exactly

Return ONLY the markdown table, nothing else."""},
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
                        "maxOutputTokens": 18000,
                        "temperature": 1,
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
            context.cells_written[bucket_name] = context.cells_written.get(bucket_name, 0) + 1

        return json.dumps({"success": success})

    elif tool_name == "insert_new_period_column":
        bucket_name = context.current_file
        if not bucket_name:
            return json.dumps({"error": "No current file set"})

        updater = context.get_updater(bucket_name)
        if not updater:
            return json.dumps({"error": f"Cannot open file {bucket_name}"})

        result = updater.insert_new_period_column(
            tool_input["sheet_name"],
            tool_input["date_header"],
            tool_input["period_header"]
        )

        if result.get("success"):
            context.files_modified.add(bucket_name)
            if "quarterly" in bucket_name:
                context.detected_quarter = tool_input["period_header"]

        return json.dumps(result)

    elif tool_name == "update_excel_cells_batch":
        bucket_name = context.current_file
        if not bucket_name:
            return json.dumps({"error": "No current file set"})

        updater = context.get_updater(bucket_name)
        if not updater:
            return json.dumps({"error": f"Cannot open file {bucket_name}"})

        sheet_name = tool_input["sheet_name"]
        updates = tool_input["updates"]
        batch = [{"sheet_name": sheet_name, "cell_ref": u["cell_ref"], "value": u["value"]} for u in updates]
        successful = updater.update_cells_batch(batch)

        if successful > 0:
            context.files_modified.add(bucket_name)
            context.cells_written[bucket_name] = context.cells_written.get(bucket_name, 0) + successful

        return json.dumps({"success": True, "cells_updated": successful, "total_requested": len(updates)})

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
        del context.updaters[bucket_name]

    if bucket_name in context.files:
        return storage.upload_file(
            bucket_name,
            f"{context.ticker}.xlsx",
            context.files[bucket_name]
        )
    return False


def run_agent(ticker: str) -> dict[str, Any]:
    """
    Run the standardized agentic workflow for a ticker, processing 8 files sequentially.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with success status, files updated count, etc.
    """
    client = anthropic.Anthropic()
    storage = StorageClient()

    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)

        print(f"Downloading standardized files for {ticker}...")
        files = storage.download_all_files(ticker, work_dir)

        if not files:
            return {
                "success": False,
                "error": "No files found for ticker",
                "files_updated": 0,
            }

        print(f"Downloaded {len(files)} files")

        context = AgentContext(ticker, work_dir, files)
        start_time = time.time()
        total_iterations = 0
        files_updated = 0

        try:
            for file_idx, file_name in enumerate(FILE_ORDER, 1):
                # Skip annual files if quarterly report was not Q4
                if "annual" in file_name and context.detected_quarter:
                    if "Q4" not in context.detected_quarter.upper():
                        print(f"\n⏭️  Skipping {file_name} -- {context.detected_quarter} report, not Q4/annual")
                        context.completed_files.append(file_name)
                        context.notes.append({
                            "category": "file_skipped",
                            "content": f"{file_name}: Skipped -- {context.detected_quarter} report, annual files only updated for Q4.",
                            "file": file_name,
                            "timestamp": time.time(),
                        })
                        continue

                if file_name not in files:
                    print(f"\n⏭️  Skipping {file_name} (not downloaded)")
                    continue

                context.current_file = file_name
                browse_params = FILE_TO_BROWSE_PARAMS[file_name]

                print(f"\n{'='*60}")
                print(f"📁 Processing file {file_idx}/{len(FILE_ORDER)}: {file_name}")
                print(f"{'='*60}")

                file_analysis = analyze_excel_file_full(files[file_name])
                full_schema = format_full_schema_for_llm(file_analysis)

                empty_cells = []
                leftmost_date = None
                leftmost_period = None
                data_rows = None
                for sheet in file_analysis.get("sheets", []):
                    empty_cells.extend(sheet.get("empty_cells", []))
                    if leftmost_date is None:
                        leftmost_date = sheet.get("leftmost_date")
                        leftmost_period = sheet.get("leftmost_period")
                        data_rows = sheet.get("data_rows")

                # For standardized, we don't have a pre-known target date.
                # The agent will compare StockAnalysis data dates with the file's leftmost date.
                # Skip files with no empty cells (the agent will determine if a new column is needed after browsing)
                # We always let the agent run to check if newer data exists on StockAnalysis

                print(f"  📊 Leftmost date: {leftmost_date} / {leftmost_period}")
                print(f"  📊 {len(empty_cells)} existing empty cells")

                scratchpad_summary = build_scratchpad_summary(context.notes)

                system_prompt = build_file_system_prompt(
                    ticker=ticker,
                    file_name=file_name,
                    file_index=file_idx,
                    total_files=len(FILE_ORDER),
                    browse_params=browse_params,
                    scratchpad_summary=scratchpad_summary,
                    leftmost_date=leftmost_date,
                    leftmost_period=leftmost_period,
                    data_rows=data_rows,
                )

                messages = [{"role": "user", "content": f"Begin processing {file_name} for {ticker}.\n\nCOMPLETE FILE DATA:\n{full_schema}\n\nIMPORTANT:\n- Browse StockAnalysis FIRST to see what data is available\n- Compare the first data column date from StockAnalysis with the file's leftmost date ({leftmost_date})\n- If StockAnalysis has newer data, insert a new column and fill it\n- If dates match and no empty cells exist, respond with FILE COMPLETE\n- Use FULL absolute numbers (e.g., 394328000000 not 394.3B)\n- For ratios, use decimal values as shown on StockAnalysis\n- You have up to 18 iterations. Be thorough but efficient."}]

                max_file_iterations = 18
                for iteration in range(1, max_file_iterations + 1):
                    total_iterations += 1
                    iter_start = time.time()
                    print(f"\n  --- {file_name} iteration {iteration}/{max_file_iterations} ---")

                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=15000,
                        system=system_prompt,
                        tools=TOOLS,
                        messages=messages,
                    )

                    for block in response.content:
                        if hasattr(block, "text"):
                            print(f"\n  💭 Agent: {block.text[:500]}")
                            if len(block.text) > 500:
                                print(f"    ... ({len(block.text)} chars total)")

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
                    cells = context.cells_written.get(file_name, 0)
                    if cells > 0:
                        if save_single_file(context, storage, file_name):
                            files_updated += 1
                            print(f"  📤 Uploaded {file_name} ({cells} cells written)")
                        else:
                            print(f"  ⚠️  Failed to upload {file_name}")
                    else:
                        print(f"  ⚠️  Skipping upload of {file_name} — column inserted but no data cells written")

                print(f"\n  Progress: {len(context.completed_files)}/{len(FILE_ORDER)} files processed")

            total_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"AGENT COMPLETE — {total_iterations} total iterations in {total_time:.1f}s")
            print(f"Files updated: {files_updated}/{len(FILE_ORDER)}")
            print(f"{'='*60}")

            if context.notes:
                print(f"\n📋 Scratchpad ({len(context.notes)} notes):")
                for i, note in enumerate(context.notes, 1):
                    print(f"  {i}. [{note['category']}] ({note.get('file', '?')}) {note['content'][:200]}")

            context.close_all()

            return {
                "success": True,
                "files_updated": files_updated,
                "data_sources": list(set(context.data_sources)),
                "total_iterations": total_iterations,
                "time_seconds": round(total_time, 1),
            }

        except Exception as e:
            context.close_all()
            return {
                "success": False,
                "error": str(e),
                "files_updated": files_updated,
                "total_iterations": total_iterations,
            }
