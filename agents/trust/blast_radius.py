"""Blast Radius Scorer — how many resources/users are affected?"""

import structlog

logger = structlog.get_logger(__name__)

# Higher blast = lower score (safer = higher score)
NAMESPACE_RISK = {
    "production":  0.6,
    "prod":        0.6,
    "staging":     0.8,
    "preprod":     0.75,
    "ml-workloads": 0.7,
    "default":     0.5,
    "kube-system": 0.4,
}

RISK_LEVEL_FACTOR = {
    "critical": 0.3,
    "high":     0.5,
    "medium":   0.7,
    "low":      0.9,
    "info":     1.0,
}

ACTION_BLAST_WEIGHT = {
    "patch_resources":    0.85,  # limited blast — one deployment
    "rollback":           0.60,  # affects all pods in deployment
    "scale_down":         0.55,  # reduces capacity
    "create_exception":   0.70,  # policy exception = wide blast
    "delete_pod":         0.40,  # pod-level blast
    "delete_resource":    0.20,  # resource deletion = wide blast
    "monitor":            1.00,  # no blast
    "escalate":           1.00,  # no blast
    "restart":            0.50,  # pod restart = temporary
}


class BlastRadiusScorer:
    """Score blast radius — higher score = safer (smaller blast)."""

    def score(
        self,
        action_type: str,
        risk_level: str,
        parameters: dict,
        namespace: str = "",
    ) -> tuple[float, str]:
        namespace_lower = namespace.lower()
        ns_factor = 1.0
        for key, val in NAMESPACE_RISK.items():
            if key in namespace_lower:
                ns_factor = val
                break

        risk_factor = RISK_LEVEL_FACTOR.get(risk_level, 0.5)
        action_factor = ACTION_BLAST_WEIGHT.get(action_type, 0.5)

        score = (ns_factor * 0.3 + risk_factor * 0.3 + action_factor * 0.4) * 100

        reason = (
            f"ns={namespace}({ns_factor}), "
            f"risk={risk_level}({risk_factor}), "
            f"action={action_type}({action_factor})"
        )
        return round(score, 2), reason
