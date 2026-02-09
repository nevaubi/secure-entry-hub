"""
Agent orchestrator using Anthropic Claude.

Coordinates the agentic workflow:
1. Analyze Excel schemas
2. Determine what data is needed
3. Browse for data
4. Update files
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Any
import anthropic

from .storage import StorageClient
from .schema import analyze_all_files, format_schema_for_llm
from .browser import extract_financials
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
        "description": "Browse StockAnalysis.com to extract financial statement data (income statement, balance sheet, cash flow) for the ticker. Returns structured financial data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "statement_type": {
                    "type": "string",
                    "enum": ["income-statement", "balance-sheet", "cash-flow-statement"],
                    "description": "Type of financial statement to extract"
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
    }
]


SYSTEM_PROMPT = """You are a financial data agent. Your task is to update Excel files containing financial statements with accurate, up-to-date data.

WORKFLOW:
1. First, use analyze_excel to understand the structure of each file you need to update
2. Identify what data needs to be filled in (look for empty cells, outdated data)
3. Use browse_stockanalysis to get the latest financial data from StockAnalysis.com
4. Use update_excel_cell to fill in the correct values
5. Call save_all_files when done

IMPORTANT RULES:
- Always verify the data you're inserting matches the expected format and period
- Match row labels carefully (Revenue, Net Income, Total Assets, etc.)
- Match column headers to the correct fiscal periods
- Numbers should be in the same scale as existing data (thousands, millions, etc.)
- If you can't find accurate data for a cell, leave it empty rather than guessing
- Be careful to distinguish between annual and quarterly data

FILES AVAILABLE:
- financials-annual-income: Annual income statement data
- financials-annual-balance: Annual balance sheet data  
- financials-annual-cashflow: Annual cash flow statement data
- financials-quarterly-income: Quarterly income statement data
- financials-quarterly-balance: Quarterly balance sheet data
- financials-quarterly-cashflow: Quarterly cash flow statement data
- standardized-annual-*: Standardized versions of the above
- standardized-quarterly-*: Standardized versions of the above
"""


class AgentContext:
    """Context for the running agent."""

    def __init__(self, ticker: str, work_dir: Path, files: dict[str, Path]):
        self.ticker = ticker
        self.work_dir = work_dir
        self.files = files
        self.analyses: dict[str, dict] = {}
        self.financial_data: dict[str, dict] = {}
        self.updaters: dict[str, ExcelUpdater] = {}
        self.data_sources: list[str] = []
        self.files_modified: set[str] = set()

    def get_updater(self, bucket_name: str) -> ExcelUpdater | None:
        """Get or create an updater for a file."""
        if bucket_name not in self.updaters:
            if bucket_name in self.files:
                self.updaters[bucket_name] = ExcelUpdater(self.files[bucket_name])
        return self.updaters.get(bucket_name)

    def close_all(self):
        """Close all open workbooks."""
        for updater in self.updaters.values():
            updater.close()


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
        key = f"{statement_type}_{period}"

        # Check if we already have this data
        if key not in context.financial_data:
            from .browser import StockAnalysisBrowser
            with StockAnalysisBrowser() as browser:
                if browser.login():
                    context.financial_data[key] = browser.extract_financial_table(
                        context.ticker, statement_type, period
                    )
                    context.data_sources.append(f"stockanalysis.com/{statement_type}/{period}")
                else:
                    context.financial_data[key] = {"error": "Failed to login"}

        return json.dumps(context.financial_data[key], indent=2)

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
2. Identify cells that need to be updated with latest financial data
3. Browse StockAnalysis.com to get the data
4. Update the appropriate cells
5. Save all files when done

Focus on filling in any empty cells or updating any data that appears outdated."""

        messages = [{"role": "user", "content": user_message}]

        # Run the agent loop
        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                print(f"\n--- Agent iteration {iteration} ---")

                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                # Process response
                if response.stop_reason == "end_turn":
                    print("Agent finished")
                    break

                if response.stop_reason == "tool_use":
                    # Handle tool calls
                    assistant_content = response.content
                    tool_results = []

                    for block in assistant_content:
                        if block.type == "tool_use":
                            print(f"Tool call: {block.name}")
                            result = handle_tool_call(context, block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    # Add assistant response and tool results to messages
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": tool_results})

                else:
                    print(f"Unexpected stop reason: {response.stop_reason}")
                    break

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

            return {
                "success": True,
                "files_updated": files_updated,
                "data_sources": list(set(context.data_sources)),
                "iterations": iteration,
            }

        except Exception as e:
            context.close_all()
            return {
                "success": False,
                "error": str(e),
                "files_updated": 0,
            }
