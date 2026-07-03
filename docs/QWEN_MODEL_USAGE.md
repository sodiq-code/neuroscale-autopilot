# Qwen Model Usage Guide

## Overview

NeuroScale v2 uses multiple Qwen models strategically to balance cost, latency, and accuracy.

## Model Selection Matrix

| Use Case | Model | Context | Thinking | Latency | Cost | When to Use |
|----------|-------|---------|----------|---------|------|------------|
| **Critical RCA** | qwen3-max | 1M tokens | ✅ Yes | 5-30s | High | Production incidents, complex diagnosis |
| **Standard Diagnosis** | qwen-plus | 128K tokens | ❌ No | 2-5s | Medium | Standard alerts, routine remediation |
| **Simple Summary** | qwen-turbo | 8K tokens | ❌ No | 1-2s | Low | Alert deduplication, escalation summary |
| **Embeddings** | text-embedding-v3 | N/A | N/A | <1s | Very Low | Semantic search, runbook matching |
| **Escalation** | qwen-turbo | 8K tokens | ❌ No | 1-2s | Low | Human escalation messages |

## Model Specifications

### Qwen3-Max (Thinking Mode)

**Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`  
**Model ID:** `qwen3-max`  
**Context Window:** 1,000,000 tokens  
**Thinking Mode:** ✅ Supported  
**Output Tokens:** Up to 8,000  

**Use Cases:**
- Deep root cause analysis
- Complex multi-factor diagnosis
- Generating kubectl YAML patches
- Streaming reasoning to dashboard

**Example Request:**
```python
response = await client.chat.completions.create(
    model="qwen3-max",
    messages=[
        {"role": "system", "content": "You are a Kubernetes SRE expert."},
        {"role": "user", "content": "Analyze this OOMKilled pod..."}
    ],
    extra_body={"enable_thinking": True},
    stream=True,
    temperature=0.7,
    max_tokens=4000
)
```

**Cost:** ~$0.10 per incident (with thinking)  
**Latency:** 5-30 seconds  
**Accuracy:** 98%+  

### Qwen-Plus

**Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`  
**Model ID:** `qwen-plus`  
**Context Window:** 128,000 tokens  
**Thinking Mode:** ❌ Not supported  
**Output Tokens:** Up to 2,000  

**Use Cases:**
- Standard incident diagnosis
- Runbook matching
- Alert correlation
- Cost impact analysis

**Example Request:**
```python
response = await client.chat.completions.create(
    model="qwen-plus",
    messages=[
        {"role": "user", "content": "What's causing this CrashLoop?"}
    ],
    temperature=0.5,
    max_tokens=1000
)
```

**Cost:** ~$0.03 per incident  
**Latency:** 2-5 seconds  
**Accuracy:** 95%  

### Qwen-Turbo

**Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`  
**Model ID:** `qwen-turbo`  
**Context Window:** 8,000 tokens  
**Thinking Mode:** ❌ Not supported  
**Output Tokens:** Up to 1,000  

**Use Cases:**
- Simple alert deduplication
- Escalation message generation
- Quick summaries
- Lightweight analysis

**Example Request:**
```python
response = await client.chat.completions.create(
    model="qwen-turbo",
    messages=[
        {"role": "user", "content": "Summarize this alert"}
    ],
    temperature=0.3,
    max_tokens=500
)
```

**Cost:** ~$0.01 per incident  
**Latency:** 1-2 seconds  
**Accuracy:** 90%  

### Text-Embedding-V3

**Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`  
**Model ID:** `text-embedding-v3`  
**Embedding Dimension:** 1,024  
**Input Tokens:** Up to 8,000  

**Use Cases:**
- Semantic search over runbooks
- Alert similarity matching
- Incident clustering
- Knowledge base retrieval

**Example Request:**
```python
response = await client.embeddings.create(
    model="text-embedding-v3",
    input="OOMKilled pod in production"
)
embedding = response.data[0].embedding  # 1024-dim vector
```

**Cost:** ~$0.0001 per 1K tokens  
**Latency:** <1 second  

## Routing Logic

### Critical Incident Flow

```
Alert Received
    ↓
Severity = CRITICAL?
    ├─ YES → Route to Qwen3-Max (thinking mode)
    │        ├─ Stream reasoning to dashboard
    │        ├─ Generate YAML patch
    │        └─ Return detailed RCA
    │
    └─ NO → Severity = STANDARD?
             ├─ YES → Route to Qwen-Plus
             │        ├─ Standard diagnosis
             │        ├─ Runbook matching
             │        └─ Return action plan
             │
             └─ NO → Route to Qwen-Turbo
                      ├─ Quick summary
                      ├─ Alert deduplication
                      └─ Return escalation message
```

### Cost-Aware Routing

```
Budget Remaining?
    ├─ HIGH (>80%) → Use Qwen3-Max for better accuracy
    ├─ MEDIUM (50-80%) → Use Qwen-Plus for balance
    └─ LOW (<50%) → Use Qwen-Turbo to conserve budget
```

## Configuration

### Environment Variables

```bash
# DashScope API Configuration
export DASHSCOPE_API_KEY="sk-..."
export DASHSCOPE_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

# Model Selection
export NEUROSCALE_CRITICAL_MODEL="qwen3-max"
export NEUROSCALE_STANDARD_MODEL="qwen-plus"
export NEUROSCALE_SIMPLE_MODEL="qwen-turbo"
export NEUROSCALE_EMBEDDING_MODEL="text-embedding-v3"

# Thinking Mode
export NEUROSCALE_ENABLE_THINKING="true"
export NEUROSCALE_THINKING_MAX_TOKENS="4000"

# Cost Limits
export NEUROSCALE_MAX_COST_PER_INCIDENT="0.50"
export NEUROSCALE_MONTHLY_BUDGET="500"
```

### Configuration File

```yaml
# agents/router/models.yaml
models:
  critical_rca:
    model: qwen3-max
    thinking_enabled: true
    max_tokens: 4000
    temperature: 0.7
    
  standard_analysis:
    model: qwen-plus
    thinking_enabled: false
    max_tokens: 2000
    temperature: 0.5
    
  simple_summary:
    model: qwen-turbo
    thinking_enabled: false
    max_tokens: 1000
    temperature: 0.3
    
  embedding:
    model: text-embedding-v3
    dimension: 1024

cost_limits:
  per_incident_max: 0.50
  monthly_budget: 500
  
routing:
  critical_threshold: 0.8
  standard_threshold: 0.5
  cost_aware: true
```

## Prompt Engineering

### System Prompts

**For Qwen3-Max (Thinking Mode):**
```
You are an expert Kubernetes SRE with 10+ years of experience.
Your task is to deeply analyze production incidents.

Use your thinking capability to:
1. Break down the problem systematically
2. Consider multiple root causes
3. Evaluate trade-offs
4. Generate concrete solutions

Always provide:
- Step-by-step reasoning
- Root cause analysis
- Concrete kubectl commands or YAML patches
- Confidence level (0-1)
```

**For Qwen-Plus (Standard):**
```
You are a Kubernetes troubleshooting expert.
Analyze the incident and provide a remediation plan.

Be concise and actionable.
```

**For Qwen-Turbo (Simple):**
```
Summarize this alert in one sentence.
```

### Example Prompts

**Critical RCA (Qwen3-Max):**
```
Analyze this OOMKilled pod incident:

Pod: payment-service-abc123
Namespace: production
Memory Limit: 512Mi
Memory Usage: 650Mi
Restart Count: 5

Cluster State:
- Node has 8Gi available
- 3 other pods in same deployment
- HPA enabled with 2-10 replicas

Provide:
1. Root cause analysis
2. Why this happened
3. Concrete kubectl patch to fix
4. Confidence level
```

**Standard Diagnosis (Qwen-Plus):**
```
CrashLoop alert for web-server deployment.
Last 3 restarts: OOMKilled, Segmentation fault, OOMKilled.
CPU: 100m, Memory: 256Mi.

What's the likely cause and fix?
```

**Simple Summary (Qwen-Turbo):**
```
Alert: High CPU usage (95%) on node-5 for 10 minutes.
Summary?
```

## Performance Tuning

### Temperature Settings

| Model | Use Case | Temperature | Rationale |
|-------|----------|-------------|-----------|
| qwen3-max | Deep analysis | 0.7 | Creative reasoning |
| qwen-plus | Standard diagnosis | 0.5 | Balanced |
| qwen-turbo | Quick summary | 0.3 | Deterministic |

### Token Limits

| Model | Max Tokens | Typical Output | Headroom |
|-------|-----------|----------------|----------|
| qwen3-max | 4,000 | 1,000-2,000 | 50% |
| qwen-plus | 2,000 | 500-1,000 | 50% |
| qwen-turbo | 1,000 | 100-300 | 70% |

### Streaming Configuration

**Enable streaming for:**
- Qwen3-Max (to show thinking in real-time)
- Long-running analyses

**Disable streaming for:**
- Qwen-Turbo (too fast to stream)
- Synchronous operations

## Cost Optimization

### Budget Management

```python
from agents.router.cost_governor import CostGovernor

governor = CostGovernor(monthly_budget=500)

# Check budget before routing
if governor.can_afford_qwen3max():
    model = "qwen3-max"
else:
    model = "qwen-plus"

# Track cost per incident
cost = governor.track_incident(model, tokens_used)
```

### Cost Reduction Strategies

1. **Use Qwen-Turbo for simple alerts** — 10x cheaper
2. **Batch similar incidents** — Reduce API calls
3. **Cache embeddings** — Reuse runbook matches
4. **Limit thinking tokens** — Set max_tokens appropriately
5. **Monitor budget** — Alert when approaching limit

## Troubleshooting

### Issue: Qwen3-Max thinking mode not working

**Solution:**
```python
# Ensure extra_body parameter is set
response = await client.chat.completions.create(
    model="qwen3-max",
    messages=[...],
    extra_body={"enable_thinking": True},  # ← Required
    stream=True
)
```

### Issue: Embeddings dimension mismatch

**Solution:**
```python
# text-embedding-v3 always returns 1024-dim vectors
embedding = response.data[0].embedding
assert len(embedding) == 1024
```

### Issue: Rate limiting

**Solution:**
```python
# Implement exponential backoff
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_qwen_with_retry():
    return await client.chat.completions.create(...)
```

## Monitoring

### Key Metrics

- `qwen_api_calls_total` — Total API calls by model
- `qwen_api_cost_total` — Total cost by model
- `qwen_api_latency_seconds` — Latency distribution
- `qwen_thinking_tokens_used` — Thinking mode token usage
- `qwen_model_selection_count` — Routing decisions

### Alerts

```yaml
- alert: QwenBudgetExceeded
  expr: qwen_api_cost_total > 500
  for: 1m
  
- alert: QwenLatencyHigh
  expr: qwen_api_latency_seconds > 30
  for: 5m
  
- alert: QwenThinkingTokensHigh
  expr: qwen_thinking_tokens_used > 3000
  for: 1m
```

## Best Practices

1. **Always use thinking mode for critical incidents** — Better accuracy
2. **Stream reasoning to dashboard** — Transparency
3. **Cache embeddings** — Reduce API calls
4. **Monitor cost** — Stay within budget
5. **Use fallback models** — Handle API failures gracefully
6. **Test prompts** — Validate before production
7. **Log all API calls** — Audit trail
8. **Set appropriate timeouts** — Prevent hanging

---

**Documentation Version:** v2.0.0  
**Last Updated:** 2026-07-04  
**Status:** Production Ready
