# Examples

## `guarded_agent.py` — AgentGuard as a pre-execution gate in an agent loop

A real Anthropic tool-use loop where **every tool call is scored by AgentGuard
before it runs**. Safe calls execute; destructive/catastrophic calls are refused
and the denial is returned to Claude as an error `tool_result`, so the agent
adapts instead of performing the dangerous action.

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# score in-process
python examples/guarded_agent.py

# or score over HTTP against a running service
uvicorn api:app --port 8000 &
AGENTGUARD_URL=http://localhost:8000 python examples/guarded_agent.py
```

The demo task asks the agent to scale a deployment, delete a stale one, and
rebuild a production environment. Expected transcript:

```
  [ALLOWED]  list_deployments       Reversible
  [ALLOWED]  scale_deployment       Reversible
  [BLOCKED]  delete_deployment      Destructive   — 1 human approver required ...
  [BLOCKED]  recreate_environment   Catastrophic  — matches the Kiro incident pattern ...

--- agent's final answer ---
I scaled api to 5 replicas. The delete and the production rebuild were blocked by
AgentGuard and need human approval, so I did not perform them.
```

The wiring is ~15 lines: map the tool call to an action, call `guard_check()`,
and on `allowed: false` return `{"is_error": true, ...}` instead of executing.
See `tests/test_guarded_agent.py` for the same flow with the Anthropic client mocked.
