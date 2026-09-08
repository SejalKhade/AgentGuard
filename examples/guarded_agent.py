"""
Example: an Anthropic tool-use loop with AgentGuard as a pre-execution gate.

Every tool call Claude makes is scored by AgentGuard BEFORE it runs. Read-only and
reversible calls execute; destructive and catastrophic calls are refused and the
denial is returned to Claude as an error tool_result, so the agent adapts instead
of performing the dangerous action.

    python examples/guarded_agent.py
    AGENTGUARD_URL=http://localhost:8000 python examples/guarded_agent.py   # gate via the REST API

Needs ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import anthropic

from claude_explainer import CLAUDE_MODEL
from pipeline_direct import score_one

# If set, the gate check goes over HTTP to a running `uvicorn api:app`.
# Otherwise it is scored in-process via the same code path.
AGENTGUARD_URL = os.environ.get("AGENTGUARD_URL")


# ── AgentGuard gate ───────────────────────────────────────────────────────────
def guard_check(tool_name: str, tool_input: dict) -> dict:
    """Score a pending tool call. Returns AgentGuard's /score payload."""
    action = {
        "name": tool_name,
        "target": (tool_input.get("target") or tool_input.get("env")
                   or tool_input.get("resource") or ""),
        "agent_id": "guarded-agent-example",
        "parameters": {k: v for k, v in tool_input.items()
                       if k not in ("target", "env", "resource")},
    }
    if AGENTGUARD_URL:
        req = urllib.request.Request(
            f"{AGENTGUARD_URL.rstrip('/')}/score",
            data=json.dumps(action).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    return score_one(action)


# ── Demo tools (stand-ins for real infrastructure calls) ──────────────────────
TOOLS = [
    {
        "name": "list_deployments",
        "description": "List the deployments running in an environment.",
        "input_schema": {
            "type": "object",
            "properties": {"env": {"type": "string"}},
            "required": ["env"],
        },
    },
    {
        "name": "scale_deployment",
        "description": "Change the replica count of a deployment (reversible).",
        "input_schema": {
            "type": "object",
            "properties": {
                "env": {"type": "string"},
                "name": {"type": "string"},
                "replicas": {"type": "integer"},
            },
            "required": ["env", "name", "replicas"],
        },
    },
    {
        "name": "delete_deployment",
        "description": "Permanently delete a deployment.",
        "input_schema": {
            "type": "object",
            "properties": {"env": {"type": "string"}, "name": {"type": "string"}},
            "required": ["env", "name"],
        },
    },
    {
        "name": "recreate_environment",
        "description": "Tear down and rebuild an entire environment from scratch.",
        "input_schema": {
            "type": "object",
            "properties": {"env": {"type": "string"}, "force": {"type": "boolean"}},
            "required": ["env"],
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Pretend to perform the infrastructure action."""
    return {
        "list_deployments": f"{args.get('env')} deployments: api, worker, cache",
        "scale_deployment": (f"scaled {args.get('name')} to {args.get('replicas')} "
                             f"replicas in {args.get('env')}"),
        "delete_deployment": f"deleted {args.get('name')} from {args.get('env')}",
        "recreate_environment": f"recreated {args.get('env')}",
    }.get(name, "ok")


# ── Guarded agent loop ────────────────────────────────────────────────────────
def run(task: str, *, api_key: str | None = None, max_turns: int = 8) -> list[dict]:
    """Run the agent loop. Returns a list of events (allowed / blocked / final)."""
    client = anthropic.Anthropic(api_key=api_key)
    messages: list[dict] = [{"role": "user", "content": task}]
    events: list[dict] = []

    for _ in range(max_turns):
        resp = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=1024, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content
                           if getattr(b, "type", None) == "text").strip()
            events.append({"type": "final", "text": text})
            return events

        tool_results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            verdict = guard_check(block.name, block.input)
            label = verdict["classification"]["blast_label"]
            gate = verdict["gate"]

            if verdict["allowed"]:
                events.append({"type": "allowed", "tool": block.name, "blast": label})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": execute_tool(block.name, block.input),
                })
            else:
                events.append({"type": "blocked", "tool": block.name,
                               "blast": label, "reason": gate["reason"]})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": (
                        f"BLOCKED by AgentGuard: {gate['status']} — {label}, "
                        f"{gate['approvers_needed']} human approver(s) required. "
                        f"{gate['reason']} Do not retry; a human must approve this."
                    ),
                })

        messages.append({"role": "user", "content": tool_results})

    events.append({"type": "final", "text": "(max turns reached)"})
    return events


if __name__ == "__main__":
    task = (
        "Tidy up our environments. Please: "
        "(1) list what is deployed in staging, "
        "(2) scale the 'api' deployment in staging to 5 replicas, "
        "(3) delete the stale 'worker' deployment in staging, and "
        "(4) rebuild the production 'prod-cost-explorer' environment from scratch "
        "to pick up new config. Do whatever you're able to."
    )

    print(f"gate: {'REST API ' + AGENTGUARD_URL if AGENTGUARD_URL else 'in-process'}\n")
    for e in run(task):
        if e["type"] == "allowed":
            print(f"  [ALLOWED]  {e['tool']:22} {e['blast']}")
        elif e["type"] == "blocked":
            print(f"  [BLOCKED]  {e['tool']:22} {e['blast']}  — {e['reason'][:78]}...")
        else:
            print("\n--- agent's final answer ---")
            print(e["text"])
