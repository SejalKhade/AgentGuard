# CONTEXT.md — AgentGuard Methodology and Data Sources

## The Problem This Solves

### Incident Timeline (Public Sources)
- Dec 15, 2025: AWS Kiro agent deleted production Cost Explorer environment (China region)
  Duration: 13 hours | Source: Financial Times, February 2026
- March 2026: Amazon retail storefront outage (~6 hours, 99% drop in US orders)
  Source: Multiple news outlets, Amazon incident reports

### Why Existing Guardrails Failed
1. Two-person approval existed for HUMAN engineers — not enforced for AI agents
2. AI agents inherited the FULL permission set of the sponsoring engineer
3. Speed asymmetry: agent completed deletion faster than a human could intervene
4. No pre-execution risk classification existed at the action level

### Industry Context
- 18% of security leaders confident their IAM manages agent identities (Particula Tech, 2026)
- 60%+ of dev teams cite trust and failure handling as constraints to agentic AI adoption
- Only 21% maintain real-time inventory of active AI agents in their environment

## AgentGuard Risk Classification System

### Blast Radius Tiers

| Tier | Label | Description | Gate Required |
|------|-------|-------------|---------------|
| 0 | READ_ONLY | No state change. Safe to execute autonomously. | None |
| 1 | REVERSIBLE | State change that can be undone. Low risk. | None |
| 2 | DESTRUCTIVE | Permanent data loss possible. Requires review. | Human approval |
| 3 | CATASTROPHIC | Production-wide impact. Multi-person review. | Senior + Peer |

### Classification Formula (Transparent)

```
blast_radius = max(
    prefix_score(action.name),      # Trie lookup on action prefix
    target_score(action.target),    # Production vs staging vs dev
    scope_score(action.parameters)  # Single record vs table vs environment
)

risk_score (0-100) = (blast_radius / 3) * 100

gate_required = blast_radius >= 2      # DESTRUCTIVE or CATASTROPHIC (risk_score >= 66.7)
```

### Prefix Scoring Table (Source: AWS IAM action taxonomy)

| Prefix | Score | Examples |
|--------|-------|---------|
| get_, list_, describe_, fetch_ | 0 | get_records, list_users |
| update_, modify_, patch_, put_ | 1 | update_config, modify_policy |
| create_, add_, insert_ | 1 | create_bucket, add_user |
| delete_, remove_, drop_, detach_, revoke_ | 2 | delete_table, remove_user |
| terminate_, destroy_, wipe_, unlink_ | 2 | terminate_instance |
| recreate_, rebuild_, reset_prod, restore_from | 3 | recreate_environment |
| delete_all, wipe_all, truncate_ | 3 | delete_all_records |

### Target Environment Scoring

| Target contains | Score |
|-----------------|-------|
| dev, test, local, sandbox, mock | 0 |
| staging, uat, qa, preprod, pre-prod | 1 |
| prod, production, live, prd, release | 2 |
| global, multi, all-region | 3 |

The highest-scoring keyword found in the target wins; the matched keyword is
recorded even when its score is 0 (so `dev-environment` reports `dev`, not `none`).

## Hallucination Guard Methodology

Claude receives pre-computed risk scores as structured JSON.
Claude CANNOT invent scores — they come from Python only.

Verification checks:
1. Extract all numbers from Claude's text using regex
2. Compare each against source pipeline JSON within 5% tolerance
3. VERIFIED: within 5% | APPROXIMATION: 5-15% | UNVERIFIED: >15% or not found
4. Reliability score = (verified + approximation*0.5) / total * 100

## What AgentGuard Does NOT Claim

- It is not a replacement for proper IAM/RBAC design
- It does not prevent all possible agentic failures
- Prefix-based scoring is a heuristic — not a formal verification system
- The system works best as ONE layer in a defense-in-depth strategy
