# NeuroScale v2 Trust Layer — Technical Deep Dive

## Overview

The Trust Layer is the core innovation of NeuroScale v2. It is a **verifiable, explainable trust scoring algorithm** that gates all remediation actions. Before any action is executed, the system computes a trust score that reflects the confidence in the remediation plan. This score determines whether the action is executed immediately, verified with a dry-run first, or escalated to a human operator.

## The Problem

Traditional Kubernetes self-healing systems face a critical trust gap:

- **Too conservative:** They require human approval for every action, defeating the purpose of automation.
- **Too aggressive:** They execute actions without verification, risking cascading failures.
- **Opaque:** Operators cannot understand why an action was taken or rejected.

The Trust Layer solves this by providing a **transparent, quantified measure of action safety**.

## The Algorithm

The trust score is a **weighted composite of four sub-scores**, each measuring a different aspect of action safety:

```
final_score = (
  0.30 × reversibility_score +
  0.25 × blast_radius_score +
  0.25 × runbook_confidence_score +
  0.20 × history_score
)
```

### Sub-Score 1: Reversibility (Weight: 0.30)

**Question:** Can the action be undone if something goes wrong?

**Scoring:**
- Fully reversible (e.g., scale-up, rollback): 90-100
- Partially reversible (e.g., config patch with backup): 70-80
- Difficult to reverse (e.g., delete): 30-40
- Non-reversible (e.g., data deletion): 10-20

**Factors:**
- Action type (scale-up is more reversible than delete)
- Resource type (Pods are ephemeral, PersistentVolumes have state)
- Backup availability
- Rollback plan presence

**Example:**
```python
# Scale-up is highly reversible
reversibility_score = 95

# Delete is low reversibility
reversibility_score = 20
```

### Sub-Score 2: Blast Radius (Weight: 0.25)

**Question:** How many resources could be affected?

**Scoring:**
- Single resource: 90-100 (very safe)
- 2-5 resources: 80 (safe)
- 6-10 resources: 60 (moderate)
- 11-50 resources: 40 (risky)
- 50+ resources: 20 (very risky)

**Factors:**
- Action type (pod-level vs. node-level vs. cluster-level)
- Resource replicas
- Pods on a node (for node operations)
- Resources in a namespace (for namespace operations)

**Example:**
```python
# Deleting a single pod
affected_count = 1
blast_radius_score = 95

# Draining a node with 50 pods
affected_count = 50
blast_radius_score = 20
```

### Sub-Score 3: Runbook Confidence (Weight: 0.25)

**Question:** How confident is the remediation plan?

**Scoring:**
- Exact match with high success history: 90-100
- Good match with moderate success: 70-80
- Generic runbook: 50-60
- Uncertain match: 30-40
- No runbook found: 20

**Factors:**
- Semantic similarity to known runbooks (0-1)
- Margin between top and second-best match
- Plan completeness (steps, parameters, validation)
- Rollback plan presence
- Historical success rate of the runbook

**Example:**
```python
# High semantic similarity to a known runbook
retrieval_score = 0.95
retrieval_margin = 0.5
runbook_confidence_score = 95

# No runbook found
runbook_confidence_score = 20
```

### Sub-Score 4: History (Weight: 0.20)

**Question:** What is the historical success rate for this action type?

**Scoring:**
- High success rate (>90%): 85-100
- Good success rate (70-90%): 70-85
- Moderate success rate (50-70%): 50-70
- Low success rate (<50%): 30-50
- No history: 50 (neutral)

**Factors:**
- Total attempts of this action type
- Successful attempts
- Confidence adjustment based on sample size

**Example:**
```python
# 100 scale-down attempts, 95 successful
success_rate = 0.95
history_score = 95

# 2 delete attempts, 1 successful
success_rate = 0.5
history_score = 50  # Low confidence due to small sample
```

## Execution Modes

The final trust score determines the execution mode:

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 90 | **EXECUTE** | Execute remediation immediately without dry-run |
| 70-89 | **DRYRUN_VERIFY** | Perform dry-run first, then execute if successful |
| < 70 | **ESCALATE_HUMAN** | Wait for human approval (timeout 300s) |

### EXECUTE Mode (Score ≥ 90)

- **When:** High-confidence, low-risk actions
- **Examples:** Scale-up, rollback, config patch with backup
- **Behavior:** Remediation is executed immediately
- **Timeout:** None (immediate execution)

### DRYRUN_VERIFY Mode (Score 70-89)

- **When:** Moderate-confidence actions
- **Examples:** Scale-down, patch without backup
- **Behavior:** 
  1. Execute action in dry-run mode (no actual changes)
  2. Verify dry-run output
  3. If dry-run succeeds, execute live
  4. If dry-run fails, escalate to human
- **Timeout:** None (dry-run is fast)

### ESCALATE_HUMAN Mode (Score < 70)

- **When:** Low-confidence or high-risk actions
- **Examples:** Delete operations, untested runbooks
- **Behavior:**
  1. Generate Slack notification with action details
  2. Wait for human approval
  3. Timeout after 300 seconds
  4. Auto-reject on timeout (safety-first)
- **Timeout:** 300 seconds

## Audit Trail

Every trust score computation is logged to `outcomes.jsonl` for audit trail and compliance:

```json
{
  "final_score": 85.5,
  "execution_mode": "dryrun_verify",
  "reversibility_score": 80.0,
  "blast_radius_score": 90.0,
  "runbook_confidence_score": 85.0,
  "history_score": 75.0,
  "reasoning": "Trust score 85.5 in range [70, 90). Dry-run first, then live if successful.",
  "timestamp": "2026-07-03T22:30:00Z",
  "action_id": "action-12345",
  "alert_id": "alert-67890"
}
```

## Configuration

Trust thresholds and weights can be customized in `agents/trust/policies.yaml`:

```yaml
thresholds:
  execute_live: 90
  dryrun_and_verify: 70
  human_escalation: 0

weights:
  reversibility: 0.30
  blast_radius: 0.25
  runbook_confidence: 0.25
  history: 0.20
```

Action-specific overrides are also supported:

```yaml
action_overrides:
  delete_pod:
    execute_threshold: 85
    dryrun_threshold: 65
  delete_resource:
    execute_threshold: 95
    dryrun_threshold: 80
```

## Integration Points

### 1. Orchestrator Integration

The orchestrator calls the trust score engine before executing any action:

```python
trust_result = trust_engine.compute_score(
    alert_id=alert.id,
    action_id=action.id,
    action_type=action.type,
    target_resource=action.target,
    remediation_plan=plan,
    cluster_state=cluster_state,
)

if trust_result.execution_mode == ExecutionMode.EXECUTE:
    await executor.execute(action)
elif trust_result.execution_mode == ExecutionMode.DRYRUN_VERIFY:
    dryrun_result = await executor.dryrun(action)
    if dryrun_result.success:
        await executor.execute(action)
    else:
        await escalation.escalate(action, dryrun_result)
else:
    await escalation.escalate(action, trust_result)
```

### 2. Dashboard Integration

The React dashboard displays the trust score panel:

```jsx
<TrustPanel
  finalScore={85.5}
  executionMode="dryrun_verify"
  subScores={{
    reversibility: 80.0,
    blastRadius: 90.0,
    runbookConfidence: 85.0,
    history: 75.0,
  }}
  reasoning="Trust score 85.5 in range [70, 90)..."
/>
```

### 3. MCP Tool Integration

The trust score is exposed via MCP tool `get_trust_score`:

```python
@mcp_server.tool()
async def get_trust_score(alert_id: str, action_id: str) -> Dict[str, Any]:
    """Get the trust score for an action."""
    result = trust_engine.compute_score(...)
    return asdict(result)
```

## Examples

### Example 1: High-Confidence Scale-Up

**Action:** Scale deployment from 3 to 5 replicas

**Sub-scores:**
- Reversibility: 100 (fully reversible)
- Blast Radius: 90 (only affects 2 new pods)
- Runbook Confidence: 95 (exact match, high success history)
- History: 90 (100+ scale-ups, 98% success rate)

**Final Score:** 0.30×100 + 0.25×90 + 0.25×95 + 0.20×90 = **94.0**

**Execution Mode:** EXECUTE (immediate)

### Example 2: Moderate-Confidence Config Patch

**Action:** Patch ConfigMap with new settings

**Sub-scores:**
- Reversibility: 75 (partially reversible, backup available)
- Blast Radius: 80 (affects 5 pods)
- Runbook Confidence: 70 (good match, moderate success history)
- History: 65 (20 config patches, 70% success rate)

**Final Score:** 0.30×75 + 0.25×80 + 0.25×70 + 0.20×65 = **73.0**

**Execution Mode:** DRYRUN_VERIFY (dry-run first)

### Example 3: Low-Confidence Delete

**Action:** Delete a pod

**Sub-scores:**
- Reversibility: 20 (non-reversible)
- Blast Radius: 95 (single pod)
- Runbook Confidence: 30 (no runbook found)
- History: 40 (5 deletes, 2 successful)

**Final Score:** 0.30×20 + 0.25×95 + 0.25×30 + 0.20×40 = **43.0**

**Execution Mode:** ESCALATE_HUMAN (wait for approval)

## Validation & Testing

The Trust Layer includes comprehensive test coverage:

- **Unit tests:** Each sub-score analyzer has dedicated tests
- **Integration tests:** End-to-end trust score computation
- **Edge case tests:** Boundary conditions, missing data, extreme values
- **Audit tests:** Outcomes logging and retrieval

Run tests with:

```bash
pytest tests/test_trust_score.py -v
```

## Future Enhancements

Potential improvements to the Trust Layer:

1. **Machine learning:** Use historical outcomes to optimize weights
2. **Contextual scoring:** Adjust scores based on time of day, cluster load, etc.
3. **Multi-action plans:** Score composite plans with multiple actions
4. **Feedback loops:** Incorporate operator feedback to improve scoring
5. **Anomaly detection:** Detect unusual action patterns

## References

- [Trust Layer Policies](../agents/trust/policies.yaml)
- [Trust Score Engine](../agents/trust/score.py)
- [Test Suite](../tests/test_trust_score.py)
