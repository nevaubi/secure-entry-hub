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
2. Identify ONLY empty cells that need to be filled in
3. Use BOTH browse_stockanalysis AND web_search to gather financial data
4. Cross-reference values from both sources before writing anything
5. Use update_excel_cell to fill in ONLY empty cells with verified values
6. Call save_all_files when done

DUAL-SOURCE VALIDATION:
- You have two equal data sources: browse_stockanalysis and web_search
- For every data point you intend to insert, gather it from BOTH sources
- If both sources agree on a value, use it
- If the sources disagree, investigate further with additional web_search queries
- If you still cannot confirm a value with confidence, leave the cell empty
- This cross-referencing is mandatory — do NOT rely on a single source alone

CRITICAL RULES — READ CAREFULLY:

DO NOT EDIT EXISTING DATA:
- You must NEVER modify, overwrite, or change any cell that already contains a value
- ONLY populate cells that are currently empty/blank
- If a cell already has data — even if you believe it is incorrect or outdated — leave it untouched
- This is the single most important rule. Violating it will corrupt the files.

NUMBER FORMAT — FULLY WRITTEN OUT VALUES:
- All values in these Excel files are fully written out in absolute terms
- For example: revenue of 394.33 billion is stored as 394328000000, NOT as 394.33 or 394328
- When you insert a value, write the complete number with no abbreviation
- Do NOT use thousands, millions, or billions shorthand
- Match this format exactly when inserting new data

DATA ACCURACY:
- Match row labels carefully (Revenue, Net Income, Total Assets, etc.)
- Match column headers to the correct fiscal periods
- If you cannot find accurate data for a cell, leave it empty rather than guessing
- Be careful to distinguish between annual and quarterly data
- Always verify the data you're inserting matches the expected format and period

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

    elif tool_name == "web_search":
        query = tool_input["query"]
        api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        if not api_key:
            return json.dumps({"error": "PERPLEXITY_API_KEY not configured"})

        import httpx
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
2. Identify ONLY cells that are currently EMPTY and need financial data
3. Use BOTH StockAnalysis.com AND web search to get and cross-reference the data
4. Only insert values that are corroborated by both sources
5. Fill in ONLY empty cells — do NOT modify any cell that already has a value
6. Save all files when done

IMPORTANT: Only fill empty cells. Do NOT edit, overwrite, or modify any pre-existing data. All numeric values must be fully written out (e.g., 394328000000 not 394.33B)."""

        messages = [{"role": "user", "content": user_message}]

        # Run the agent loop
        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                print(f"\n--- Agent iteration {iteration} ---")

                response = client.messages.create(
                    model="claude-opus-4-6",
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
