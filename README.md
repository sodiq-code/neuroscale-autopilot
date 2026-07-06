# NeuroScale Autopilot

> **Track 4 — Autopilot Agent** | Qwen Cloud Global AI Hackathon

### NeuroScale doesn't just fix your cluster — it proves the fix is safe before it acts, and knows when to stop and ask a human.

Everyone builds agents that act. This one knows when **not** to act. NeuroScale Autopilot is a self-healing control plane for Kubernetes, powered by the **Qwen model family**, built around a single non-negotiable idea: **an autonomous SRE system earns the right to automate by making every high-impact decision explainable, measurable, and safety-aware.**

See [TRUST_LAYER.md](TRUST_LAYER.md) for the full breakdown of how that trust score actually works — and a real example, captured live from this deployment, of the system refusing to guess when its own evidence was weak.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Qwen Powered](https://img.shields.io/badge/AI-Qwen%20Max%20%7C%20Turbo%20%7C%20Embedding-orange.svg)](https://dashscope.aliyuncs.com/)
[![Deployed on Alibaba Cloud](https://img.shields.io/badge/Deployed%20on-Alibaba%20Cloud%20ECS%20%2B%20K3s-FF6A00.svg)](#live-alibaba-cloud-deployment)

---

## Live Alibaba Cloud Deployment

This project is deployed and running **right now** on a real Alibaba Cloud ECS instance in `ap-southeast-1` (Singapore), running a real k3s Kubernetes cluster with a live `checkout-service` deployment as the incident target — not a local demo, not a mock.

| Component | Detail |
|---|---|
| Cloud provider | Alibaba Cloud ECS (`ecs.e4.small`, Ubuntu 24.04) |
| Region | `ap-southeast-1` (Singapore) |
| Kubernetes | k3s v1.36.2+k3s1 (real control plane, real pods, real events) |
| Qwen base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` (see [`agents/analyzer`](agents/analyzer)) |
| Target workload | `checkout-service` deployment (3 replicas) in the `checkout` namespace |
| Proof | See `docs/screenshots-real/` for unedited screenshots of the live dashboard reacting to a real injected incident |

See the [Alibaba Cloud Deployment](#alibaba-cloud-deployment) section below for the exact steps used, and [TRUST_LAYER.md](TRUST_LAYER.md) for a real captured incident from this exact deployment.

---

## Demo Video

[![NeuroScale Autopilot Demo](https://img.youtube.com/vi/ARVD_QFKXGw/maxresdefault.jpg)](https://youtu.be/ARVD_QFKXGw)

> Click to watch the demo — full pipeline walkthrough, Qwen models in action, MCP server, and the Trust Layer deciding whether to auto-remediate, simulate, or escalate.

---

## What It Does

NeuroScale Autopilot runs a continuous self-healing loop on your Kubernetes cluster:

```
Metrics → Detect → Analyze (Qwen-Max) → Plan (Qwen-Embedding RAG) → Execute → Escalate (Qwen-Turbo)
              ↑                                                                           ↓
              └──────────────── Self-healing feedback loop ─────────────────────────────┘
```

1. **Detector** — Polls Prometheus/mock metrics; fires alerts on anomaly thresholds
2. **Analyzer** — Sends alert context to **Qwen-Max** for root cause analysis + risk scoring
3. **Planner** — Uses **Qwen-Embedding** to retrieve the most relevant runbook via semantic search; produces a structured remediation plan
4. **Executor** — Runs kubectl commands with circuit-breaker protection; dry-run by default
5. **Escalation** — **Qwen-Turbo** generates a concise Slack notification; human-in-the-loop approval for high-risk actions
6. **MCP Server** — 8 Model Context Protocol tools expose the agent to external AI clients
7. **Alibaba Cloud ECS** — Native ECS/STS client for cloud-layer remediation

---

## Architecture

![NeuroScale Autopilot Architecture](docs/assets/architecture-diagram.png)

> Full pipeline: Kubernetes/Kyverno/OpenCost events → 5 autonomous agents → MCP Server → Alibaba Cloud ECS. Orchestrator handles alert deduplication and human-approval timeout (300s).

<details>
<summary>ASCII fallback</summary>

```
┌──────────────────────────────────────────────────────────────┐
│                    NeuroScale Autopilot                      │
│                                                              │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │Detector │──▶│Analyzer      │──▶│Planner               │  │
│  │         │   │Qwen-Max LLM  │   │Qwen-Embedding + RAG  │  │
│  │Prometheus│   │RCA + Scoring │   │Runbook Retrieval     │  │
│  └─────────┘   └──────────────┘   └──────────┬───────────┘  │
│                                               │              │
│  ┌─────────────────────────┐   ┌─────────────▼───────────┐  │
│  │Escalation Agent         │◀──│Executor                 │  │
│  │Qwen-Turbo Summary       │   │kubectl + Circuit Breaker│  │
│  │Slack + Approval Flow    │   │Alibaba Cloud ECS        │  │
│  └─────────────────────────┘   └─────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │MCP Server (8 tools) — FastAPI REST + SSE                │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```
</details>

---

## Dashboard Screenshots

> Unedited screenshots captured directly from the live Alibaba Cloud deployment (`http://<instance-ip>:3000`) while a real incident was running on a real k3s cluster. No mocked data, no image editing.

**Monitoring Overview — Live incident from the real cluster, "Live" websocket status**
![Dashboard Overview](docs/screenshots-real/dashboard-overview.png)

**Hero Incident — Bad image tag injected into `checkout-service`, detected in real time**
![Checkout Incident](docs/screenshots-real/checkout-incident-detected.png)

**Trust Layer Decision Card — Root cause, confidence, risk, rollback plan, human approval gate**
![Trust Layer Decision Card](docs/screenshots-real/trust-layer-decision-card.png)

> Note: the "Qwen Analysis" text in the decision card above shows a real `AccessDenied.Unpurchased` error because the DashScope account's model activation was still pending at the moment this incident ran. Rather than fail silently or fabricate a diagnosis, the system correctly marked confidence as `low`, risk as `high`, `auto_remediate: false`, and escalated to human approval — see [TRUST_LAYER.md](TRUST_LAYER.md#what-happens-when-the-model-itself-fails) for why that's the Trust Layer working as intended, not a bug.

---

## Qwen Models Used

| Component | Model | Purpose |
|-----------|-------|---------|
| Analyzer | `qwen-max` | Root cause analysis, risk scoring, confidence |
| Planner | `text-embedding-v3` | Runbook semantic search (RAG) |
| Escalation | `qwen-turbo` | Human-readable Slack incident summaries |

All models served via **Alibaba Cloud DashScope** (`dashscope.aliyuncs.com/compatible-mode/v1`).

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- Qwen API key from [DashScope Console](https://dashscope.aliyuncs.com/)
- `kubectl` configured (or use mock mode)

### 1. Clone & Configure

```bash
git clone https://github.com/sodiq-code/neuroscale-autopilot.git
cd neuroscale-autopilot

cp .env.example .env
# Edit .env — set your QWEN_API_KEY
```

### 2. Install & Run (Local)

```bash
pip install -r requirements.txt
python main.py
```

The agent starts in **dry-run mode** by default — no real kubectl commands are executed.

### 3. Run with Docker

```bash
docker-compose up --build
```

Services:
- `http://localhost:8000` — MCP Server API + Health
- `http://localhost:3000` — React Monitoring Dashboard

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QWEN_API_KEY` | ✅ | — | DashScope API key |
| `QWEN_BASE_URL` | ❌ | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Qwen endpoint |
| `QWEN_MODEL_MAX` | ❌ | `qwen-max` | Analyzer model |
| `QWEN_MODEL_TURBO` | ❌ | `qwen-turbo` | Escalation model |
| `QWEN_MODEL_EMBEDDING` | ❌ | `text-embedding-v3` | Embedding model |
| `SLACK_WEBHOOK_URL` | ❌ | — | Slack webhook for notifications |
| `KUBECONFIG` | ❌ | `~/.kube/config` | Kubeconfig path |
| `DRY_RUN` | ❌ | `true` | Disable real kubectl execution |
| `ALIBABA_ACCESS_KEY_ID` | ❌ | — | ECS cloud remediation |
| `ALIBABA_ACCESS_KEY_SECRET` | ❌ | — | ECS cloud remediation |
| `ALIBABA_REGION_ID` | ❌ | `cn-hangzhou` | ECS region |
| `POLL_INTERVAL_SECONDS` | ❌ | `30` | Metric polling frequency |

---

## MCP Server Tools

The MCP server exposes 8 tools for external AI clients:

| Tool | Description |
|------|-------------|
| `get_cluster_status` | Current health summary of the cluster |
| `list_active_alerts` | All active alerts with severity + age |
| `get_alert_detail` | Full detail for a specific alert |
| `trigger_remediation` | Manually trigger remediation for an alert |
| `get_remediation_status` | Status of a running remediation job |
| `approve_action` | Human approval for pending high-risk actions |
| `get_runbook` | Retrieve runbook content by name |
| `get_metrics_summary` | Raw metric summary for a namespace |

---

## Project Structure

```
neuroscale-autopilot/
├── agents/
│   ├── detector/       # Prometheus poller + alert generation
│   ├── analyzer/       # Qwen-Max RCA engine
│   ├── planner/        # Qwen-Embedding RAG + remediation planner
│   ├── executor/       # kubectl runner + circuit breaker
│   └── escalation/     # Qwen-Turbo + Slack + approval flow
├── mcp_server/         # FastAPI MCP server (8 tools)
├── alibaba_cloud/      # ECS/STS client for cloud remediation
├── dashboard/          # React monitoring dashboard
├── runbooks/           # Markdown runbooks for RAG
├── k8s/                # Kubernetes manifests (deploy to ECS K8s)
├── tests/              # Pytest smoke + integration tests
├── .github/workflows/  # CI pipeline
├── main.py             # Entry point
├── Dockerfile
└── docker-compose.yml
```

---

## Alibaba Cloud Deployment

This exact repo is deployed and running on Alibaba Cloud right now. Real steps used for the live deployment referenced above:

```bash
# 1. Provision ECS instance (Alibaba Cloud, ap-southeast-1)
#    ecs.e4.small, Ubuntu 24.04, VPC + VSwitch + Security Group (22/8000/3000)

# 2. Install container runtime + lightweight Kubernetes on the instance
curl -fsSL https://get.docker.com | sh
curl -sfL https://get.k3s.io | sh -

# 3. Deploy the target workload (the incident surface for the agent to monitor)
kubectl apply -f k8s/checkout-app.yaml   # namespace + deployment + service

# 4. Build and run NeuroScale Autopilot against the real cluster
docker compose build autopilot
docker compose --profile dashboard up -d
# autopilot container mounts the real k3s kubeconfig (/root/.kube/config)
# and runs with network_mode: host so it can reach the k8s API on :6443

# 5. Verify
curl http://<instance-public-ip>:8000/health
curl http://<instance-public-ip>:3000       # live dashboard
```

For a managed-Kubernetes path instead of self-hosted k3s, the original ACK manifests are still available:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl create secret generic neuroscale-secrets \
  --from-literal=QWEN_API_KEY=<your-key> \
  -n neuroscale-autopilot
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## How the Self-Healing Loop Works

```
1. Detector polls Prometheus every 30s
2. Anomaly detected → Alert fired (severity: info/warning/critical)
3. Analyzer sends alert to Qwen-Max → returns RCA + risk score
4. Planner embeds RCA with text-embedding-v3 → finds closest runbook
5. Planner builds RemediationPlan (steps + requires_approval flag)
6. If requires_approval=True:
     → Qwen-Turbo generates summary → Slack notification sent
     → System waits up to 5 min for human approval
     → Auto-rejects on timeout (safety-first)
7. If approved (or auto-approved):
     → Executor runs kubectl steps with circuit breaker
     → On consecutive failures → breaker OPEN → no more attempts
8. Result logged → Detector re-polls → loop continues
```

---

## Benchmark: Real Numbers From the Live Deployment

Measured directly from the running system's own logs during the `checkout-service` bad-image-tag incident on the live Alibaba Cloud deployment (timestamps below are real, taken from container logs, not simulated):

| Metric | Value | Source |
|---|---|---|
| Full pipeline latency (alert fired → escalation decision ready) | **2.6 seconds** | Measured: `pipeline_start` 21:24:21.008 → `awaiting_human_approval` 21:24:23.593, including two failed external API calls handled gracefully |
| Detection to human-actionable decision card | Sub-minute (bounded by K8s event watch cycle) | Measured from live cluster events |
| Manual baseline (typical human triage of an `ImagePullBackOff`: notice alert, open dashboard, `kubectl describe`, correlate, decide) | Several minutes (industry rule of thumb, not measured in this run) | Estimate — flagged as such, not fabricated |
| Retrieval-ambiguity catches (system escalates instead of guessing) | 2/2 incidents in this test run | Both incidents in this deployment had `retrieval_score: 0.0` and were correctly escalated rather than auto-executed |
| Rollback plan present on every proposed remediation | 100% | Enforced by the Planner — no `RemediationPlan` is created without a `rollback_plan` field |

We're intentionally not padding this table with invented precision. The honest takeaway: even while two of its three Qwen model calls were failing (a real, live model-activation issue on the Alibaba account, not a code bug), the Trust Layer still made the *correct* call — escalate, don't guess — in under 3 seconds.

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

**Sodiq Jimoh** — Platform Engineer  
[LinkedIn](https://linkedin.com/in/sodiq-jimoh-afsod)

Built for the **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**
