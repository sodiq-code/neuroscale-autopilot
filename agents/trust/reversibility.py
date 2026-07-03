"""
Reversibility Analyzer — Assess whether an action can be undone.

Reversibility is a key trust factor. Actions that can be easily rolled back
receive higher scores. Actions that are destructive or hard to undo receive
lower scores.

Scoring:
- Fully reversible (e.g., rollback, scale-up): 100
- Partially reversible (e.g., config patch with backup): 70-80
- Difficult to reverse (e.g., delete): 30-40
- Non-reversible (e.g., data deletion): 10-20
"""

import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)


class ReversibilityAnalyzer:
    """Analyzes the reversibility of remediation actions."""

    # Action type reversibility baseline scores
    REVERSIBILITY_BASELINE = {
        "rollback_deployment": 95,
        "scale_up": 100,
        "scale_down": 90,
        "patch_resource": 75,
        "update_config": 70,
        "create_exception": 85,
        "delete_pod": 60,
        "drain_node": 70,
        "cordon_node": 95,
        "uncordon_node": 100,
        "restart_pod": 80,
        "evict_pod": 70,
        "apply_manifest": 60,
        "delete_resource": 20,
    }

    def analyze(
        self,
        action_type: str,
        target_resource: Dict[str, Any],
        remediation_plan: Dict[str, Any],
    ) -> float:
        """
        Analyze reversibility of an action.
        
        Args:
            action_type: Type of action being taken
            target_resource: Resource being affected
            remediation_plan: Planned remediation steps
            
        Returns:
            Reversibility score (0-100)
        """
        # Start with baseline for action type
        baseline = self.REVERSIBILITY_BASELINE.get(action_type, 50)

        # Adjust based on resource type
        resource_kind = target_resource.get("kind", "Unknown")
        resource_adjustment = self._get_resource_adjustment(resource_kind)

        # Adjust based on backup/snapshot availability
        has_backup = remediation_plan.get("has_backup", False)
        backup_adjustment = 10 if has_backup else 0

        # Adjust based on rollback plan
        has_rollback = remediation_plan.get("rollback_plan", False)
        rollback_adjustment = 15 if has_rollback else 0

        # Compute final score
        score = baseline + resource_adjustment + backup_adjustment + rollback_adjustment

        # Clamp to 0-100
        score = max(0, min(100, score))

        logger.debug(
            "reversibility_analyzed",
            action_type=action_type,
            resource_kind=resource_kind,
            baseline=baseline,
            resource_adjustment=resource_adjustment,
            backup_adjustment=backup_adjustment,
            rollback_adjustment=rollback_adjustment,
            final_score=score,
        )

        return score

    def _get_resource_adjustment(self, resource_kind: str) -> float:
        """Get adjustment factor based on resource type."""
        adjustments = {
            "Pod": -5,  # Pods are ephemeral, easier to replace
            "Deployment": 5,  # Deployments have replicas, easier to recover
            "StatefulSet": -10,  # StatefulSets have state, harder to recover
            "PersistentVolume": -20,  # PVs have data, very hard to recover
            "Node": -15,  # Nodes are infrastructure, risky
            "ConfigMap": 10,  # ConfigMaps are easily replaceable
            "Secret": -5,  # Secrets are sensitive
            "Service": 5,  # Services are easily recreated
            "Ingress": 5,  # Ingresses are easily recreated
        }
        return adjustments.get(resource_kind, 0)
