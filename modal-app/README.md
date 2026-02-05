 # Excel Agent - Modal Application
 
 This Modal application processes financial Excel files using an AI agent powered by Claude.
 
 ## Architecture
 
 1. **Webhook Endpoint**: Receives requests from Lovable's Edge Functions
 2. **Process Ticker**: Main function that handles each ticker
 3. **Agent Orchestrator**: Claude-powered agent that coordinates the workflow
 4. **Browser Automation**: Playwright-based extraction from StockAnalysis.com
 5. **Excel Updates**: openpyxl-based file modifications
 
 ## Setup
 
 ### 1. Install Modal CLI
 
 ```bash
 pip install modal
 modal setup
 ```
 
 ### 2. Create Modal Secrets
 
 Create the following secrets in your Modal dashboard (https://modal.com/secrets):
 
 **anthropic-secret:**
 ```
 ANTHROPIC_API_KEY=sk-ant-...
 ```
 
 **stockanalysis-secret:**
 ```
 STOCKANALYSIS_USERNAME=your-email@example.com
 STOCKANALYSIS_PASSWORD=your-password
 ```
 
 **supabase-external-secret:**
 ```
 EXTERNAL_SUPABASE_URL=https://your-project.supabase.co
 EXTERNAL_SUPABASE_SERVICE_KEY=eyJ...
 ```
 
 **modal-webhook-secret:**
 ```
 MODAL_WEBHOOK_SECRET=your-shared-secret
 ```
 
 ### 3. Deploy the Application
 
 ```bash
 cd modal-app
 modal deploy app.py
 ```
 
 After deployment, Modal will provide a webhook URL like:
 ```
 https://your-username--excel-agent-webhook.modal.run
 ```
 
 ### 4. Configure Lovable
 
 Add the Modal webhook URL to Lovable secrets:
 - `MODAL_WEBHOOK_URL`: The webhook URL from step 3
 
 ## Testing
 
 ### Test a single ticker locally:
 
 ```bash
 modal run app.py::test_single_ticker --ticker AAPL
 ```
 
 ### Test the webhook:
 
 ```bash
 curl -X POST https://your-username--excel-agent-webhook.modal.run \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer YOUR_WEBHOOK_SECRET" \
   -d '{
     "tickers": [
       {"ticker": "AAPL", "report_date": "2024-01-25", "timing": "afterhours"}
     ],
     "callback_url": null
   }'
 ```
 
 ## File Structure
 
 ```
 modal-app/
 ├── app.py              # Modal app definition with webhook and process_ticker
 ├── agent/
 │   ├── __init__.py
 │   ├── orchestrator.py # Claude agent loop
 │   ├── schema.py       # Excel file analysis
 │   ├── browser.py      # Playwright StockAnalysis scraper
 │   ├── updater.py      # Excel cell updates
 │   └── storage.py      # Supabase storage client
 ├── tools/
 │   └── __init__.py
 ├── requirements.txt
 └── README.md
 ```
 
 ## How It Works
 
 1. **Trigger**: Lovable's `trigger-excel-agent` Edge Function calls the webhook
 2. **Parallel Processing**: Modal spawns a function for each ticker
 3. **Download**: Files are downloaded from external Supabase storage
 4. **Analysis**: Claude analyzes each Excel file's schema
 5. **Data Gathering**: Playwright logs into StockAnalysis.com and extracts data
 6. **Updates**: Claude determines which cells to update and makes the changes
 7. **Upload**: Modified files are uploaded back to storage
 8. **Callback**: Results are reported back to Lovable
 
 ## Cost Estimates
 
 Per ticker (typical):
 - Modal compute: ~$0.03 (5 min @ $0.40/hour)
 - Anthropic API: ~$0.10 (10 calls)
 - Total: ~$0.13/ticker
 
 For 15 tickers/day: ~$2/day