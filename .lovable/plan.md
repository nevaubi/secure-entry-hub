

## Add Temperature Parameter to Kimi K2.5 API Call

### Change

**File: `modal-app/agent/orchestrator.py`**

Add `temperature=0.3` to the `llm_client.chat.completions.create()` call alongside the existing parameters (`model`, `max_tokens`, `messages`, `tools`, `tool_choice`, `thinking`).

Single line addition, no other files affected.

