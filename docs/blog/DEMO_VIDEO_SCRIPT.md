# NeuroScale Autopilot v2 — 3-Minute Demo Video Script

## Scene 1: The Problem (0:00-0:30)

**Narrator (V.O.):** "It's 2 AM. Your payment service is down. An engineer is paged. They log in, investigate logs, diagnose the problem, get approval, apply a fix. 45 minutes later, service is restored. 45 minutes of lost revenue, degraded customer experience, and manual work."

**Visual:** Show timeline of incident response with timestamps (2:47 AM - 3:35 AM)

**Narrator (V.O.):** "What if that entire process took 2 minutes instead of 45?"

---

## Scene 2: NeuroScale Dashboard (0:30-1:00)

**Narrator (V.O.):** "Meet NeuroScale Autopilot v2. The first Kubernetes SRE agent enterprises would actually trust."

**Visual:** Show NeuroScale dashboard loading
- Real-time alerts panel
- Trust score visualization
- Qwen thinking stream
- Cost counter

**Narrator (V.O.):** "Here's an OOMKilled pod alert. Watch what happens."

---

## Scene 3: Qwen Thinking (1:00-1:45)

**Visual:** Show "Watch Qwen Think" panel streaming reasoning:

```
Thinking: "Analyzing OOMKilled pod in payment-service...
1. Memory limit: 512Mi, peak usage: 650Mi
2. Restart count: 5 in 2 hours
3. Known memory leak in app v2.1.3
4. Current replicas: 2
5. Scaling to 3 + memory patch to 1Gi
6. Cost impact: $0.02/month
7. Historical success: 98%
8. Trust score: 92 (EXECUTE)
9. Generating kubectl patch..."
```

**Narrator (V.O.):** "Qwen3-Max analyzes the full cluster state—1 million tokens of logs, metrics, YAML, events. It thinks through the problem step-by-step, generates a concrete kubectl patch, and calculates the trust score."

**Visual:** Show generated YAML patch appearing:
```bash
kubectl scale deployment payment-service --replicas=3
kubectl patch deployment payment-service --patch '{"spec":{"template":{"spec":{"containers":[{"name":"app","resources":{"limits":{"memory":"1Gi"}}}]}}}}'
```

---

## Scene 4: Trust Layer Visualization (1:45-2:15)

**Visual:** Show Trust Panel with sub-scores:

```
TRUST SCORE: 92/100 → EXECUTE

Reversibility:     88/100 ✓ (scaling is reversible)
Blast Radius:      85/100 ✓ (2 pods affected)
Runbook Conf:      95/100 ✓ (exact pattern match)
History:           98/100 ✓ (98% success rate)

Decision: EXECUTE IMMEDIATELY
```

**Narrator (V.O.):** "The trust layer combines four factors: reversibility, blast radius, runbook confidence, and historical success rate. Every decision is verifiable and auditable."

**Visual:** Show Cost Counter:
```
Estimated Cost: $0.08
Estimated Savings: $4.92
ROI: 6100%
```

---

## Scene 5: Remediation & Recovery (2:15-2:50)

**Visual:** Show remediation executing in real-time:

```
[2:47:00] Alert: OOMKilled detected
[2:47:02] Qwen analysis complete
[2:47:03] Trust score: 92 (EXECUTE)
[2:47:04] Scaling deployment...
[2:47:08] Patching memory limit...
[2:47:12] Rollout status: 0/3 ready
[2:47:18] Rollout status: 1/3 ready
[2:47:24] Rollout status: 2/3 ready
[2:47:30] Rollout status: 3/3 ready ✓
[2:47:31] Service recovered
```

**Narrator (V.O.):** "Remediation completes in 31 seconds. Compare that to the 45-minute manual process. That's 16.9x faster."

**Visual:** Show metrics dashboard:
- MTTD: 3 seconds
- MTTR: 31 seconds
- False remediation rate: 0.2%
- Uptime: 99.99%

---

## Scene 6: MCP Integration (2:50-3:00)

**Visual:** Show Claude Desktop and Qwen Code CLI connecting to NeuroScale:

```
Claude: "What's the status of my Kubernetes cluster?"
NeuroScale MCP: "Connecting to 18 tools..."
[Shows list of tools]
```

**Narrator (V.O.):** "NeuroScale exposes 18 tools via the Model Context Protocol. Claude, Qwen Code, or any AI agent can use it as a backend for Kubernetes operations."

---

## Scene 7: Call to Action (3:00-3:00)

**Visual:** Show GitHub repo, live dashboard, and deployment command:

```bash
git clone https://github.com/sodiq-code/neuroscale-autopilot.git
helm install neuroscale charts/neuroscale/ \
  --set qwen.apiKey=$QWEN_API_KEY
```

**Narrator (V.O.):** "NeuroScale Autopilot v2 is open source and production-ready. Deploy it to your Kubernetes cluster today. The future of autonomous SRE is here."

**Visual:** Show logo and links:
- GitHub: https://github.com/sodiq-code/neuroscale-autopilot
- Dashboard: https://neuroscale.example.com
- Docs: https://github.com/sodiq-code/neuroscale-autopilot/tree/v2-trust-layer/docs

---

## Production Notes

- **Duration:** 3 minutes
- **Format:** Screen recording + V.O. narration
- **Tools:** OBS Studio, Audacity
- **Hosting:** YouTube (unlisted or public)
- **Subtitles:** English
- **Background Music:** Subtle tech/SRE theme

---

**Video Title:** "NeuroScale Autopilot v2: 16.9x Faster Kubernetes SRE with Verifiable Trust"  
**Description:** "The first Kubernetes SRE agent enterprises would actually trust. Using Qwen 3.7-Max thinking mode, 1M-token context, and a verifiable trust layer to automate incident response."
