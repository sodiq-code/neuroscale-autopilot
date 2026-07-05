"""Reversibility Scorer — how easily can this action be undone?"""

import structlog

logger = structlog.get_logger(__name__)

# Actions ranked by reversibility (0-100)
REVERSIBILITY_MAP = {
    "monitor":           100,  # read-only, fully safe
    "get_pod_status":    100,
    "get_pod_logs":      100,
    "get_deployment_status": 100,
    "create_exception":  80,   # can delete PolicyException
    "patch_resources":   60,   # can revert patch, but pod may restart
    "scale_down":        50,   # can scale up, but downtime in between
    "rollback":          40,   # can re-apply newer version, but state is lost
    "restart":           30,   # pod restart clears in-memory state
    "delete_pod":        20,   # pod gone, IP changes
    "delete_resource":   10,   # permanent unless backed by GitOps
    "escalate":          100,  # no change, just notification
}


class ReversibilityScorer:
    """Score how reversible an action is (0-100)."""

    def score(self, action_type: str, parameters: dict) -> tuple[float, str]:
        base = REVERSIBILITY_MAP.get(action_type, 50)
        reason = f"Base={base}"

        # If it's a dry-run, reversibility is irrelevant = high
        if parameters.get("dry_run") is True:
            return 100.0, "Dry-run mode — no state changed"

        # Scale-related adjustments
        if action_type == "scale_down":
            replicas = parameters.get("target_replicas", 1)
            try:
                replicas = int(replicas)
            except (TypeError, ValueError):
                replicas = 0
            if replicas == 0:
                return 10.0, "Scale-to-zero is hard to reverse (cold start latency)"
            if replicas >= 2:
                base = 70  # multi-replica → failover exists
                reason = f"Multi-replica ({replicas}), safe to re-scale"
            else:
                reason = f"Single-replica (fragile), base={base}"

        if action_type == "rollback":
            # If ArgoCD in use, rollback is more reversible (GitOps)
            if parameters.get("argocd_app_name"):
                base = 60
                reason = "ArgoCD-backed — GitOps enables re-sync"

        return float(base), reason
