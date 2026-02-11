

## Hardcode Kimi K2.5 as the Agent LLM

### Overview
Remove the `AGENT_LLM` environment variable toggle and hardcode the orchestrator to always use Moonshot Kimi K2.5. This simplifies the code by removing the dual-path logic.

### Changes

**1. `modal-app/agent/orchestrator.py`**
- Remove the `AGENT_LLM` env var check and all Claude/Anthropic SDK call paths
- Always initialize the OpenAI client pointed at `https://api.moonshot.ai/v1`
- Always use `model="kimi-k2.5"`, `thinking=True`, `max_tokens=30000`
- Remove the Anthropic client import and initialization (keep only OpenAI)
- Clean up any if/else branching between Claude and Kimi -- only the Kimi path remains

**2. `modal-app/app.py`**
- Remove `AGENT_LLM` parameter passing
- Keep `moonshot-secret` in the secrets list
- Optionally remove `anthropic-secret` from secrets if no other code uses it (will verify during implementation)

**3. `modal-app/requirements.txt`**
- Keep `openai>=1.30.0`
- Optionally remove `anthropic` if nothing else imports it (will verify)

### Result
Cleaner, single-path orchestrator that always uses Kimi K2.5. No env vars to manage.

