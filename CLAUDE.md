# CLAUDE.md — AgentGuard: Pre-Execution Risk Scorer for Agentic AI Actions

## Why This Project Exists

On December 15, 2025, Amazon's internal AI coding agent (Kiro) triggered a 13-hour
AWS outage by autonomously deleting a production environment. The two-person approval
process that existed for human engineers did not apply to AI agents.

AgentGuard solves this: a microservice that intercepts LLM agent tool calls BEFORE
execution, scores them by blast radius, and enforces human approval gates only on
high-risk operations — without slowing down low-risk read-only actions.

## Architecture

One deterministic pipeline, plus an optional Claude explanation layer on top.

### The pipeline (pipeline_direct.py) — always runs
- Pure Python rule-based risk scoring
- Fully deterministic — same input always produces same output
- Zero API calls, zero latency overhead on read-only actions
- Action -> RiskScorer -> BlastRadius -> ApprovalGate -> AuditLogger

### Claude explanation layer (claude_explainer.py) — optional
- NOT a pipeline. Takes the pipeline's output + an API key and asks Claude to
  explain the pre-computed scores in plain English for an engineering manager
- Claude NEVER recalculates scores — it only receives pre-computed values
- HallucinationGuard verifies every numerical claim Claude makes
- Model: claude-sonnet-5 (see CLAUDE_MODEL in claude_explainer.py)
- Enabled by a checkbox in the dashboard; the REST API is deterministic-only

### Surfaces
- app.py — Streamlit dashboard for interactive exploration (+ optional Claude layer)
- api.py — FastAPI service: POST /score (single action), POST /score/batch
  (full pipeline), GET /health. Run with `uvicorn api:app`.
- examples/guarded_agent.py — reference Anthropic tool-use loop that calls the
  gate (in-process or via AGENTGUARD_URL) before executing each tool; blocked
  calls come back to Claude as an is_error tool_result.
- pipeline_direct.score_one(action_dict) — the shared gate contract used by the
  API, the example, and any embedding code: {action, classification, gate, allowed}.

## What This Project Does NOT Do

- It does NOT replace human judgment on critical actions
- It does NOT claim to prevent all AI-caused outages
- It does NOT store API keys (entered in dashboard, never written to disk)
- Claude receives structured JSON, not raw action strings — preventing prompt injection

## File Structure

- app.py                     Streamlit dashboard (entry point)
- api.py                     FastAPI microservice — HTTP wrapper over the direct pipeline
- pipeline_direct.py         The pipeline — deterministic, no LLM (score_one / run)
- claude_explainer.py        Optional Claude explanation layer (not a pipeline)
- examples/
  - guarded_agent.py         Anthropic tool-use loop with AgentGuard as the gate
- modules/
  - risk_scorer.py           Core blast radius classifier (OOP, data structures)
  - approval_gate.py         Human-in-loop enforcement logic + priority queue
  - audit_logger.py          Structured audit trail (DynamoDB-compatible JSON)
  - hallucination_guard.py   Verifies Claude's numerical claims against source
- data/
  - sample_actions.json      Test action sequences
- tests/                     pytest unit tests (~99% module coverage)
  - test_risk_scorer.py      Trie, scoring tables, full classification
  - test_approval_gate.py    Gate state machine + priority queue ordering
  - test_audit_logger.py     Singleton logger, ordered dict, summary aggregation
  - test_hallucination_guard.py  Numeric claim extraction and verification
  - test_claude_explainer.py  Explanation layer with the Anthropic client mocked
  - test_api.py              FastAPI endpoints (TestClient)
  - test_guarded_agent.py    Agent loop gates and blocks tool calls (Anthropic mocked)
- Dockerfile                 Container definition
- docker-compose.yml         Local orchestration (dashboard + api)
- .github/workflows/ci.yml   GitHub Actions CI/CD
- requirements.txt
- CLAUDE.md                  This file
- CONTEXT.md                 Data sources and methodology

## OOP Design Principles Used

- Action class (data structure with type, target, parameters, metadata)
- RiskScorer class (strategy pattern — rule-based + LLM modes)
- ApprovalGate class (state machine: PENDING -> APPROVED/BLOCKED)
- AuditLogger class (singleton pattern — one log per session)
- HallucinationGuard class (verifier pattern)

## Data Structures Used

- Trie (PrefixTrie) for O(k) action prefix matching (get_ / delete_ / recreate_)
- Priority queue (heapq) in ApprovalGate — pending/blocked decisions served
  highest blast radius first, ties by arrival order (ApprovalGate.next_pending)
- Ordered dict (collections.OrderedDict) for the audit log, keyed by insertion
  sequence so replay order is preserved
- Frozen dataclass for immutable Action records

## Algorithm Complexity

- Risk scoring: O(1) per action (hash lookup + trie prefix match)
- Audit log write: O(1) amortized
- Hallucination guard: O(n) where n = number of numerical claims in Claude output
