

## Add Perplexity Web Search as a Co-Equal Data Source

### Goal

Add a `web_search` tool powered by Perplexity's Sonar API that the agent uses **alongside** StockAnalysis.com — not as a fallback, but as a validation partner. The agent should query both sources and cross-reference values before writing anything to a cell.

---

### What changes

**1. New Modal secret: `perplexity-secret`**

You will need to create a secret in your Modal dashboard (modal.com > Settings > Secrets) called `perplexity-secret` with:
- Key: `PERPLEXITY_API_KEY`
- Value: Your Perplexity API key (from perplexity.ai/settings/api)

**2. `modal-app/app.py`**

Add the new secret to the secrets list (line 41):
```python
modal.Secret.from_name("perplexity-secret"),  # PERPLEXITY_API_KEY
```

**3. `modal-app/agent/orchestrator.py` — Three additions:**

**(a) New tool definition** added to the `TOOLS` list (after `save_all_files`):
```python
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
```

**(b) New handler** in `handle_tool_call` (before the `else` branch):
```python
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
```

**(c) Updated SYSTEM_PROMPT** — Revised workflow and new section on dual-source validation:

The workflow steps change from a linear StockAnalysis-only approach to:

```
WORKFLOW:
1. Use analyze_excel to understand the structure of each file you need to update
2. Identify ONLY empty cells that need to be filled in
3. Use BOTH browse_stockanalysis AND web_search to gather financial data
4. Cross-reference values from both sources before writing anything
5. Use update_excel_cell to fill in ONLY empty cells with verified values
6. Call save_all_files when done
```

New section added to the prompt:

```
DUAL-SOURCE VALIDATION:
- You have two equal data sources: browse_stockanalysis and web_search
- For every data point you intend to insert, gather it from BOTH sources
- If both sources agree on a value, use it
- If the sources disagree, investigate further with additional web_search queries
- If you still cannot confirm a value with confidence, leave the cell empty
- This cross-referencing is mandatory — do NOT rely on a single source alone
```

**(d) Updated user message** — Step 3 changes to reflect dual sourcing:

```
3. Use BOTH StockAnalysis.com AND web search to get and cross-reference the data
4. Only insert values that are corroborated by both sources
```

---

### Files modified

| File | Change |
|---|---|
| `modal-app/app.py` | Add `perplexity-secret` to secrets list |
| `modal-app/agent/orchestrator.py` | Add tool definition, handler, and update system/user prompts for dual-source validation |

### Secret setup required

Create `perplexity-secret` in the Modal dashboard with key `PERPLEXITY_API_KEY` before deploying.
