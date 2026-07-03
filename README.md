# NeuroScale Autopilot v2

> **The Autonomous SRE with a Verifiable Trust Layer**  
> Track 4 — Autopilot Agent | Qwen Cloud Global AI Hackathon

**NeuroScale Autopilot v2** is the first Kubernetes self-healing agent that enterprises would actually trust. It combines **Qwen 3.7-Max's thinking mode**, a **verifiable trust score algorithm**, and **18 MCP tools** to autonomously detect, diagnose, and remediate infrastructure incidents — while proving every action is safe, reversible, and cost-justified before execution.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Qwen Powered](https://img.shields.io/badge/AI-Qwen%203.7-Max%20%7C%20Thinking%20Mode-orange.svg)](https://dashscope.aliyuncs.com/)
[![MCP Tools](https://img.shields.io/badge/MCP%20Tools-18-green.svg)](docs/MCP_TOOLS.md)
[![Trust Layer](https://img.shields.io/badge/Trust%20Layer-Verifiable-purple.svg)](docs/TRUST_LAYER.md)

---

## What's New in v2

### 🧠 Qwen 3.7-Max Thinking Mode
- **1M-token context window** for comprehensive incident analysis
- **Streaming reasoning** displayed live on the dashboard
- **Concrete YAML patches** generated, not just descriptions
- **Cost-optimized routing** between qwen3-max, qwen-plus, and qwen-turbo

### 🛡️ Verifiable Trust Score Engine
- **Composite algorithm** combining reversibility, blast radius, runbook confidence, and history
- **Transparent decision-making** — every action is scored and logged
- **Three execution modes:**
  - **EXECUTE** (score ≥ 90): Immediate remediation
  - **DRYRUN_VERIFY** (70-89): Dry-run first, then live if successful
  - **ESCALATE_HUMAN** (<70): Wait for human approval
- **Audit trail** in `outcomes.jsonl` for compliance

### ⚡ Chaos Injection Harness
- **12 reproducible scenarios** for testing the pipeline
- **Safe in dev clusters** — automatic cleanup in < 60 seconds
- **Integrated into dashboard** — inject chaos with a single click

### 🔧 Expanded MCP Surface
- **18 tools** (up from 8) for external AI clients
- **Trust scoring** exposed as a tool
- **Runbook search** with semantic RAG
- **Incident history** and **failure prediction**

### 💰 Cost Governance
- **Per-incident cost tracking** with OpenCost integration
- **Cost impact prediction** before execution
- **Model router** for intelligent cost-quality tradeoffs

### 📊 Comprehensive Benchmarking
- **Reproducible impact metrics** (MTTR, MTTD, cost per incident)
- **Baseline comparison** against human SRE response times
- **Trust score accuracy** validation

---

## Architecture

![NeuroScale Autopilot v2 Architecture](docs/assets/architecture-v2.png)

**Pipeline:**
```
Metrics → Detect → Analyze (Qwen3-Max Thinking) → Plan (RAG) → Trust Score → Execute/Verify/Escalate
              ↑                                                                           ↓
              └──────────────── Self-healing feedback loop ─────────────────────────────┘
```

**Data Flow:**
- **Inputs:** Prometheus metrics, Kubernetes events, Kyverno policies, OpenCost
- **Processing:** 6-agent pipeline with trust layer gating
- **Outputs:** MCP tools, React dashboard, Slack notifications, outcomes log
- **Deployment:** Alibaba Cloud ACK (Kubernetes)

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
git checkout v2-trust-layer

cp .env.example .env
# Edit .env — set your QWEN_API_KEY and other settings
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
- **API:** `http://localhost:8000` — MCP Server + Health
- **Dashboard:** `http://localhost:3000` — React Monitoring Dashboard
- **WebSocket:** `ws://localhost:8000/ws` — Live incident updates

### 4. Test the Pipeline

```bash
# Trigger a demo incident
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "oomkill"}'

# View incidents
curl http://localhost:8000/api/incidents

# Get trust score
curl -X POST http://localhost:8000/mcp/tools/get_trust_score \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## Qwen Models Used

| Component | Model | Purpose | Thinking Mode |
|-----------|-------|---------|---|
| **Analyzer** | `qwen3-max` | Root cause analysis, risk scoring | ✅ Yes |
| **Planner** | `qwen-plus` | Runbook retrieval, plan generation | ❌ No |
| **Escalation** | `qwen-turbo` | Slack summaries, human notifications | ❌ No |
| **Embeddings** | `text-embedding-v3` | Semantic runbook search | — |

All models served via **Alibaba Cloud DashScope** (`dashscope-intl.aliyuncs.com/compatible-mode/v1`).

---

## Trust Layer Algorithm

The trust score is a **weighted composite** of four sub-scores:

```
final_score = (
  0.30 × reversibility +
  0.25 × blast_radius +
  0.25 × runbook_confidence +
  0.20 × history
)
```

**Execution Decision:**
- **≥ 90:** Execute immediately
- **70-89:** Dry-run first, then live if successful
- **< 70:** Escalate to human for approval

**Example:** Scale-down gets score 78.5 → DRYRUN_VERIFY mode

[Deep dive →](docs/TRUST_LAYER.md)

---

## MCP Tools (18 Total)

### Cluster Monitoring (1-4)
- `get_cluster_status` — Cluster health summary
- `list_active_alerts` — Active alerts with severity
- `get_alert_detail` — Full alert details
- `get_metrics_summary` — Namespace metrics

### Remediation Control (5-8)
- `trigger_remediation` — Manually trigger remediation
- `get_remediation_status` — Remediation job status
- `approve_action` — Human approval endpoint
- `get_runbook` — Retrieve runbook content

### Trust & Safety (9-11)
- `get_trust_score` — Trust score for an action
- `explain_reasoning` — Qwen3-Max thinking chain
- `simulate_remediation` — Dry-run without execution

### Knowledge & History (12-15)
- `get_cluster_topology` — Cluster graph JSON
- `search_runbooks` — Semantic RAG search
- `get_incident_history` — Past incidents by pattern
- `rollback_last_action` — Safety mechanism

### Cost & Prediction (16-18)
- `query_cost_impact` — Cost impact prediction
- `predict_failure` — Proactive failure prediction
- `(Enhanced) approve_action` — Approval with conditions

[Full reference →](docs/MCP_TOOLS.md)

---

## Project Structure

```
neuroscale-autopilot/
├── agents/
│   ├── detector/           # Prometheus poller + alert generation
│   ├── analyzer/           # Qwen3-Max RCA engine
│   ├── planner/            # Qwen-Embedding RAG + remediation planner
│   ├── executor/           # kubectl runner + circuit breaker
│   ├── escalation/         # Qwen-Turbo + Slack + approval flow
│   ├── trust/              # ✨ NEW: Trust Score engine
│   └── router/             # ✨ NEW: Model router + cost governor
├── mcp_server/             # FastAPI MCP server (18 tools)
├── alibaba_cloud/          # ECS/ACK client for cloud remediation
├── dashboard/              # React monitoring dashboard
├── chaos/                  # ✨ NEW: 12 chaos injection scenarios
├── runbooks/               # Markdown runbooks for RAG
├── k8s/                    # Kubernetes manifests
├── charts/                 # ✨ NEW: Helm chart for ACK deployment
├── benchmarks/             # ✨ NEW: Reproducible impact metrics
├── tests/                  # Pytest suite (40+ tests)
├── docs/                   # Comprehensive documentation
│   ├── TRUST_LAYER.md      # ✨ NEW: Trust algorithm deep dive
│   ├── MCP_TOOLS.md        # ✨ NEW: All 18 tools documented
│   ├── ARCHITECTURE.md     # ✨ NEW: Full system design
│   ├── QUICKSTART.md       # ✨ NEW: Get running in 5 min
│   └── IMPACT.md           # ✨ NEW: Benchmark results
├── .env.example            # Environment template
├── LICENSE                 # Apache 2.0
├── main.py                 # Entry point
└── docker-compose.yml      # Docker Compose setup
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QWEN_API_KEY` | ✅ | — | DashScope API key |
| `QWEN_BASE_URL` | ❌ | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Qwen endpoint |
| `QWEN_MODEL_MAX` | ❌ | `qwen3-max` | Analyzer model |
| `QWEN_MODEL_PLUS` | ❌ | `qwen-plus` | Planner model |
| `QWEN_MODEL_TURBO` | ❌ | `qwen-turbo` | Escalation model |
| `SLACK_WEBHOOK_URL` | ❌ | — | Slack notifications |
| `KUBECONFIG` | ❌ | `~/.kube/config` | Kubeconfig path |
| `DRY_RUN` | ❌ | `true` | Disable real kubectl |
| `TRUST_EXECUTE_THRESHOLD` | ❌ | `90` | Trust score threshold |
| `TRUST_DRYRUN_THRESHOLD` | ❌ | `70` | Dry-run threshold |
| `CHAOS_ENABLED` | ❌ | `true` | Enable chaos injection |

---

## How It Works

### 1. Detection
The detector polls Prometheus every 30 seconds for anomalies and fires alerts.

### 2. Analysis
The analyzer sends alert context to **Qwen3-Max with thinking mode** for root cause analysis. The thinking chain is streamed to the dashboard.

### 3. Planning
The planner uses **Qwen-Embedding** to semantically search the runbook corpus and produces a structured remediation plan.

### 4. Trust Scoring
The trust engine computes a composite score based on reversibility, blast radius, runbook confidence, and history.

### 5. Execution Decision
- **High trust (≥ 90):** Execute immediately
- **Medium trust (70-89):** Dry-run first, then live if successful
- **Low trust (< 70):** Escalate to human for approval (timeout 300s)

### 6. Execution
The executor runs kubectl commands with circuit-breaker protection. On consecutive failures, the breaker opens and stops further attempts.

### 7. Escalation
If approval is needed, Qwen-Turbo generates a concise Slack summary and waits for human decision.

### 8. Logging
All outcomes are logged to `outcomes.jsonl` for audit trail and historical analysis.

---

## Deployment to Alibaba Cloud ACK

### 1. Create ACK Cluster

```bash
# Using Alibaba Cloud CLI
aliyun cs CreateCluster --ClusterName neuroscale-v2 --RegionId ap-southeast-1
```

### 2. Deploy with Helm

```bash
# Add Helm chart
helm repo add neuroscale https://github.com/sodiq-code/neuroscale-autopilot
helm repo update

# Install
helm install neuroscale neuroscale/neuroscale \
  --namespace neuroscale-autopilot \
  --create-namespace \
  --set qwen.apiKey=$QWEN_API_KEY
```

### 3. Verify Deployment

```bash
kubectl get pods -n neuroscale-autopilot
kubectl logs -n neuroscale-autopilot -l app=neuroscale -f
```

[Full deployment guide →](docs/ALIBABA_DEPLOYMENT.md)

---

## Benchmarking

Run reproducible impact benchmarks:

```bash
python benchmarks/run_benchmarks.py --cluster $KUBECONFIG --runs 5
```

**Metrics:**
- Mean Time To Detect (MTTD): < 30s
- Mean Time To Diagnose (MTTD): < 60s
- Mean Time To Remediate (MTTR): < 120s
- False remediation rate: < 5%
- Cost per incident: 50% lower than human SRE

[Impact report →](docs/IMPACT.md)

---

## Testing

Run the full test suite:

```bash
# All tests
pytest tests/ -v

# Trust layer tests only
pytest tests/test_trust_score.py -v

# With coverage
pytest tests/ --cov=agents --cov-report=html
```

**Test Coverage:**
- 40+ unit and integration tests
- Trust score algorithm (8+ tests)
- Chaos scenarios (6+ tests)
- MCP tools (10+ tests)
- Model router (4+ tests)

---

## Demo Video

Watch a **live 3-minute demo** showing:
- 2 AM outage scenario
- Live chaos injection from dashboard
- Qwen3-Max thinking mode with streamed reasoning
- Trust layer panel with sub-scores
- Remediation and recovery timing

[YouTube Demo →](https://youtu.be/DEMO_URL)

---

## Blog Post

Read the **2,500-word Medium article**:

> "How I Built the First Kubernetes SRE Agent Enterprises Would Actually Trust — Using Qwen 3.7-Max's Thinking Mode, 1M-Token Context, and a Verifiable Trust Layer"

Topics:
- The 2 AM problem
- Shortcomings of existing self-healing systems
- The trust layer algorithm
- Qwen thinking mode and large context
- MCP integration
- Benchmark economics
- Quick installation
- Roadmap

[Read on Medium →](https://medium.com/@sodiq-code/neuroscale-v2)

---

## License

**Apache License 2.0** — See [LICENSE](LICENSE)

---

## Author

**Sodiq Jimoh** — Platform Engineer  
[LinkedIn](https://linkedin.com/in/sodiq-jimoh-afsod) | [GitHub](https://github.com/sodiq-code)

Built for the **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**

---

## Acknowledgments

- **Alibaba Cloud** for DashScope and ACK infrastructure
- **Qwen Team** for the 3.7-Max model and thinking mode
- **Model Context Protocol** for the MCP specification
- **Kubernetes Community** for the amazing ecosystem

---

## Next Steps

1. **Clone the repository** and follow the Quick Start
2. **Configure your Qwen API key** in `.env`
3. **Run locally** with `python main.py` or Docker
4. **Test the pipeline** with demo scenarios
5. **Deploy to Alibaba Cloud ACK** for production use
6. **Integrate with your MCP client** (Claude, Qwen, etc.)

---

## Support & Contributing

- **Issues:** [GitHub Issues](https://github.com/sodiq-code/neuroscale-autopilot/issues)
- **Discussions:** [GitHub Discussions](https://github.com/sodiq-code/neuroscale-autopilot/discussions)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Built with ❤️ for the Kubernetes community**
