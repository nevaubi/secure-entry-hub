

## Reduce Claude Token Usage

### The Problem

The full Excel schema (all cell values for the entire file) is embedded in the `system` prompt, which gets sent on **every** Claude API call -- up to 15 times per file. For a 50-row x 12-column file, that's ~600 cell values repeated every iteration, adding up to massive input token waste.

### Changes

All changes are in `modal-app/agent/orchestrator.py`.

#### 1. Move schema from system prompt to first user message

Currently `build_file_system_prompt` includes the full schema + empty cells list in the system prompt (lines 245-249). This is re-sent every iteration.

**Fix**: Split the prompt into two parts:
- **System prompt** (`build_file_system_prompt`): Keep only the workflow rules, instructions, and new-column detection -- remove `full_schema` and `empty_cells` content
- **First user message** (line 644): Include the full schema and empty cells here instead

Since Claude's message history accumulates, the schema from the first message is already visible on all subsequent iterations -- no need to repeat it.

#### 2. Remove `updated_schema` from insertion tool result

After `insert_new_period_column`, the handler (lines 468-475) re-analyzes the file and stuffs the entire refreshed schema into the tool result. This persists in message history for all remaining iterations.

**Fix**: Remove the `updated_schema` injection. The `row_map` already returned by the insertion tool tells the agent exactly which cells to fill -- the full grid is redundant.

#### 3. Reduce `max_tokens` for non-first iterations

The agent uses `max_tokens=8192` on every call (line 655). After the first iteration where it plans its approach, subsequent iterations are mostly tool calls that need far fewer output tokens.

**Fix**: Use 8192 for iteration 1, 4096 for subsequent iterations.

#### 4. Switch Perplexity from `sonar-pro` to `sonar`

Line 492 uses `sonar-pro`, the most expensive model. For simple financial data lookups, `sonar` is sufficient.

### Estimated Token Savings

| Change | Savings |
|---|---|
| Schema in first message only (not system prompt) | 60-80% reduction in Claude input tokens |
| Remove updated_schema from tool result | 5-10K tokens per insertion file |
| Lower max_tokens after iteration 1 | Minor output token savings |
| Switch to sonar | Lower Perplexity cost per query |

### Technical Details

**System prompt change**: `build_file_system_prompt` will no longer accept `full_schema` or `empty_cells` params. It keeps: ticker, file name, file index, browse params, new column detection, scratchpad summary, and workflow instructions.

**First message change** (line 644): The initial user message becomes:
```python
messages = [{
    "role": "user",
    "content": f"Begin processing {file_name} for {ticker}. Report date: {report_date}, timing: {timing}.\n\n"
               f"COMPLETE FILE DATA:\n{full_schema}\n\n"
               f"EMPTY CELLS NEEDING DATA ({len(empty_cells)} total):\n{', '.join(empty_cells) if empty_cells else 'None'}"
}]
```

**Tool result change** (lines 468-475): Remove the try/except block that calls `analyze_excel_file_full` and sets `result["updated_schema"]`.

**max_tokens change** (line 655): 
```python
max_tokens = 8192 if iteration == 1 else 4096
```

**Perplexity model** (line 492): Change `"sonar-pro"` to `"sonar"`.

