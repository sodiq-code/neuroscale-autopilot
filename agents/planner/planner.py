"""
Planner Agent — Selects the exact remediation runbook using RAG over runbook library.
Uses Qwen embeddings to find the best matching runbook for the RCA.
Implements human-in-the-loop checkpoint for high-risk actions.
"""

import os
import json
import asyncio
import numpy as np
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Optional
from agents.analyzer.analyzer import RCA

logger = structlog.get_logger(__name__)


class RemediationPlan(BaseModel):
    rca_alert_id: str
    runbook_name: str
    runbook_steps: list[str]
    requires_approval: bool
    approval_reason: Optional[str]
    parameters: dict
    rollback_plan: str
    estimated_duration: str


class PlannerAgent:
    """
    Retrieves the best runbook for a given RCA using Qwen embeddings + cosine similarity.
    Enforces human-in-the-loop for critical actions.
    """

    def __init__(self):
        api_key = os.getenv("QWEN_API_KEY")
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.embedding_model = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v3")

        # Load runbook library
        self.runbooks = self._load_runbooks()
        self._embeddings_cache: dict[str, list[float]] = {}

    def _load_runbooks(self) -> list[dict]:
        """Load runbooks from the runbooks directory."""
        runbooks_dir = os.path.join(os.path.dirname(__file__), "../../runbooks")
        runbooks = []

        try:
            import glob
            for path in glob.glob(f"{runbooks_dir}/*.json"):
                with open(path) as f:
                    runbooks.append(json.load(f))
        except Exception as e:
            logger.warning("runbook_load_error", error=str(e))

        if not runbooks:
            # Built-in fallback runbooks
            runbooks = self._default_runbooks()

        logger.info("runbooks_loaded", count=len(runbooks))
        return runbooks

    def _default_runbooks(self) -> list[dict]:
        return [
            {
                "name": "oomkill-increase-memory-limits",
                "description": "OOMKilled pod: increase container memory limits and requests",
                "triggers": ["OOMKill", "OOMKilled", "memory limit exceeded", "exit code 137"],
                "steps": [
                    "Identify the affected deployment via kubectl get pod",
                    "Get current memory limits: kubectl get deployment -o yaml",
                    "Calculate new limits: current_limit * 2 (capped at node capacity)",
                    "Patch deployment: kubectl patch deployment <name> -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"<container>\",\"resources\":{\"limits\":{\"memory\":\"<new_limit>\"}}}]}}}}'",
                    "Wait for rollout: kubectl rollout status deployment/<name>",
                    "Verify pod is running: kubectl get pods -n <namespace>",
                    "Monitor for 5 minutes to confirm stability"
                ],
                "parameters": ["namespace", "deployment_name", "container_name", "new_memory_limit"],
                "risk": "low",
                "rollback": "kubectl rollout undo deployment/<deployment_name> -n <namespace>",
                "estimated_duration": "45 seconds"
            },
            {
                "name": "crashloop-rollback-deployment",
                "description": "CrashLoopBackOff: rollback deployment to last stable version",
                "triggers": ["CrashLoopBackOff", "crash loop", "repeated crashes", "BackOff"],
                "steps": [
                    "Check deployment rollout history: kubectl rollout history deployment/<name>",
                    "Identify last stable revision",
                    "Trigger rollback via ArgoCD: argocd app rollback <app-name>",
                    "Monitor rollback status: kubectl rollout status deployment/<name>",
                    "Confirm pods are healthy: kubectl get pods -n <namespace>",
                    "Check logs to confirm no new errors: kubectl logs -l app=<name> --tail=50"
                ],
                "parameters": ["namespace", "deployment_name", "argocd_app_name"],
                "risk": "medium",
                "rollback": "Re-apply previous rollback or manual deployment",
                "estimated_duration": "90 seconds"
            },
            {
                "name": "kyverno-policy-exception",
                "description": "Kyverno policy violation: create policy exception for approved workload",
                "triggers": ["policy violation", "Kyverno", "disallow-root", "privileged", "policy blocked"],
                "steps": [
                    "Review the violated policy: kubectl get clusterpolicy <policy-name> -o yaml",
                    "Validate the workload is approved for exception",
                    "Create PolicyException resource in namespace",
                    "Apply via GitOps: commit exception YAML to infrastructure repo",
                    "ArgoCD will sync the exception automatically",
                    "Verify exception is active: kubectl get policyexception -n <namespace>"
                ],
                "parameters": ["namespace", "policy_name", "workload_name", "exception_reason"],
                "risk": "medium",
                "rollback": "Delete the PolicyException resource",
                "estimated_duration": "2 minutes"
            },
            {
                "name": "cost-spike-scale-down",
                "description": "Cost spike: scale down idle or over-provisioned workloads",
                "triggers": ["cost spike", "budget exceeded", "overspend", "idle KServe", "cost alert"],
                "steps": [
                    "Query OpenCost for top consumers in namespace",
                    "Identify idle or over-replicated workloads",
                    "Check if KServe model replicas can be reduced",
                    "Scale down: kubectl scale deployment <name> --replicas=<count>",
                    "Or scale KServe InferenceService: kubectl patch isvc <name> --patch '{\"spec\":{\"predictor\":{\"maxReplicas\":1}}}'",
                    "Verify cost reduction in OpenCost after 10 minutes"
                ],
                "parameters": ["namespace", "workload_name", "target_replicas"],
                "risk": "medium",
                "rollback": "kubectl scale deployment <name> --replicas=<original_count>",
                "estimated_duration": "30 seconds"
            },
            {
                "name": "deployment-failure-force-sync",
                "description": "Deployment failure: force ArgoCD sync to restore desired state",
                "triggers": ["deployment failed", "FailedCreate", "sync failed", "OutOfSync"],
                "steps": [
                    "Check ArgoCD app status: argocd app get <app-name>",
                    "Review sync error details",
                    "Force hard refresh: argocd app get --hard-refresh <app-name>",
                    "Trigger sync: argocd app sync <app-name> --force",
                    "Monitor sync status: argocd app wait <app-name> --sync",
                    "Verify all resources are healthy"
                ],
                "parameters": ["argocd_app_name", "namespace"],
                "risk": "low",
                "rollback": "argocd app rollback <app-name>",
                "estimated_duration": "60 seconds"
            }
        ]

    async def plan(self, rca: RCA) -> RemediationPlan:
        """Select and return the best remediation plan for the given RCA."""
        logger.info("planning_remediation", alert_id=rca.alert_id, action_type=rca.action_type)

        # Find best matching runbook via embedding similarity
        runbook = await self._find_best_runbook(rca)

        # Determine if human approval is needed
        requires_approval = self._requires_human_approval(rca, runbook)
        approval_reason = None
        if requires_approval:
            approval_reason = self._approval_reason(rca, runbook)

        plan = RemediationPlan(
            rca_alert_id=rca.alert_id,
            runbook_name=runbook["name"],
            runbook_steps=runbook["steps"],
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            parameters=self._extract_parameters(rca, runbook),
            rollback_plan=runbook.get("rollback", "Manual rollback required"),
            estimated_duration=runbook.get("estimated_duration", "Unknown"),
        )

        logger.info("plan_created",
                    runbook=plan.runbook_name,
                    requires_approval=plan.requires_approval,
                    duration=plan.estimated_duration)
        return plan

    async def _find_best_runbook(self, rca: RCA) -> dict:
        """Use Qwen embeddings to find the most semantically similar runbook."""
        query = f"{rca.root_cause} {rca.recommended_action} {rca.action_type}"

        try:
            query_emb = await self._embed(query)
            best_score = -1
            best_runbook = self.runbooks[0]

            for rb in self.runbooks:
                rb_text = f"{rb['name']} {rb['description']} {' '.join(rb['triggers'])}"
                rb_emb = await self._embed(rb_text)
                score = self._cosine_similarity(query_emb, rb_emb)

                if score > best_score:
                    best_score = score
                    best_runbook = rb

            logger.info("runbook_selected",
                        name=best_runbook["name"],
                        similarity_score=round(best_score, 4))
            return best_runbook

        except Exception as e:
            logger.error("embedding_error_fallback", error=str(e))
            # Fallback: keyword match
            return self._keyword_match(rca)

    async def _embed(self, text: str) -> list[float]:
        """Get Qwen embedding for text with caching."""
        if text in self._embeddings_cache:
            return self._embeddings_cache[text]

        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        emb = response.data[0].embedding
        self._embeddings_cache[text] = emb
        return emb

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        va, vb = np.array(a), np.array(b)
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-10))

    def _keyword_match(self, rca: RCA) -> dict:
        """Simple keyword fallback when embeddings fail."""
        keywords = (rca.action_type + " " + rca.root_cause).lower()
        for rb in self.runbooks:
            for trigger in rb["triggers"]:
                if any(t in keywords for t in trigger.lower().split()):
                    return rb
        return self.runbooks[0]

    def _requires_human_approval(self, rca: RCA, runbook: dict) -> bool:
        """Determine if action needs human approval before executing."""
        if rca.risk_level in ("critical", "high"):
            return True
        if rca.confidence == "low":
            return True
        if not rca.auto_remediate:
            return True
        if runbook.get("risk") == "high":
            return True
        return False

    def _approval_reason(self, rca: RCA, runbook: dict) -> str:
        reasons = []
        if rca.risk_level in ("critical", "high"):
            reasons.append(f"Risk level is {rca.risk_level}")
        if rca.confidence == "low":
            reasons.append("Qwen confidence is low")
        if not rca.auto_remediate:
            reasons.append("Qwen recommends human review")
        return ". ".join(reasons) + ". Please approve or reject this remediation."

    def _extract_parameters(self, rca: RCA, runbook: dict) -> dict:
        """Extract parameters needed for the runbook from the alert context."""
        # These would be populated from the alert raw_data in production
        return {
            "alert_id": rca.alert_id,
            "action_type": rca.action_type,
            "runbook_params": runbook.get("parameters", []),
        }
