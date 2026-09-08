"""
AgentGuard REST API — FastAPI microservice.

Wraps the deterministic direct pipeline so an agent runtime (or a sidecar proxy
in front of a tool executor) can score a tool call over HTTP *before* it runs.

Run locally:

    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /health         liveness probe
    POST /score          score a single action, return the gate decision
    POST /score/batch    run the full pipeline over a sequence of actions
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

import pipeline_direct
from modules.approval_gate import ApprovalGate
from modules.audit_logger import AuditLogger
from modules.risk_scorer import Action, RiskScorer

app = FastAPI(
    title="AgentGuard",
    version="1.0.0",
    description="Pre-execution risk scorer for agentic AI actions.",
)

# RiskScorer is stateless once constructed (the prefix Trie is built in __init__),
# so a single instance is safe to share across requests.
_scorer = RiskScorer()


class ActionIn(BaseModel):
    name: str = Field(..., examples=["delete_table"])
    target: str = Field(..., examples=["prod-database"])
    agent_id: str = Field("unknown", examples=["kiro-agent-01"])
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class ScoreOut(BaseModel):
    action: dict
    classification: dict
    gate: dict
    allowed: bool


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "agentguard", "version": app.version}


@app.post("/score", response_model=ScoreOut)
def score(action_in: ActionIn) -> ScoreOut:
    """Score one action and return whether it may execute autonomously."""
    action = Action(
        name=action_in.name,
        target=action_in.target,
        agent_id=action_in.agent_id,
        parameters=action_in.parameters,
        description=action_in.description,
        timestamp=datetime.datetime.now().isoformat(),
    )
    classification = _scorer.classify(action)
    decision = ApprovalGate(simulate_approval=True).evaluate(classification).to_dict()
    return ScoreOut(
        action=action.to_dict(),
        classification=classification,
        gate=decision,
        allowed=decision["passed"],
    )


@app.post("/score/batch")
def score_batch(actions: list[ActionIn]) -> dict:
    """Run the full direct pipeline over a sequence of actions (with audit summary)."""
    AuditLogger.reset()
    return pipeline_direct.run([a.model_dump() for a in actions])
