"""
Blast Radius Analyzer — Estimate how many resources could be affected.

Blast radius is a critical trust factor. Actions that affect only a single pod
are lower risk than actions that affect an entire namespace or cluster.

Scoring:
- Single pod/resource: 90-100
- Single deployment (few replicas): 70-80
- Multiple deployments: 50-60
- Entire namespace: 30-40
- Cluster-wide: 10-20
"""

import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)


class BlastRadiusAnalyzer:
    """Analyzes the blast radius of remediation actions."""

    def analyze(
        self,
        action_type: str,
        target_resource: Dict[str, Any],
        cluster_state: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Analyze blast radius of an action.
        
        Args:
            action_type: Type of action being taken
            target_resource: Resource being affected
            cluster_state: Current cluster state (optional)
            
        Returns:
            Blast radius score (0-100, higher is safer/lower blast radius)
        """
        # Estimate affected resource count
        affected_count = self._estimate_affected_resources(
            action_type=action_type,
            target_resource=target_resource,
            cluster_state=cluster_state,
        )

        # Convert affected count to score
        score = self._count_to_score(affected_count)

        logger.debug(
            "blast_radius_analyzed",
            action_type=action_type,
            affected_count=affected_count,
            score=score,
        )

        return score

    def _estimate_affected_resources(
        self,
        action_type: str,
        target_resource: Dict[str, Any],
        cluster_state: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Estimate the number of resources that could be affected.
        
        Returns:
            Estimated count of affected resources
        """
        resource_kind = target_resource.get("kind", "Unknown")
        namespace = target_resource.get("namespace", "default")

        # For pod-level actions, only 1 resource affected
        if action_type in ["delete_pod", "restart_pod", "evict_pod"]:
            return 1

        # For deployment-level actions, check replica count
        if action_type in ["scale_down", "scale_up", "rollback_deployment"]:
            replicas = target_resource.get("spec", {}).get("replicas", 1)
            return max(1, replicas)

        # For node-level actions, could affect many pods
        if action_type in ["cordon_node", "drain_node"]:
            if cluster_state:
                pods_on_node = cluster_state.get("pods_on_node", {}).get(
                    target_resource.get("name"), 0
                )
                return pods_on_node
            return 10  # Conservative estimate

        # For namespace-level actions
        if action_type in ["apply_manifest", "delete_resource"]:
            if cluster_state:
                namespace_resources = cluster_state.get("namespace_resources", {}).get(
                    namespace, 0
                )
                return namespace_resources
            return 5  # Conservative estimate

        # For cluster-wide actions
        if action_type in ["create_exception"]:
            if cluster_state:
                cluster_resources = cluster_state.get("total_resources", 0)
                return cluster_resources
            return 50  # Conservative estimate

        # Default: assume moderate blast radius
        return 3

    def _count_to_score(self, affected_count: int) -> float:
        """
        Convert affected resource count to a blast radius score.
        
        Scoring:
        - 1 resource: 95 (very safe)
        - 2-5 resources: 80 (safe)
        - 6-10 resources: 60 (moderate)
        - 11-50 resources: 40 (risky)
        - 50+ resources: 20 (very risky)
        """
        if affected_count <= 1:
            return 95.0
        elif affected_count <= 5:
            return 80.0
        elif affected_count <= 10:
            return 60.0
        elif affected_count <= 50:
            return 40.0
        else:
            return 20.0
