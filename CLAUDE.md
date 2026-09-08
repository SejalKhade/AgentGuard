# CLAUDE.md — AgentGuard: Pre-Execution Risk Scorer for Agentic AI Actions

## Why This Project Exists

On December 15, 2025, Amazon's internal AI coding agent (Kiro) triggered a 13-hour
AWS outage by autonomously deleting a production environment. The two-person approval
process that existed for human engineers did not apply to AI agents.

AgentGuard solves this: a microservice that intercepts LLM agent tool calls BEFORE
execution, scores them by blast radius, and enforces human approval gates only on
high-risk operations — without slowing down low-risk read-only actions.

## Architecture

Two pipelines:

### Pipeline 1: Direct Pipeline (No LLM)
- Pure Python rule-based risk scoring
- Fully deterministic — same input always produces same output
- Zero API calls, zero latency overhead on read-only actions
- Action -> RiskScorer -> BlastRadius -> ApprovalGate -> AuditLogger

### Pipeline 2: Claude-Augmented Pipeline
- Runs direct pipeline first (scores are never delegated to Claude)
- Claude INTERPRETS the risk score and explains it in plain English
- Claude NEVER recalculates scores — it only receives pre-computed values
- HallucinationGuard verifies every numerical claim Claude makes

## What This Project Does NOT Do

- It does NOT replace human judgment on critical actions
- It does NOT claim to prevent all AI-caused outages
- It does NOT store API keys (entered in dashboard, never written to disk)
- Claude receives structured JSON, not raw action strings — preventing prompt injection

## File Structure

- app.py                     Streamlit dashboard (entry point)
- pipeline_direct.py         Pipeline 1 — deterministic, no LLM
- pipeline_claude.py         Pipeline 2 — Claude-augmented interpretation
- modules/
  - risk_scorer.py           Core blast radius classifier (OOP, data structures)
  - approval_gate.py         Human-in-loop enforcement logic
  - audit_logger.py          Structured audit trail (DynamoDB-compatible JSON)
  - hallucination_guard.py   Verifies Claude's numerical claims against source
- data/
  - sample_actions.json      Test action sequences
- tests/
  - test_risk_scorer.py      pytest unit tests (90%+ coverage target)
  - test_approval_gate.py    pytest tests for gate logic
- Dockerfile                 Container definition
- docker-compose.yml         Local orchestration
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

- Trie for O(1) action prefix matching (read_ / delete_ / recreate_)
- Priority queue for pending approval requests (highest blast radius first)
- Ordered dict for audit log (insertion order preserved)
- Frozen dataclass for immutable Action records

## Algorithm Complexity

- Risk scoring: O(1) per action (hash lookup + trie prefix match)
- Audit log write: O(1) amortized
- Hallucination guard: O(n) where n = number of numerical claims in Claude output
