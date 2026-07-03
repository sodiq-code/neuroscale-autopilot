# NeuroScale Autopilot v2 — System Architecture

## Overview

NeuroScale Autopilot v2 is a production-grade Kubernetes SRE agent that combines:
- **Verifiable Trust Layer** — 4-factor scoring algorithm for safe automation
- **Qwen 3.7-Max Thinking Mode** — 1M-token context for deep RCA
- **18-Tool MCP Surface** — Extensible interface for external AI clients
- **Chaos Injection Harness** — 12 reproducible failure scenarios
- **Cost Transparency** — Per-incident cost tracking and budgeting

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    External AI Clients                           │
│         (Claude Desktop, Qwen Code CLI, Custom Agents)           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                    MCP Protocol
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    MCP Server (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 18 Tools: Monitoring, Remediation, Trust, History, Cost │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│  Analyzer    │ │   Planner   │ │  Executor   │
│ (Qwen3-Max)  │ │  (Runbooks) │ │ (kubectl)   │
└───────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │     Trust Score Engine          │
        │  ┌──────────────────────────┐   │
        │  │ • Reversibility (30%)    │   │
        │  │ • Blast Radius (25%)     │   │
        │  │ • Runbook Conf (25%)     │   │
        │  │ • History (20%)          │   │
        │  └──────────────────────────┘   │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Decision & Execution          │
        │  ┌──────────────────────────┐   │
        │  │ EXECUTE (≥90)            │   │
        │  │ DRYRUN_VERIFY (70-89)    │   │
        │  │ ESCALATE_HUMAN (<70)     │   │
        │  └──────────────────────────┘   │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Outcomes Logging              │
        │   (outcomes.jsonl)              │
        └────────────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Data Sources                  │
        │  ┌──────────────────────────┐   │
        │  │ • Prometheus             │   │
        │  │ • Kubernetes API         │   │
        │  │ • Kyverno                │   │
        │  │ • OpenCost               │   │
        │  └──────────────────────────┘   │
        └────────────────────────────────┘
```

## Core Components

### 1. Analyzer Agent

**File:** `agents/analyzer/analyzer_qwen3max.py`

Performs root cause analysis using Qwen3-Max thinking mode.

**Features:**
- Accepts up to 1M tokens of cluster state
- Streams reasoning chain to dashboard
- Generates concrete kubectl YAML patches
- Fallback to Qwen-Turbo for simple alerts

**Input:**
```json
{
  "alert_id": "alert-123",
  "alert_type": "oomkill",
  "cluster_state": {...},
  "metrics": {...}
}
```

**Output:**
```json
{
  "thinking_chain": "Step 1: Analyze memory usage...",
  "rca": "Root cause: Pod memory limit too low",
  "action_type": "patch",
  "yaml_patch": "kubectl patch deployment...",
  "confidence": 0.95
}
```

### 2. Planner Agent

**File:** `agents/planner/planner.py`

Creates remediation plans from RCA.

**Features:**
- Runbook-based planning
- Parameter validation
- Blast radius assessment
- Cost estimation

### 3. Trust Score Engine

**File:** `agents/trust/score.py`

Verifiable 4-factor scoring algorithm.

**Factors:**
1. **Reversibility (30%)** — Can the action be undone?
   - Scaling: High (reversible)
   - Deletion: Low (not reversible)
   - Patch: Medium (can rollback)

2. **Blast Radius (25%)** — How many resources affected?
   - Single pod: Low
   - Deployment: Medium
   - Node: High

3. **Runbook Confidence (25%)** — How confident is the fix?
   - Exact match: High
   - Partial match: Medium
   - No match: Low

4. **History (20%)** — Historical success rate?
   - Past successes: High
   - Past failures: Low
   - No history: Medium

**Decision Logic:**
```
if score >= 90:
    return "EXECUTE"
elif score >= 70:
    return "DRYRUN_VERIFY"
else:
    return "ESCALATE_HUMAN"
```

### 4. Executor Agent

**File:** `agents/executor/executor.py`

Executes remediation actions with trust scoring.

**Features:**
- Mandatory trust score computation
- Circuit breaker protection
- Blast radius parameter validation
- Outcomes logging to `outcomes.jsonl`

**Execution Modes:**
- **EXECUTE** — Immediate execution
- **DRYRUN_VERIFY** — Dry-run first, then live
- **ESCALATE_HUMAN** — Wait for human approval

### 5. Model Router

**File:** `agents/router/model_router.py`

Intelligent routing to Qwen models.

**Routing Policy:**
| Severity | Model | Context | Cost |
|----------|-------|---------|------|
| Critical | qwen3-max | Full cluster (1M tokens) | High |
| Standard | qwen-plus | Partial state | Medium |
| Simple | qwen-turbo | Metrics only | Low |
| Embedding | text-embedding-v3 | Vector search | Very Low |

### 6. Cost Governor

**File:** `agents/router/cost_governor.py`

Per-incident cost tracking.

**Metrics:**
- Model API costs
- Compute costs
- Remediation costs
- Total cost per incident

### 7. Chaos Injection Framework

**File:** `chaos/scenarios.py`

12 reproducible failure scenarios.

**Scenarios:**
1. OOMKilled pod
2. Bad ConfigMap
3. Node NotReady
4. ImagePullBackOff
5. CrashLoopBackOff
6. HPA Thrashing
7. PersistentVolume Detach
8. NetworkPolicy Misconfiguration
9. DNS Failure
10. Certificate Expiry
11. Ingress Misroute
12. Cost Anomaly

All scenarios auto-cleanup in < 60 seconds.

### 8. MCP Server

**File:** `mcp_server/tools.py`

18 tools for external AI clients.

**Tool Categories:**
- **Cluster Monitoring (4)** — get_pod_status, get_node_status, get_metrics, get_logs
- **Remediation Control (4)** — execute_patch, scale_deployment, restart_pod, rollback
- **Trust & Safety (3)** — get_trust_score, explain_reasoning, simulate_remediation
- **Knowledge & History (4)** — search_runbooks, get_incident_history, get_cluster_topology, query_cost_impact
- **Cost & Prediction (3)** — predict_failure, get_cost_impact, approve_action

## Data Flow

### Incident Detection → Resolution

```
1. Alert Ingestion
   └─→ Prometheus Alert → Alert Manager → NeuroScale

2. Analysis
   └─→ Analyzer (Qwen3-Max) → RCA + YAML Patch

3. Planning
   └─→ Planner → Remediation Plan

4. Trust Scoring
   └─→ Trust Engine → Score + Decision

5. Execution
   └─→ Executor → Apply Patch → Monitor

6. Logging
   └─→ outcomes.jsonl → Audit Trail
```

### Feedback Loops

**Loop 1: Outcomes → History**
```
Execution Outcome → outcomes.jsonl → History Analyzer
→ Update historical success rates → Improve future scores
```

**Loop 2: Cost → Budgeting**
```
Per-incident cost → Cost Governor → Budget enforcement
→ Route to cheaper models if budget tight
```

**Loop 3: Reasoning → Learning**
```
Thinking chain → Dashboard → Human feedback
→ Improve prompts and weights
```

## Deployment Architecture

### Kubernetes Deployment

```
Namespace: neuroscale-autopilot

Pods:
├── neuroscale-analyzer (Qwen3-Max client)
├── neuroscale-planner (Runbook engine)
├── neuroscale-executor (kubectl client)
├── neuroscale-mcp-server (FastAPI)
└── neuroscale-dashboard (React frontend)

Services:
├── neuroscale-api (ClusterIP:8000)
├── neuroscale-mcp (ClusterIP:8001)
└── neuroscale-dashboard (LoadBalancer:3000)

ConfigMaps:
├── trust-policies (weights, thresholds)
├── runbooks (remediation templates)
└── model-config (Qwen API keys, endpoints)

RBAC:
├── ServiceAccount: neuroscale
├── ClusterRole: neuroscale-admin
└── ClusterRoleBinding: neuroscale-admin
```

### Alibaba Cloud ACK Specifics

**Region:** ap-southeast-1 (Singapore)  
**Cluster Type:** Managed Kubernetes  
**Networking:** VPC with NAT Gateway  
**Storage:** Alibaba Cloud NAS for outcomes.jsonl  
**Monitoring:** Alibaba Cloud Container Service for Kubernetes (ACK) monitoring  

## Security & Compliance

### Trust Layer Security

- **No action without trust score** — Mandatory computation
- **Audit trail** — All outcomes logged to outcomes.jsonl
- **Human escalation** — Low-confidence actions require approval
- **Circuit breaker** — Prevents cascading failures
- **Blast radius validation** — Dangerous parameters blocked

### Data Security

- **No secrets in code** — All credentials via environment variables
- **Encrypted communication** — TLS for all external APIs
- **RBAC enforcement** — Kubernetes RBAC for all operations
- **Audit logging** — All actions logged with timestamps

## Performance Characteristics

### Latency

- **Detection** — < 1 minute (Prometheus scrape interval)
- **Analysis** — 5-30 seconds (Qwen3-Max thinking)
- **Planning** — 2-5 seconds (runbook matching)
- **Trust Scoring** — < 1 second (local computation)
- **Execution** — 10-60 seconds (kubectl apply)
- **Total MTTR** — 30-120 seconds (vs 15-30 minutes industry average)

### Throughput

- **Concurrent incidents** — 10-50 (depends on cluster size)
- **Qwen API rate limit** — 10 req/s (configurable)
- **MCP tool throughput** — 100+ req/s (local)

### Cost

- **Per incident (Qwen3-Max)** — $0.05-0.15
- **Per incident (Qwen-Turbo)** — $0.01-0.03
- **Monthly (1000 incidents)** — $50-150
- **Savings vs manual SRE** — $500-2000/month

## Extensibility

### Adding New Chaos Scenarios

```python
# chaos/custom_scenario.py
class CustomScenario(ChaosScenario):
    async def inject(self):
        # Apply failure
        pass
    
    async def cleanup(self):
        # Revert failure
        pass
```

### Adding New MCP Tools

```python
# mcp_server/tools.py
@mcp_tool
async def my_custom_tool(param1: str) -> Dict:
    """Custom tool description."""
    return {"result": "..."}
```

### Customizing Trust Weights

```yaml
# agents/trust/policies.yaml
weights:
  reversibility: 0.35  # Increase from 0.30
  blast_radius: 0.25
  runbook_confidence: 0.20  # Decrease from 0.25
  history: 0.20
```

## Monitoring & Observability

### Key Metrics

- `neuroscale_trust_score` — Trust score distribution
- `neuroscale_execution_mode` — EXECUTE vs DRYRUN vs ESCALATE
- `neuroscale_mttr_seconds` — Mean time to remediate
- `neuroscale_cost_per_incident` — Cost tracking
- `neuroscale_false_remediation_rate` — Safety metric

### Logging

- **Structured logging** — JSON format via structlog
- **Log levels** — DEBUG, INFO, WARNING, ERROR
- **Log destinations** — stdout (collected by Kubernetes)

### Dashboard

- **Trust Panel** — Real-time trust scores
- **Thinking Stream** — Live Qwen reasoning
- **Cost Counter** — Per-incident cost display
- **Chaos Injection** — Manual scenario triggering
- **Outcomes** — Historical action log

## Roadmap

### v2.1 (Q3 2026)
- Multi-action plan optimization
- ML-based weight tuning
- Advanced anomaly detection
- Contextual scoring

### v2.2 (Q4 2026)
- Feedback loop integration
- Operator learning system
- Cross-cluster federation
- SLA-aware remediation

---

**Architecture Version:** v2.0.0  
**Last Updated:** 2026-07-04  
**Status:** Production Ready
