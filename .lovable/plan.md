

## Add Kimi K2.5 as Configurable LLM in Modal Agent

### Overview
Make the agent LLM switchable between Claude Sonnet 4.5 and Moonshot Kimi K2.5 via an environment variable. Kimi uses an OpenAI-compatible API with thinking mode enabled, requiring tool format conversion and reasoning context preservation.

### Changes

**1. `modal-app/requirements.txt`** -- Add OpenAI SDK
- Add `openai>=1.30.0` for Kimi's OpenAI-compatible API

**2. `modal-app/app.py`** -- Add Moonshot secret
- Add `modal.Secret.from_name("moonshot-secret")` to the secrets list (expects `MOONSHOT_API_KEY`)

**3. `modal-app/agent/orchestrator.py`** -- Core refactor

The main changes:

- **Model selection via env var**: Read `AGENT_LLM` env var (default `"claude"`). When set to `"kimi"`, use the OpenAI SDK pointed at `https://api.moonshot.ai/v1` with model `kimi-k2.5`
- **Tool format conversion**: Create a helper that converts the existing Anthropic `input_schema` tool definitions to OpenAI `parameters` format (just a key rename per tool)
- **Thinking mode**: Enable `thinking=True` in the Kimi request; set `max_tokens=30000`
- **Reasoning context preservation**: When appending assistant messages to conversation history for Kimi, include `reasoning_content` from `response.choices[0].message` so multi-turn tool calling works correctly
- **Response parsing**: Map Kimi's OpenAI-style `tool_calls` response back to the same `handle_tool_call` function -- extract `function.name` and `json.loads(function.arguments)` instead of Anthropic's `block.name` / `block.input`
- **Stop condition**: Check `finish_reason == "stop"` (OpenAI) instead of `stop_reason == "end_turn"` (Anthropic)
- **tool_choice**: Set to `"auto"` (the only option with Kimi thinking mode)

### Technical Detail -- Conversation History for Kimi

```text
Anthropic format:
  messages.append({"role": "assistant", "content": [ToolUseBlock, ...]})
  messages.append({"role": "user", "content": [{"type": "tool_result", ...}]})

Kimi (OpenAI) format:
  messages.append({"role": "assistant", "content": text, "reasoning_content": reasoning, "tool_calls": [...]})
  messages.append({"role": "tool", "tool_call_id": id, "content": result_str})  # one per tool call
```

### Files Modified

| File | Change |
|------|--------|
| `modal-app/requirements.txt` | Add `openai>=1.30.0` |
| `modal-app/app.py` | Add `moonshot-secret` to secrets list, add `AGENT_LLM` param to `process_ticker` and `webhook` |
| `modal-app/agent/orchestrator.py` | Add Kimi client init, tool format converter, dual-path LLM call + response parsing in the iteration loop, 30k max tokens for Kimi |

### Secret Setup
You'll need to create a Modal secret called `moonshot-secret` with key `MOONSHOT_API_KEY`. To switch models, set the `AGENT_LLM` env var to `"kimi"` (or pass it through the webhook payload). Default remains `"claude"`.

### Risk
- Low risk to existing Claude path -- it remains the default and its code path is untouched
- Kimi's thinking tokens count toward max_tokens; 30k provides ample headroom
- The tool definitions are functionally identical, just different key names

