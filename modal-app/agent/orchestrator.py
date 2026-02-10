"""
Agent orchestrator using Anthropic Claude.

Coordinates the agentic workflow:
1. Process Excel files one at a time (6 sequential sub-runs)
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
    "financials-annual-income",
    "financials-annual-balance",
    "financials-annual-cashflow",
    "financials-quarterly-income",
    "financials-quarterly-balance",
    "financials-quarterly-cashflow",
]

# Maps file names to browse_stockanalysis parameters
FILE_TO_BROWSE_PARAMS = {
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
                    "enum": ["as-reported"],
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
        "name": "insert_new_period_column",
        "description": "Insert a new column B into the current Excel file for a new fiscal period. This shifts ALL existing data one column to the right, then sets the date header (row 1) and period header (row 2) in the new column B. Returns a list of row numbers that need data (rows where the adjacent shifted column has values). Call this BEFORE using update_excel_cell to fill the new column.",
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
    browse_params: dict,
    scratchpad_summary: str,
    report_date: str = "",
    fiscal_period_end: str | None = None,
    leftmost_date: str | None = None,
    leftmost_period: str | None = None,
    data_rows: list[int] | None = None,
) -> str:
    """Build a focused system prompt for processing a single file."""

    # Use fiscal_period_end for column date comparison (fallback to report_date)
    target_date = fiscal_period_end or report_date

    # Determine if a new column needs to be inserted
    needs_new_column = False
    if leftmost_date and target_date:
        needs_new_column = target_date > leftmost_date

    new_column_section = ""
    if needs_new_column:
        rows_preview = str(data_rows[:20]) if data_rows else "unknown"
        if data_rows and len(data_rows) > 20:
            rows_preview += f"... ({len(data_rows)} total)"
        new_column_section = f"""
NEW COLUMN INSERTION REQUIRED:
- The fiscal_period_end ({target_date}) is NEWER than the current leftmost date column ({leftmost_date} / {leftmost_period})
- You MUST call insert_new_period_column FIRST to create a new column B
- Use fiscal_period_end ({target_date}) as the date_header and determine the correct fiscal period label (for all annual data, use Q4 YYYY instead of FY YYYY in the column header for the fiscal label)
- After insertion, fill only the new column B cells for all rows that had data in the previous columns. Do not guess or hallucinate, and do not insert or modify any other data other than only the newly created column B
- The rows needing data are: {rows_preview}
"""
    elif leftmost_date:
        new_column_section = f"""
CURRENT LEFTMOST COLUMN: {leftmost_date} / {leftmost_period}
- The fiscal_period_end ({target_date}) matches or is older than the leftmost column
- No new column insertion needed
"""

    prompt = f"""You are a financial data agent. You are processing file {file_index}/{total_files} for ticker {ticker}.

CURRENT FILE: {file_name}
This is the ONLY file you need to work on right now.

MATCHING StockAnalysis.com PAGE:
- statement_type: {browse_params['statement_type']}
- period: {browse_params['period']}
- data_type: {browse_params['data_type']}
Call browse_stockanalysis with these exact parameters to get the data.

{scratchpad_summary}

WORKFLOW:
1. Check if a new column needs to be inserted:
   - If the NEW COLUMN INSERTION REQUIRED section appears above, you MUST call insert_new_period_column FIRST
   - Use the date from the FIRST data column (leftmost) of the Gemini-extracted markdown table as your date_header. For annual files, ALWAYS use "Q4 YYYY" as the period_header. For quarterly files, use the specific quarter (e.g. "Q1 2026", "Q2 2026").
   - After insertion, the tool returns a row_map telling you exactly which cells to fill (e.g. B3=Total Assets, B4=Current Assets...)
2. If no new column is needed and there are no empty cells, respond with "FILE COMPLETE"
3. Call browse_stockanalysis with the parameters above to navigate to the matching page
4. Call extract_page_with_vision to read the financial data from the screenshot
5. Match the extracted data to the row labels from the file/row_map
6. Use update_excel_cell to fill ALL cells in one go — batch as many calls as possible per iteration
7. When done, respond with "FILE COMPLETE"

IMPORTANT — FOR NEW COLUMN INSERTION:
- After inserting the column, you get a row_map with exact cell references and labels
- Browse StockAnalysis FIRST, extract data, then batch-fill all cells that correctly match the corresponding row label via the StockAnalysis data, use your professional judgement
- Utilize the web_search for the remaining required row labels, sometimes row labels will not match perfectly, use your best accurate judgement.
- You can optionally use web_search for a quick sanity check for validation if required, but do not call it excessively, if you have the required correct data values to fill the column B for the current respective file, then utilize update_excel_cell to insert the values and complete, do not alter any other column data ONLY the new Column B
- Accuracy is critical: you have up to 15 iterations max, so be thorough — browse, extract, and batch-write all cells carefully
- ALWAYS REMEMBER to use update_excel_cell when finished gathering the required data to ensure you actually fill in the respective column B cells before finishing

FOR FILLING EXISTING EMPTY CELLS (no insertion):
- Use dual-source validation: gather from StockAnalysis AND Perplexity web_search as needed
- If both sources agree, use the value; if they disagree, investigate or leave empty, use your best judgement

CRITICAL RULES:
- When inserting a new column, ONLY fill rows listed in the row_map
- When a new column is being inserted, IGNORE all empty cells in columns C, D, E, etc.
  Your ONLY job is to fill the NEW column B with the latest period's data.
  Do NOT research or fill historical data from older periods.
- After gathering financial data, you MUST call update_excel_cell for every target row.
  Do NOT stop after browsing or extracting — the file is not complete until cells are written.
  Always use fully written-out absolute numbers (e.g., 394328000000 not 394.3B).
  Carefully match each value to its corresponding row label before writing, use your best judgement for potentially slightly .
- When filling empty cells (no insertion), NEVER modify cells that already contain values
- All numeric values must be fully written out (e.g., 394328000000 not 394.33B)
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

        # Fiscal period end date (forced for date headers)
        self.fiscal_period_end: str | None = None

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
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={gemini_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": """You are a financial data extraction specialist. Analyze this screenshot of a financial statement table.

TASK: Extract ONLY the first 4 columns from the LEFT side of the table. Start from the leftmost column (row labels) and include the next 3 data columns to the right.

OUTPUT FORMAT: A markdown table with:
- Row 1: Column headers exactly as shown (dates or period labels)
- All subsequent rows: Row labels in column 1, numeric values in columns 2-4
- Reproduce ALL numeric values EXACTLY as displayed (do not round, convert, or abbreviate)
- Reproduce ALL row labels EXACTLY as displayed
- Reproduce ALL column headers/dates EXACTLY as displayed
- If a cell is empty or shows a dash, use an empty cell in the markdown

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

    elif tool_name == "insert_new_period_column":
        bucket_name = context.current_file
        if not bucket_name:
            return json.dumps({"error": "No current file set"})

        updater = context.get_updater(bucket_name)
        if not updater:
            return json.dumps({"error": f"Cannot open file {bucket_name}"})

        # Let the agent determine the date from the Gemini-extracted markdown table
        result = updater.insert_new_period_column(
            tool_input["sheet_name"],
            tool_input["date_header"],
            tool_input["period_header"]
        )

        if result.get("success"):
            context.files_modified.add(bucket_name)

        return json.dumps(result)

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
                "model": "sonar",
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


def run_agent(ticker: str, report_date: str, timing: str, fiscal_period_end: str | None = None) -> dict[str, Any]:
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
        context.fiscal_period_end = fiscal_period_end
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

                # Collect empty cells and leftmost date info
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

                # Check if new column insertion is needed (use fiscal_period_end, fallback to report_date)
                target_date = fiscal_period_end or report_date
                needs_new_column = leftmost_date and target_date and target_date > leftmost_date

                # Skip files with no empty cells AND no new column needed
                if not empty_cells and not needs_new_column:
                    print(f"  ✅ No empty cells and no new column needed — skipping")
                    context.completed_files.append(file_name)
                    context.notes.append({
                        "category": "file_complete",
                        "content": f"{file_name}: No empty cells, no new column needed, skipped.",
                        "file": file_name,
                        "timestamp": time.time(),
                    })
                    continue

                if needs_new_column:
                    print(f"  🆕 New column needed (fiscal_period_end {target_date} > leftmost {leftmost_date})")
                    print(f"  📊 {len(data_rows or [])} rows will need data in the new column")
                else:
                    print(f"  📊 {len(empty_cells)} empty cells to fill")

                # Build scratchpad summary from all previous work
                scratchpad_summary = build_scratchpad_summary(context.notes)

                # Build focused system prompt for this file
                system_prompt = build_file_system_prompt(
                    ticker=ticker,
                    file_name=file_name,
                    file_index=file_idx,
                    total_files=len(FILE_ORDER),
                    browse_params=browse_params,
                    scratchpad_summary=scratchpad_summary,
                    report_date=report_date,
                    fiscal_period_end=fiscal_period_end,
                    leftmost_date=leftmost_date,
                    leftmost_period=leftmost_period,
                    data_rows=data_rows,
                )

                # Fresh message history for each file
                if needs_new_column:
                    messages = [{"role": "user", "content": f"Begin processing {file_name} for {ticker}. Report date: {report_date}, fiscal_period_end: {target_date}, timing: {timing}.\n\nCOMPLETE FILE DATA:\n{full_schema}\n\nA NEW COLUMN INSERTION IS REQUIRED.\n\nIMPORTANT — DATE AND PERIOD HEADERS:\n- Do NOT use fiscal_period_end or report_date for the column header.\n- Instead, FIRST call browse_stockanalysis, THEN call extract_page_with_vision.\n- The Gemini vision result will return a markdown table. Use the DATE from the FIRST data column (leftmost after row labels) of that markdown table as your date_header.\n- For annual files, ALWAYS use 'Q4 YYYY' as the period_header. For quarterly files, use the specific quarter (e.g. 'Q1 2026').\n- The Gemini markdown table is your PRIMARY data source. Use web_search only for validation or missing values.\n\nYou have up to 15 iterations. Be thorough:\n1. Browse + extract in iteration 1\n2. Insert column with correct date/period from the markdown table\n3. Batch-write ALL cells using data from the markdown table\n4. Use web_search for validation or gaps as needed\n5. Finish when all cells are written\n\nFocus ONLY on the newest period column B after insertion.\nDo NOT fill old/historical empty cells. Ignore columns C, D, E, etc.\nUse FULL absolute numbers (e.g., 394328000000 not 394.3B or 394,328).\nMatch each value to the correct row label carefully before inserting.\nDo NOT stop after extracting data — the job is not done until every cell is written."}]
                else:
                    messages = [{"role": "user", "content": f"Begin processing {file_name} for {ticker}. Report date: {report_date}, timing: {timing}.\n\nCOMPLETE FILE DATA:\n{full_schema}\n\nEMPTY CELLS NEEDING DATA ({len(empty_cells)} total):\n{', '.join(empty_cells) if empty_cells else 'None'}"}]

                # Sub-loop: 15 iterations max per file
                max_file_iterations = 15
                for iteration in range(1, max_file_iterations + 1):
                    total_iterations += 1
                    iter_start = time.time()
                    print(f"\n  --- {file_name} iteration {iteration}/{max_file_iterations} ---")

                    response = client.messages.create(
                        model="claude-sonnet-4-5-20250514",,
                        max_tokens=8192 if iteration == 1 else 4096,
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
