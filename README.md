# AgentGuard

**Pre-execution risk scorer for agentic AI actions.**

AgentGuard is a microservice that intercepts an LLM agent's tool calls **before**
they execute, scores each one by *blast radius*, and enforces a human approval gate
only on the dangerous ones — while letting read-only and reversible actions through
with zero latency.

---

## Why this exists

On **December 15, 2025**, Amazon's internal AI coding agent (Kiro) autonomously
deleted a production environment (Cost Explorer, China region) and triggered a
**13-hour AWS outage**. A two-person approval process existed for human engineers —
but it was never enforced for AI agents, and the agent inherited the full permission
set of the engineer who launched it.

The core failure wasn't the model. It was that **no system classified the action's
risk before it ran**. "Delete and recreate a production environment" was executed
with the same ceremony as "list S3 buckets."

AgentGuard is that missing layer.

## What it does

- Classifies every agent action into one of four **blast-radius tiers**
- Auto-approves tiers 0–1 (read-only / reversible) with **no API call and no latency**
- Blocks tiers 2–3 (destructive / catastrophic) behind a **human approval gate**
- Emits a **DynamoDB-compatible audit entry** for every action and every gate decision
- Optionally uses **Claude** to explain the risk in plain English — without ever
  letting Claude recalculate a score

## What it does **not** do

- It does **not** replace human judgment on critical actions
- It does **not** claim to prevent every AI-caused outage
- It does **not** store API keys — the key is entered in the dashboard and never
  written to disk
- Claude receives **structured JSON, not raw action strings**, which removes the
  prompt-injection surface

---

## How it works

### Blast-radius tiers

| Tier | Label | Meaning | Gate |
|:----:|-------|---------|------|
| 0 | `READ_ONLY` | No state change | None — runs immediately |
| 1 | `REVERSIBLE` | State change that can be undone | None — logged and allowed |
| 2 | `DESTRUCTIVE` | Permanent data loss possible | 1 human approver |
| 3 | `CATASTROPHIC` | Production-wide impact | 2 approvers (Senior + Peer) |

### The scoring formula (fully transparent)

```
blast_radius = max(
    prefix_score(action.name),       # Trie prefix match: get_/update_/delete_/recreate_ ...
    target_score(action.target),     # dev / staging / prod / global
    scope_score(action.parameters)   # single record vs. "all", "force", "cascade", "recursive"
)

risk_score (0-100) = (blast_radius / 3) * 100
gate_required      = blast_radius >= 2
```

Every classification returns the **full calculation trace** — which of the three
factors dominated, which keyword matched, and which source table it came from — so a
reviewer can audit *why* an action was blocked.

**Worked example — the Kiro action:**

```python
Action(name="recreate_environment",
       target="prod-cost-explorer-china",
       parameters={"force": True, "all": True})

# prefix "recreate_" -> 3   target "prod" -> 2   scope "all" -> 2
# blast_radius = max(3, 2, 2) = 3  ->  CATASTROPHIC, risk_score 100, 2 approvers, BLOCKED
```

### Two pipelines

**Pipeline 1 — Direct (no LLM).** Pure Python, fully deterministic: the same input
always produces the same output. Zero API calls, zero added latency.

```
Action -> RiskScorer -> ApprovalGate -> AuditLogger
```

**Pipeline 2 — Claude-augmented.** Runs the direct pipeline first, then passes the
**pre-computed** scores to Claude (`claude-sonnet-5`) for a plain-English briefing
(action-by-action analysis, Kiro-pattern match, mitigation recommendations). Claude
**never computes or recomputes a score** — and every number in its response is checked
by the `HallucinationGuard`, which extracts each numeric claim via regex and verifies
it against the source pipeline JSON (`VERIFIED` within 5%, `APPROXIMATION` within 15%,
otherwise `UNVERIFIED`).

### Surfaces

| Surface | Entry point | Use |
|---|---|---|
| Dashboard | `streamlit run app.py` | Interactive exploration, full calculation trace |
| REST API | `uvicorn api:app` | Programmatic pre-execution gate for an agent runtime |
| CLI | `python pipeline_direct.py` | Score `data/sample_actions.json`, print JSON |
| Library | `from modules.risk_scorer import RiskScorer` | Embed directly |

---

## Project structure

```
app.py                        Streamlit dashboard (entry point)
api.py                        FastAPI microservice — HTTP wrapper over the direct pipeline
pipeline_direct.py            Pipeline 1 — deterministic, no LLM
pipeline_claude.py            Pipeline 2 — Claude-augmented interpretation
modules/
  risk_scorer.py              Blast-radius classifier (Action, PrefixTrie, RiskScorer)
  approval_gate.py            Human-in-loop state machine + heapq priority queue
  audit_logger.py             Structured audit trail (singleton, DynamoDB-compatible JSON)
  hallucination_guard.py      Verifies Claude's numerical claims against source data
data/
  sample_actions.json         Demo action sequence (includes the exact Kiro action)
tests/                        pytest unit tests (~99% module coverage, 64 tests)
Dockerfile                    Container definition
docker-compose.yml            Local orchestration (dashboard + api)
.github/workflows/ci.yml      CI: tests + coverage gate + API smoke test + Docker build
CONTEXT.md                    Data sources, incident timeline, scoring tables
```

### Design notes

- **`Action`** — frozen dataclass: immutable, hashable, safe to pass across threads
- **`PrefixTrie`** — O(k) prefix matching on the action name (k = prefix length,
  effectively O(1) relative to the ruleset)
- **`RiskScorer`** — strategy-style classifier over three independent factor tables;
  `dominant_factors` reports every factor tied at the winning score
- **`ApprovalGate`** — explicit state machine ("innocent until proven dangerous":
  default allow, block only at tier ≥ 2). Gated decisions land on a `heapq`
  priority queue — `next_pending()` serves the highest blast radius first, ties
  by arrival order
- **`AuditLogger`** — singleton, one `OrderedDict` log per session (keyed by
  insertion sequence), exportable as JSON

---

## Running it

### Dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. The Claude-augmented pipeline needs an Anthropic API key,
entered in the dashboard sidebar (never persisted).

### REST API

```bash
uvicorn api:app --port 8000
```

```bash
# Score one action before an agent executes it
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"name":"recreate_environment","target":"prod-cost-explorer-china",
       "agent_id":"kiro-01","parameters":{"force":true,"all":true}}'
# -> {"allowed": false, "gate": {"status": "BLOCKED", "approvers_needed": 2}, ...}
```

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/health` | — | liveness |
| `POST` | `/score` | one action | classification + gate decision + `allowed` |
| `POST` | `/score/batch` | list of actions | full pipeline output + audit summary |

Interactive docs at `http://localhost:8000/docs`.

### Direct pipeline from the CLI

```bash
python pipeline_direct.py        # scores data/sample_actions.json, prints the full trace
```

### Programmatic use

```python
from modules.risk_scorer import RiskScorer, Action
from modules.approval_gate import ApprovalGate

scorer, gate = RiskScorer(), ApprovalGate()

action = Action(name="delete_table", target="prod-db", agent_id="agent-01",
                parameters={"table_name": "sessions"})

classification = scorer.classify(action)      # -> blast_radius 2, risk_score 66.7
decision = gate.evaluate(classification)       # -> GateStatus.PENDING, 1 approver
if not decision.to_dict()["passed"]:
    raise PermissionError(decision.reason)     # block execution until approved
```

### Docker

```bash
docker compose up --build      # dashboard on :8501, API on :8000
```

or a single service:

```bash
docker build -t agentguard .
docker run -p 8501:8501 agentguard
```

---

## Tests

```bash
pytest tests/ -v --cov=modules --cov-report=term-missing
```

64 tests, ~99% module coverage. CI runs the suite on every push to `main`/`develop`
with an 80% coverage gate, verifies the Kiro action still classifies as
`CATASTROPHIC`, smoke-tests the REST API, and builds the Docker image.

## License

Not currently licensed for redistribution. All rights reserved by the author.
