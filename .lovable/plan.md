

## Implementation Plan: Agentic Excel Processing with Modal + Anthropic

### Overview

Build a production-grade agentic system that processes 12 Excel files per ticker, dynamically understanding each file's unique schema, browsing financial data sources (web search + StockAnalysis.com), and updating the files with accurate values.

---

### Architecture

```text
                    LOVABLE CLOUD                              MODAL.COM
                    ─────────────                              ─────────
                         │
    ┌────────────────────┴────────────────────┐
    │                                         │
    │   Cron Triggers                         │
    │   8:15 AM CT (premarket)                │
    │   5:30 PM CT (afterhours)               │
    │                                         │
    └────────────────────┬────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────┐
    │  Edge Function: trigger-excel-agent     │
    │  ─────────────────────────────────────  │
    │  1. Query earnings_calendar             │
    │  2. Filter by timing (pre/after)        │
    │  3. POST to Modal webhook               │
    │     with ticker list                    │
    └────────────────────┬────────────────────┘
                         │
                         │ HTTPS POST
                         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     MODAL.COM                                   │
    │  ───────────────────────────────────────────────────────────── │
    │                                                                 │
    │  ┌───────────────────────────────────────────────────────────┐ │
    │  │  @app.function()                                          │ │
    │  │  process_ticker(ticker: str)                              │ │
    │  │  ────────────────────────────────────                     │ │
    │  │                                                           │ │
    │  │  PHASE 1: SCHEMA DISCOVERY                                │ │
    │  │  ├─ Download 12 Excel files from external storage         │ │
    │  │  ├─ Parse each file with openpyxl                         │ │
    │  │  └─ Feed structure to Anthropic for understanding         │ │
    │  │                                                           │ │
    │  │  PHASE 2: DATA GATHERING (Agentic)                        │ │
    │  │  ├─ AI determines what data is needed                     │ │
    │  │  ├─ Web search for recent financials                      │ │
    │  │  ├─ Playwright browser: StockAnalysis.com                 │ │
    │  │  │   ├─ Login with saved credentials                      │ │
    │  │  │   ├─ Navigate to ticker financial pages                │ │
    │  │  │   └─ Extract income/balance/cashflow data              │ │
    │  │  └─ AI reconciles data from multiple sources              │ │
    │  │                                                           │ │
    │  │  PHASE 3: UPDATE & SAVE                                   │ │
    │  │  ├─ AI maps data to correct cells in each file            │ │
    │  │  ├─ Update Excel files with openpyxl                      │ │
    │  │  └─ Upload files back to external storage                 │ │
    │  │                                                           │ │
    │  │  PHASE 4: REPORT                                          │ │
    │  │  └─ POST status back to Lovable edge function             │ │
    │  └───────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  Parallel execution: .map() across all tickers                  │
    └─────────────────────────────────────────────────────────────────┘
```

---

### Component Details

#### 1. Secrets Required

| Secret Name | Purpose | Where Used |
|-------------|---------|------------|
| `ANTHROPIC_API_KEY` | Claude API for agentic reasoning | Modal |
| `STOCKANALYSIS_USERNAME` | StockAnalysis.com login | Modal |
| `STOCKANALYSIS_PASSWORD` | StockAnalysis.com login | Modal |
| `MODAL_WEBHOOK_SECRET` | Secure webhook authentication | Edge Function + Modal |

---

#### 2. Edge Function: `trigger-excel-agent`

A lightweight orchestrator that queries the database and triggers Modal:

- Query `earnings_calendar` for tickers by timing
- Query `earnings_file_processing` for file availability status
- POST ticker list to Modal webhook endpoint
- Log processing start to a new `excel_processing_runs` table

---

#### 3. Modal Application Structure

```text
excel-agent/
├── app.py              # Modal app definition
├── agent/
│   ├── __init__.py
│   ├── schema.py       # Excel schema analysis with Claude
│   ├── browser.py      # Playwright browser automation
│   ├── search.py       # Web search integration
│   ├── updater.py      # Excel file update logic
│   └── storage.py      # External Supabase storage client
├── tools/
│   ├── __init__.py
│   ├── web_search.py   # Web search tool for Claude
│   ├── browse.py       # Browser action tool for Claude
│   └── excel.py        # Excel read/write tool for Claude
└── requirements.txt    # openpyxl, anthropic, playwright
```

---

#### 4. Anthropic Agent Design

The agent uses Claude's tool-calling capability with a multi-step workflow:

**System Prompt Context:**
```text
You are a financial data agent. Your task is to:
1. Understand the structure of Excel financial files
2. Identify what data needs to be updated (look for empty cells, outdated dates)
3. Use tools to search the web and browse StockAnalysis.com
4. Update the Excel files with accurate, verified financial data

You have access to these tools:
- analyze_excel: Inspect Excel file structure and contents
- web_search: Search for financial data on the web
- browse_stockanalysis: Navigate and extract data from StockAnalysis.com
- update_excel_cell: Update a specific cell in an Excel file
```

**Tool Definitions:**

| Tool | Description |
|------|-------------|
| `analyze_excel` | Parse Excel file, return sheet names, column headers, sample data, empty cells |
| `web_search` | Search query for financial data (uses Firecrawl or similar) |
| `browse_stockanalysis` | Login, navigate to ticker, extract financial tables |
| `update_excel_cell` | Write value to specific sheet/cell in Excel file |
| `save_all_files` | Upload all modified files back to storage |

---

#### 5. Browser Automation Flow (StockAnalysis.com)

```text
1. Launch Playwright browser (Modal has native support)
2. Navigate to stockanalysis.com/login
3. Enter credentials from environment
4. Go to /stocks/{TICKER}/financials/
5. Extract tables:
   ├─ /income-statement/ (annual + quarterly)
   ├─ /balance-sheet/ (annual + quarterly)
   └─ /cash-flow-statement/ (annual + quarterly)
6. Parse tables into structured data
7. Return to agent for mapping
```

---

#### 6. Database Tables

**New table: `excel_processing_runs`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `ticker` | TEXT | Stock ticker |
| `report_date` | DATE | Earnings date |
| `timing` | TEXT | 'premarket' or 'afterhours' |
| `status` | TEXT | 'pending', 'processing', 'completed', 'failed' |
| `files_updated` | INTEGER | Count of files modified |
| `data_sources_used` | TEXT[] | Array of sources queried |
| `error_message` | TEXT | Error details if failed |
| `started_at` | TIMESTAMPTZ | Processing start time |
| `completed_at` | TIMESTAMPTZ | Processing end time |
| `created_at` | TIMESTAMPTZ | Record creation |

---

### Implementation Steps

#### Phase 1: Infrastructure Setup

1. **Add Secrets to Lovable Cloud**
   - `ANTHROPIC_API_KEY`
   - `STOCKANALYSIS_USERNAME`
   - `STOCKANALYSIS_PASSWORD`
   - `MODAL_WEBHOOK_SECRET`

2. **Create Database Table**
   - Add `excel_processing_runs` for tracking

3. **Create Edge Function**
   - `trigger-excel-agent` to orchestrate Modal calls

---

#### Phase 2: Modal Application Development

4. **Setup Modal Project**
   - Initialize Modal app with Python 3.11
   - Install dependencies: `openpyxl`, `anthropic`, `playwright`
   - Configure browser image with Playwright

5. **Implement Storage Client**
   - Download/upload files from external Supabase storage
   - Handle authentication with service key

6. **Implement Browser Automation**
   - StockAnalysis.com login flow
   - Financial data extraction from ticker pages
   - Error handling for rate limits/captchas

7. **Build Agent Tools**
   - `analyze_excel`: Dynamic schema understanding
   - `web_search`: Financial data lookup
   - `browse_stockanalysis`: Authenticated browsing
   - `update_excel_cell`: Precise cell updates

8. **Create Agent Orchestrator**
   - Claude conversation loop with tool calling
   - Context window management for large Excel files
   - Retry logic and error recovery

---

#### Phase 3: Integration

9. **Create Webhook Endpoint in Modal**
   - Receive ticker list from Lovable
   - Spawn parallel processing with `.map()`
   - Report results back

10. **Schedule Cron Jobs**
    - Modify existing crons to call new trigger function
    - Or create new `trigger-excel-agent` crons

---

#### Phase 4: Monitoring & Reliability

11. **Add Status Callback**
    - Modal posts completion status to Lovable
    - Update `excel_processing_runs` table

12. **Dashboard View**
    - Display processing status and history
    - Show success/failure rates per ticker

---

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Excel Library** | openpyxl | Python standard, preserves formatting, supports .xlsx |
| **AI Model** | Claude 3.5 Sonnet | Best for agentic tool-calling, cost-effective |
| **Browser** | Playwright | Modal native support, reliable automation |
| **Parallelism** | Modal .map() | Process 5-30 tickers concurrently |
| **Search** | Firecrawl or Perplexity | Already have connector available |

---

### Cost Estimates (per day, 15 tickers average)

| Component | Est. Cost |
|-----------|-----------|
| Modal compute (15 x 5 min) | ~$0.50 |
| Anthropic API (15 x 10 calls) | ~$1.50 |
| Total | ~$2-3/day |

---

### Files to Create

| File | Purpose |
|------|---------|
| `supabase/functions/trigger-excel-agent/index.ts` | Orchestrator edge function |
| `modal-app/app.py` | Modal application entry |
| `modal-app/agent/schema.py` | Excel schema analysis |
| `modal-app/agent/browser.py` | StockAnalysis automation |
| `modal-app/agent/storage.py` | Supabase storage client |
| `modal-app/tools/*.py` | Claude tool implementations |
| Database migration | `excel_processing_runs` table |

---

### Testing Strategy

1. **Single Ticker Test**: Run agent on one ticker (e.g., AMZN) manually
2. **Schema Flexibility Test**: Process files with different structures
3. **Browser Reliability**: Test login flow and extraction
4. **End-to-End**: Trigger via cron, verify files updated
5. **Error Recovery**: Test with missing files, network failures

---

### Next Steps After Approval

1. Set up the required secrets in Lovable Cloud
2. Create the `excel_processing_runs` database table
3. Build the `trigger-excel-agent` edge function
4. Create the Modal application (provided as code for you to deploy)
5. Wire everything together and test
 
 ---
 
 ## Implementation Progress
 
 ### ✅ Completed
 
 - [x] **Secrets Added**: ANTHROPIC_API_KEY, STOCKANALYSIS_USERNAME, STOCKANALYSIS_PASSWORD, MODAL_WEBHOOK_SECRET
 - [x] **Database Table**: Created `excel_processing_runs` table with RLS
 - [x] **Edge Functions** (deployed): 
   - `trigger-excel-agent`: Orchestrator that queries earnings and triggers Modal
   - `excel-agent-callback`: Receives completion status from Modal
 - [x] **Modal Application**: Complete Python codebase in `modal-app/` directory
   - `app.py`: Modal app with webhook endpoint
   - `agent/orchestrator.py`: Claude agent loop with tool calling
   - `agent/schema.py`: Dynamic Excel schema analysis
   - `agent/browser.py`: Playwright automation for StockAnalysis.com
   - `agent/updater.py`: Excel cell update logic
   - `agent/storage.py`: External Supabase storage client
 
 ### 🔄 Next Steps (User Action Required)
 
 1. **Deploy Modal App**: 
    ```bash
    cd modal-app
    pip install modal
    modal setup  # If not already done
    modal deploy app.py
    ```
 
 2. **Create Modal Secrets** (in Modal Dashboard at https://modal.com/secrets):
    - `anthropic-secret`: `ANTHROPIC_API_KEY=sk-ant-...`
    - `stockanalysis-secret`: `STOCKANALYSIS_USERNAME=...`, `STOCKANALYSIS_PASSWORD=...`
    - `supabase-external-secret`: `EXTERNAL_SUPABASE_URL=...`, `EXTERNAL_SUPABASE_SERVICE_KEY=...`
    - `modal-webhook-secret`: `MODAL_WEBHOOK_SECRET=...` (same value as Lovable secret)
 
 3. **Add Modal Webhook URL to Lovable**: Add `MODAL_WEBHOOK_URL` secret with the URL from Modal deploy
 
 4. **Test Single Ticker**: `modal run app.py::test_single_ticker --ticker AAPL`
 
 5. **Set Up Crons** (optional): Schedule trigger-excel-agent to run at market times

