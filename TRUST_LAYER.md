# The Trust Layer

> **NeuroScale Autopilot doesn't just fix your cluster — it proves the fix is safe before it acts, and knows when to stop and ask a human.**

Everyone building "AI agents that act" in this hackathon. We built the one that knows when **not** to act.

## Why Trust Is the Product, Not a Feature

An agent that auto-remediates *everything* isn't impressive — it's dangerous. Real SRE teams don't want an agent that confidently executes the wrong fix. They want an agent that:

1. Explains what it thinks happened (root cause)
2. Says how confident it is
3. Knows the blast radius of its proposed fix
4. Refuses to act alone when the evidence is thin
5. Always leaves a rollback path

That is the entire premise of the Trust Layer. It sits between **diagnosis** and **execution**, and it is the difference between "an agent that fixed it" and "an agent you can trust in production."

## How the Score Is Built

Every incident that flows through the pipeline (Detector → Analyzer → Planner → Executor → Escalation) accumulates a decision record with five real, inspectable signals:

| Signal | What it measures | Where it comes from |
|---|---|---|
| **Analyzer confidence** | How sure Qwen-Max is about the root cause | LLM-reported confidence: high / medium / low |
| **Runbook retrieval score** | How close the matched runbook is to this incident | Cosine similarity from `text-embedding-v3` RAG search |
| **Retrieval margin** | Gap between best and second-best runbook match | Used to catch ambiguous matches — a close 2nd place means "not sure" |
| **Risk level** | Blast radius / reversibility of the proposed action | Analyzer-assigned, informed by action type (restart vs. delete vs. scale) |
| **Auto-remediate flag** | The final yes/no gate | `True` only when confidence is high AND retrieval score clears threshold (0.65) AND risk is low |

If **any** of these signals fall short, `requires_approval` flips to `true` and the incident stops for a human, with a plain-English reason attached. This isn't a UI trick — it's read directly from the pipeline's own decision object and rendered as-is.

### Real example, captured live from this deployment

During testing on the actual Alibaba Cloud cluster, the system caught its own retrieval failure and refused to guess:

> *"Risk level is high. Analyzer confidence is low. Runbook retrieval confidence is low — top match is ambiguous. A wrong runbook executed confidently is worse than no runbook. Analyzer recommends human review. Please approve or reject this remediation."*

That sentence — generated automatically by the Planner agent, not hand-written for a demo — is the Trust Layer working exactly as designed: it would rather escalate than act on a shaky match.

## The Decision Card

Every incident in the dashboard renders as a decision card with:

- **Root Cause** — the Analyzer's diagnosis
- **Confidence / Risk / Auto-remediate** — the three headline signals
- **Reasoning trace** — expandable, so the "why" is never hidden
- **Remediation Plan** — runbook name, ETA, and exact rollback command
- **Approve / Reject** — the human checkpoint, front and center

This is deliberately not a wall of raw model tokens. Judges (and real operators) don't need to read an LLM's stream-of-consciousness — they need the five signals above and a clear action.

## What Happens When the Model Itself Fails

A trust system has to be honest about its own failure modes too. During this deployment, the Qwen model calls were temporarily blocked by an account-level model-activation issue on Alibaba Cloud's side (not a code bug). Rather than crash, retry silently, or fabricate an answer, the system did exactly what it's designed to do when it can't get a confident signal:

- Marked confidence as `low`
- Marked risk as `high`
- Set `auto_remediate: false`
- Escalated to human approval with the real error surfaced in the reasoning trace

That is the Trust Layer holding up under a real degraded-dependency scenario — not a scripted demo, an actual live failure captured on the production dashboard.

## Reversibility Is Non-Negotiable

Every remediation plan the Planner produces carries an explicit `rollback_plan` field. No plan is proposed — automatically or for approval — without a documented way back. For Kubernetes-native actions this is typically a one-line `kubectl rollout undo`, but the point isn't the specific command: it's that **the system never proposes a one-way door.**

## Summary

| Question a judge might ask | Answer |
|---|---|
| Does it solve a real problem? | Yes — unsafe autonomous remediation in production Kubernetes |
| Why is it safer than "just an agent that acts"? | It scores confidence, retrieval quality, and risk before every action, and refuses to act when any signal is weak |
| Why does Qwen matter specifically? | Qwen-Max drives root-cause reasoning, `text-embedding-v3` drives runbook retrieval confidence, Qwen-Turbo drives human-readable escalation — three different models doing three different trust-relevant jobs |
| Could this run tomorrow? | Yes — it's deployed right now on a real Alibaba Cloud ECS instance running a real k3s cluster, watching a real deployment |
| What will you remember about this tomorrow? | *The one that refuses unsafe remediations unless they pass its Trust Layer.* |
