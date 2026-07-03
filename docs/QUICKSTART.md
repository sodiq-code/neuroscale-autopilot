# NeuroScale Autopilot v2 — Quick Start (5 Minutes)

## Prerequisites

- Docker & Docker Compose
- kubectl (v1.24+)
- Python 3.11+
- Qwen API key (free tier available)

## Step 1: Clone Repository (30 seconds)

```bash
git clone https://github.com/sodiq-code/neuroscale-autopilot.git
cd neuroscale-autopilot
git checkout v2-trust-layer
```

## Step 2: Set Environment Variables (1 minute)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
export QWEN_API_KEY="sk-your-api-key-here"
export DASHSCOPE_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
```

**Get a free Qwen API key:**
1. Visit https://dashscope.aliyun.com
2. Sign up for free tier
3. Create API key
4. Copy key to `.env`

## Step 3: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

## Step 4: Start Services (1 minute)

### Option A: Docker Compose (Recommended)

```bash
docker-compose up -d
```

This starts:
- NeuroScale API (port 8000)
- MCP Server (port 8001)
- Dashboard (port 3000)
- Prometheus (port 9090)

### Option B: Local Development

```bash
# Terminal 1: Start API
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Start Dashboard
cd dashboard && npm start

# Terminal 3: Start MCP Server
python mcp_server/server.py
```

## Step 5: Verify Installation (1 minute)

```bash
# Check API health
curl http://localhost:8000/health

# Check MCP Server
curl http://localhost:8001/tools

# Open Dashboard
open http://localhost:3000
```

Expected output:
```json
{
  "status": "healthy",
  "version": "v2.0.0",
  "trust_layer": "enabled"
}
```

## Step 6: Run Your First Incident (1 minute)

### Inject a Chaos Scenario

```bash
# Trigger an OOMKilled pod
curl -X POST http://localhost:8000/chaos/inject/oomkilled \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "pod_name": "test-pod"}'
```

### Watch the Magic

1. **Dashboard** (http://localhost:3000):
   - See the alert appear
   - Watch Qwen thinking in real-time
   - View trust score calculation
   - See remediation execute

2. **API Logs**:
   ```bash
   docker logs neuroscale-api | tail -f
   ```

3. **Outcomes Log**:
   ```bash
   tail -f outcomes.jsonl
   ```

## Common Commands

### Run Benchmarks

```bash
# Run 5 iterations of all scenarios
python benchmarks/run_benchmarks.py --runs 5

# Compare to industry baseline
python benchmarks/baseline_human.py
```

### View Trust Scores

```bash
# Get latest trust scores
curl http://localhost:8000/trust/scores

# Get specific incident
curl http://localhost:8000/trust/scores/alert-123
```

### Access MCP Tools

```bash
# List all 18 tools
curl http://localhost:8001/tools

# Call a tool
curl -X POST http://localhost:8001/tools/get_cluster_topology \
  -H "Content-Type: application/json" \
  -d '{}'
```

### View Outcomes

```bash
# Pretty-print outcomes
cat outcomes.jsonl | jq .

# Filter by execution mode
cat outcomes.jsonl | jq 'select(.execution_mode == "execute")'

# Get statistics
cat outcomes.jsonl | jq -s 'group_by(.execution_mode) | map({mode: .[0].execution_mode, count: length})'
```

## Kubernetes Deployment

### Deploy to Local Cluster

```bash
# Create namespace
kubectl create namespace neuroscale-autopilot

# Install Helm chart
helm install neuroscale charts/neuroscale/ \
  --namespace neuroscale-autopilot \
  --set qwen.apiKey=$QWEN_API_KEY

# Verify deployment
kubectl get pods -n neuroscale-autopilot
```

### Deploy to Alibaba Cloud ACK

```bash
# Configure kubectl for ACK
# (Obtain kubeconfig from Alibaba Cloud console)

# Install chart
helm install neuroscale charts/neuroscale/ \
  --namespace neuroscale-autopilot \
  --create-namespace \
  --set qwen.apiKey=$QWEN_API_KEY \
  --set alibaba.region=ap-southeast-1

# Verify
kubectl get svc -n neuroscale-autopilot
```

## Troubleshooting

### Issue: "Connection refused" on localhost:8000

**Solution:**
```bash
# Check if container is running
docker ps | grep neuroscale

# View logs
docker logs neuroscale-api

# Restart
docker-compose restart neuroscale-api
```

### Issue: Qwen API key not recognized

**Solution:**
```bash
# Verify API key
echo $QWEN_API_KEY

# Check .env file
cat .env | grep QWEN_API_KEY

# Restart with new key
docker-compose down
docker-compose up -d
```

### Issue: Dashboard not loading

**Solution:**
```bash
# Check if port 3000 is in use
lsof -i :3000

# Kill process on port 3000
kill -9 <PID>

# Restart
docker-compose restart neuroscale-dashboard
```

### Issue: Benchmarks failing

**Solution:**
```bash
# Check if Kubernetes cluster is available
kubectl cluster-info

# Verify chaos scenarios are installed
python -c "from chaos.scenarios import *; print('OK')"

# Run with verbose output
python benchmarks/run_benchmarks.py --runs 1 --verbose
```

## Next Steps

### 1. Explore the Dashboard

- View real-time trust scores
- Watch Qwen thinking in action
- Trigger manual chaos injections
- Monitor remediation outcomes

### 2. Read the Documentation

- **ARCHITECTURE.md** — System design
- **TRUST_LAYER.md** — Trust algorithm details
- **QWEN_MODEL_USAGE.md** — Model routing
- **MCP_TOOLS.md** — Available tools
- **IMPACT.md** — Benchmark results

### 3. Customize for Your Cluster

- Update runbooks in `runbooks/`
- Adjust trust weights in `agents/trust/policies.yaml`
- Configure model routing in `agents/router/models.yaml`
- Add custom chaos scenarios in `chaos/`

### 4. Integrate with Your Alerts

- Connect Prometheus AlertManager
- Configure webhook to NeuroScale API
- Map alert types to runbooks
- Set up escalation channels

### 5. Monitor in Production

- Set up Prometheus scraping
- Create Grafana dashboards
- Configure alerts for high MTTR
- Track cost per incident

## Performance Expectations

| Metric | Value |
|--------|-------|
| Alert Detection | < 1 min |
| Analysis Time | 5-30 sec |
| Trust Scoring | < 1 sec |
| Remediation | 10-60 sec |
| **Total MTTR** | **30-120 sec** |
| Industry Average | 15-30 min |
| **Speedup** | **16.9x faster** |

## Support

- **GitHub Issues** — https://github.com/sodiq-code/neuroscale-autopilot/issues
- **Documentation** — https://github.com/sodiq-code/neuroscale-autopilot/tree/v2-trust-layer/docs
- **Qwen API Docs** — https://dashscope.aliyun.com/docs

## What's Next?

After getting comfortable with NeuroScale v2:

1. **Deploy to production** — Use Helm chart on Alibaba Cloud ACK
2. **Connect real alerts** — Integrate with your Prometheus setup
3. **Tune trust weights** — Customize for your SLOs
4. **Add custom runbooks** — Extend with your remediation procedures
5. **Monitor & iterate** — Use outcomes.jsonl to improve

---

**Quick Start Version:** v2.0.0  
**Last Updated:** 2026-07-04  
**Estimated Time:** 5 minutes  
**Status:** Production Ready

**Ready to automate your Kubernetes SRE? Let's go! 🚀**
