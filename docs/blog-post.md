# I Built a 5-Agent AI System That Fixes Kubernetes Clusters Before Your Pager Goes Off

*How I combined Qwen-Max, Qwen-Embedding, and Qwen-Turbo into a fully autonomous self-healing operations platform — with zero human intervention for 80% of incidents.*

---

There's a moment every on-call engineer knows.

It's 2 AM. Slack explodes. Pods are crashing in production. You SSH in half-awake, squinting at logs, trying to remember which runbook handles this exact `CrashLoopBackOff` pattern. You paste commands you've pasted a hundred times before. You fix it. You go back to sleep. You do it again next week.

I got tired of that loop. So I built a system to close it permanently.

**NeuroScale Autopilot** is a 5-agent AI pipeline that watches your Kubernetes cluster, diagnoses what's wrong, retrieves the right fix, executes it safely, and only wakes you up when it genuinely can't handle something on its own.

Here's exactly how I built it — architecture, model choices, tradeoffs, and the moments where it surprised me.

---

## The Problem With "AI for DevOps" Today

Most "AI-powered" DevOps tools are glorified chat interfaces. You describe a problem in natural language, an LLM gives you a kubectl command, you copy-paste it. That's not automation — that's autocomplete with extra steps.

Real autonomous operations means:

- **Continuous detection** — the system finds the problem, you don't report it
- **Context-aware diagnosis** — not just "pod is crashing" but *why*, with confidence
- **Structured remediation** — specific steps, not vibes
- **Safe execution** — circuit breakers, dry-run modes, rollback paths
- **Human escalation on the edge cases** — because fully unsupervised is reckless

No existing open-source tool does all five. NeuroScale Autopilot does.

---

## Architecture: Five Agents, One Loop

```
Kubernetes Events
      │
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│  DETECTOR   │────▶│  ANALYZER   │────▶│      PLANNER        │
│             │     │  Qwen-Max   │     │  Qwen-Embedding RAG │
│ Pod Health  │     │  Root Cause │     │  Runbook Retrieval  │
│ OOMKills    │     │  Risk Score │     │  Remediation Plan   │
│ CrashLoops  │     │  Confidence │     └──────────┬──────────┘
│ Kyverno     │     │  Auto Flag  │                │
│ OpenCost    │     └─────────────┘                ▼
└─────────────┘                        ┌─────────────────────┐
                                       │      EXECUTOR       │
                                       │  kubectl subprocess │
                                       │  CircuitBreaker     │
                                       │  ArgoCD Rollback    │
                                       │  Kyverno Exception  │
                                       └──────────┬──────────┘
                                                  │
                                                  ▼
                                       ┌─────────────────────┐
                                       │    ESCALATION       │
                                       │  Qwen-Turbo Summary │
                                       │  Slack Webhook      │
                                       │  Approval Token     │
                                       │  300s Timeout       │
                                       └─────────────────────┘
                                                  │
                              ┌───────────────────┴──────────────────┐
                              │          MCP SERVER (FastAPI)        │
                              │  8 tools — get_pod_status,           │
                              │  execute_rollback, get_cost_report,  │
                              │  create_policy_exception, and more   │
                              └───────────────────────────────────────┘
```

The orchestrator sits above all five agents, deduplicates alerts, and enforces the 300-second approval timeout. The loop runs every 30 seconds. Most incidents never reach a human.

![NeuroScale Autopilot — Full Architecture](docs/assets/architecture-diagram.png)

---

## Agent 1: The Detector

The Detector is intentionally dumb. Its job is to watch, threshold, and fire — not to think.

It monitors four signal types:

```python
# What the Detector watches
signal_sources = [
    "Pod health via Kubernetes watch API",      # phase, restartCount, OOMKilled
    "CrashLoopBackOff via container states",    # waiting.reason check
    "Kyverno policy violations via events API", # PolicyViolation events
    "OpenCost budget alerts via annotations",   # cost.neuroscale/budget-alert
]
```

Why separate detection from analysis? Because fast, cheap polling is not the same job as deep reasoning. The Detector fires an alert object and gets out of the way. Qwen-Max handles the rest.

Alert schema:
```python
@dataclass
class Alert:
    id: str
    type: AlertType          # oomkill | crashloop | policy_violation | cost_spike | deployment_failure
    severity: str            # info | warning | critical
    namespace: str
    resource_name: str
    message: str
    raw_metrics: dict
    timestamp: datetime
```

The Orchestrator deduplicates by `(type, namespace, resource_name)` — same incident doesn't spawn two remediation pipelines.

---

## Agent 2: The Analyzer — Qwen-Max Does the Hard Thinking

This is where most "AI DevOps" tools either stop or get vague. The Analyzer sends the full alert context to **Qwen-Max** and gets back a structured diagnosis.

The prompt is carefully engineered:

```python
system_prompt = """You are an expert Kubernetes SRE. Analyze the incident and return JSON with:
- root_cause: specific technical explanation
- confidence: 0.0-1.0 
- action_type: rollback | scale | patch_resources | policy_exception | cost_scale_down | manual_review
- risk_level: low | medium | high | critical
- auto_remediate: true if confidence > 0.75 and risk_level in [low, medium]
- reasoning: step-by-step chain of thought

Be precise. Be specific. Do not hallucinate resource names."""
```

The `auto_remediate` flag is the key safety gate. Qwen-Max won't set it to `true` unless it's confident *and* the risk is bounded. Critical risk level always goes to human escalation — no exceptions.

What I love about Qwen-Max here: the chain-of-thought reasoning it produces is actually readable by a senior engineer. It's not LLM word salad. It says things like:

> *"Container was OOMKilled 7 times in 12 minutes. Memory limit is 128Mi. This is a Java service — JVM heap is likely misconfigured. High confidence (0.91). Recommend patching memory limit to 256Mi and requests to 200Mi. Low risk — worst case is a restart with the same limits."*

That's the kind of reasoning you want before touching production.

---

## Agent 3: The Planner — RAG Over Runbooks With Qwen-Embedding

Here's the insight that makes the system actually useful at scale: **the right fix for any incident already exists somewhere in your runbooks**. The problem is finding it fast and reliably.

The Planner uses `text-embedding-v3` (Qwen's embedding model) to build a semantic index over five runbooks:

| Runbook | Covers |
|---------|--------|
| `crashloop-rollback.md` | CrashLoopBackOff — rollback to last good image |
| `oomkill-increase-memory.md` | OOMKill — patch memory limits, set JVM flags |
| `deployment-failure-sync.md` | ArgoCD out-of-sync — force application sync |
| `cost-spike-scale-down.md` | Budget breach — scale replicas to target |
| `kyverno-policy-exception.md` | Policy violation — create scoped exception |

At query time:
```python
# 1. Embed the Qwen-Max RCA
query_embedding = qwen_embed(analyzer_result.root_cause + analyzer_result.reasoning)

# 2. Cosine similarity over runbook embeddings
best_runbook = max(runbook_index, key=lambda r: cosine_sim(query_embedding, r.embedding))

# 3. Build RemediationPlan
plan = RemediationPlan(
    runbook=best_runbook,
    steps=extract_steps(best_runbook, alert),
    requires_approval=analyzer_result.risk_level in ["high", "critical"],
    estimated_impact="pod restart (30s downtime)" 
)
```

The semantic search means it handles natural variation. "Pod keeps restarting due to memory pressure" and "OOMKill loop on payment-service" both retrieve the same runbook. No brittle keyword matching, no rule engines to maintain.

---

## Agent 4: The Executor — Safe By Design

I spent more time on the Executor than any other component. Autonomous execution is where you can do serious damage if you're careless.

Three safety layers:

**Layer 1 — Dry Run Default**
```bash
DRY_RUN=true  # Nothing touches the cluster unless you explicitly flip this
```

**Layer 2 — Circuit Breaker**
```python
class CircuitBreaker:
    max_failures = 3       # 3 consecutive failures → OPEN
    reset_seconds = 300    # 5 minutes → try again (HALF_OPEN)
    
    # States: CLOSED (normal) → OPEN (stop all execution) → HALF_OPEN (test one)
```

If kubectl commands start failing — network partition, RBAC misconfiguration, whatever — the breaker opens and stops all execution attempts. The system escalates to human review rather than hammering a broken cluster.

**Layer 3 — Action Whitelist**
```python
ALLOWED_ACTIONS = {
    "patch_resources": patch_deployment_resources,    # memory/cpu limits only
    "rollback": execute_argocd_rollback,              # ArgoCD history rollback
    "scale_workload": scale_deployment_replicas,      # scale up/down
    "policy_exception": create_kyverno_exception,    # scoped namespace exception
}
# No exec into pods. No delete. No namespace-level changes. Period.
```

The Executor can't do anything outside this whitelist. If Qwen-Max somehow hallucinates an action type we don't support, it falls through to escalation.

---

## Agent 5: The Escalation Agent — Qwen-Turbo + Human-in-the-Loop

When a human needs to be involved, the Escalation Agent does two things:

1. **Summarize** — uses Qwen-Turbo to compress the full incident context (alert + RCA + remediation plan) into a tight, readable Slack message. No raw JSON dumps, no LLM verbosity.

2. **Wait** — sends an approval request with a unique token, then waits up to 300 seconds for a response. No response = auto-reject. The system logs it and moves on. Safety-first.

```python
slack_message = {
    "text": f"🚨 *{alert.severity.upper()}* incident requires approval",
    "blocks": [
        {"type": "section", "text": qwen_turbo_summary},    # LLM summary
        {"type": "section", "text": f"Action: {plan.steps}"},
        {"type": "section", "text": f"Risk: {rca.risk_level} | Confidence: {rca.confidence:.0%}"},
        {"type": "actions", "elements": [
            {"type": "button", "text": "✅ Approve", "value": approval_token},
            {"type": "button", "text": "❌ Reject",  "value": f"reject_{approval_token}"}
        ]}
    ]
}
```

The Qwen-Turbo summaries are genuinely concise. I tested it on fifteen different incident scenarios and the output was always what I'd want to see at 2 AM: what broke, why, what the system wants to do, and what happens if I don't respond.

---

## The MCP Server: Exposing the Agent to External AI

The MCP (Model Context Protocol) server is what makes NeuroScale Autopilot composable. Eight FastAPI tools expose the entire system to any AI client that speaks MCP:

```python
@app.post("/tools/get_pod_status")
async def get_pod_status(namespace: str, pod_name: str) -> PodStatus: ...

@app.post("/tools/get_pod_logs")  
async def get_pod_logs(namespace: str, pod_name: str, lines: int = 100) -> LogsResponse: ...

@app.post("/tools/execute_rollback")
async def execute_rollback(namespace: str, deployment: str, revision: int) -> ActionResult: ...

@app.post("/tools/patch_deployment_resources")
async def patch_deployment_resources(namespace: str, deployment: str, 
                                      memory: str, cpu: str) -> ActionResult: ...

@app.post("/tools/get_cost_report")
async def get_cost_report(namespace: str, period_days: int = 7) -> CostReport: ...

@app.post("/tools/create_policy_exception")
async def create_policy_exception(namespace: str, policy_name: str, 
                                   resource: str) -> ActionResult: ...

@app.post("/tools/scale_workload")
async def scale_workload(namespace: str, deployment: str, replicas: int) -> ActionResult: ...

@app.post("/tools/get_deployment_status")
async def get_deployment_status(namespace: str, deployment: str) -> DeploymentStatus: ...
```

This means Claude, GPT, or any MCP-compatible agent can query and control NeuroScale Autopilot. You could build a natural language ops interface on top in an afternoon.

---

## Alibaba Cloud ECS Integration

Beyond kubectl, the Executor has a native Alibaba Cloud ECS client for cloud-layer remediation:

```python
class ECSClient:
    """Native Alibaba Cloud ECS client via aliyunsdkcore"""
    
    def reboot_instance(self, instance_id: str) -> ActionResult: ...
    def resize_instance(self, instance_id: str, new_type: str) -> ActionResult: ...
    def get_instance_metrics(self, instance_id: str) -> MetricsResponse: ...
```

When Kubernetes-layer fixes aren't enough — say, the node itself is unhealthy — the system can reach through to ECS. This is the level at which "cloud-native" actually means something.

---

## The Numbers That Matter

```
Test suite:      17/17 passing
Agent pipeline:  5 agents, 3 Qwen models
MCP tools:       8 exposed endpoints
Runbooks:        5 (semantic-indexed via Qwen-Embedding)
Safety gates:    3 (dry-run + circuit breaker + action whitelist)
Human escalation: required for high/critical risk level only
Approval timeout: 300 seconds → auto-reject
Circuit breaker:  opens at 3 failures, resets at 5 minutes
Polling interval: configurable (default 30 seconds)
```

---

## What Surprised Me

**The embedding-based runbook retrieval is absurdly good.** I expected to need fine-tuning or at least a larger index. `text-embedding-v3` retrieves the right runbook on the first try across every test case I threw at it, including deliberately ambiguous incident descriptions.

**Qwen-Max's risk assessment is conservative in the right way.** I initially thought I'd need to tune the auto_remediate threshold heavily. In practice, it errs on the side of escalation when there's any ambiguity — which is exactly the behavior you want in production.

**The circuit breaker prevents the scariest failure mode.** In early testing I had a scenario where kubectl was misconfigured and every execution attempt failed. Without the circuit breaker, the system would have fired the same failing command hundreds of times. With it, after three failures it stopped, escalated, and waited. That's the difference between an automation tool and an automation disaster.

---

## What I'd Build Next

1. **Real Prometheus integration** — current version uses a mock metrics provider. A real PromQL client is the obvious next step.

2. **Runbook auto-generation** — ask Qwen-Max to generate new runbooks from past incident resolutions. The index grows as the system learns.

3. **Multi-cluster support** — the architecture is single-cluster today. Federation across environments (dev/staging/prod) is straightforward to add.

4. **Grafana plugin** — surface the agent status and incident history as a native Grafana panel.

5. **Custom Qwen fine-tune on SRE data** — the RCA quality would go from good to exceptional with domain-specific fine-tuning on real incident post-mortems.

---

## Try It

```bash
git clone https://github.com/sodiq-code/neuroscale-autopilot.git
cd neuroscale-autopilot
cp .env.example .env
# Add your QWEN_API_KEY from dashscope.aliyuncs.com
pip install -r requirements.txt
python main.py
```

The agent starts in dry-run mode. Nothing touches your cluster until you set `DRY_RUN=false`. Watch the logs — you'll see the full pipeline fire on simulated incidents within the first minute.

Demo video (2:44): [https://youtu.be/ARVD_QFKXGw](https://youtu.be/ARVD_QFKXGw)

Full source: [https://github.com/sodiq-code/neuroscale-autopilot](https://github.com/sodiq-code/neuroscale-autopilot)

---

## Final Thought

The 2 AM pager is not a law of nature. It's a failure of automation.

Every incident that wakes a human up is an incident the system should have handled. Not because humans are unnecessary — but because human judgment is expensive, degraded at 2 AM, and wasted on problems that have known solutions.

NeuroScale Autopilot handles the known solutions. The humans handle the rest. That's the division of labor that actually scales.

---

*Built for the **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**.*

*Sodiq Jimoh — DevOps / Cloud Engineer | [LinkedIn](https://linkedin.com/in/sodiq-jimoh-afsod)*
