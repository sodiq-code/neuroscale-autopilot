"""
Runbook Confidence Analyzer — Assess confidence in the remediation plan.

Runbook confidence reflects how well-matched the remediation plan is to the
incident. High confidence means the runbook has been used successfully for
similar incidents before. Low confidence means the runbook is generic or untested.

Scoring:
- Exact match with high historical success: 90-100
- Good match with moderate success: 70-80
- Generic runbook: 50-60
- Uncertain match: 30-40
- No runbook found: 20
"""

import structlog
from typing import Dict, Any

logger = structlog.get_logger(__name__)


class RunbookConfidenceAnalyzer:
    """Analyzes confidence in the remediation plan."""

    def analyze(
        self,
        remediation_plan: Dict[str, Any],
        action_type: str,
    ) -> float:
        """
        Analyze confidence in a remediation plan.
        
        Args:
            remediation_plan: Planned remediation steps
            action_type: Type of action being taken
            
        Returns:
            Runbook confidence score (0-100)
        """
        # Check if runbook was found
        runbook_found = remediation_plan.get("runbook_found", False)
        if not runbook_found:
            logger.debug("runbook_confidence_no_runbook", action_type=action_type)
            return 20.0

        # Get retrieval score (semantic similarity)
        retrieval_score = remediation_plan.get("retrieval_score", 0.5)

        # Get retrieval margin (confidence in uniqueness of match)
        retrieval_margin = remediation_plan.get("retrieval_margin", 0.0)

        # Check if runbook was escalated (uncertain)
        retrieval_escalated = remediation_plan.get("retrieval_escalated", False)

        # Base score from retrieval
        base_score = self._retrieval_to_score(retrieval_score)

        # Adjust for margin
        margin_adjustment = self._margin_to_adjustment(retrieval_margin)

        # Penalize if escalated
        escalation_penalty = 15 if retrieval_escalated else 0

        # Adjust for plan completeness
        completeness_adjustment = self._check_plan_completeness(remediation_plan)

        # Compute final score
        score = base_score + margin_adjustment + completeness_adjustment - escalation_penalty

        # Clamp to 0-100
        score = max(0, min(100, score))

        logger.debug(
            "runbook_confidence_analyzed",
            action_type=action_type,
            base_score=base_score,
            margin_adjustment=margin_adjustment,
            escalation_penalty=escalation_penalty,
            completeness_adjustment=completeness_adjustment,
            final_score=score,
        )

        return score

    def _retrieval_to_score(self, retrieval_score: float) -> float:
        """
        Convert semantic similarity score to confidence score.
        
        Args:
            retrieval_score: Semantic similarity (0-1)
            
        Returns:
            Confidence score (0-100)
        """
        # Map 0-1 to 20-100
        return 20 + (retrieval_score * 80)

    def _margin_to_adjustment(self, retrieval_margin: float) -> float:
        """
        Adjust score based on retrieval margin (confidence in uniqueness).
        
        Args:
            retrieval_margin: Margin between top and second-best match (0-1)
            
        Returns:
            Adjustment factor (-10 to +10)
        """
        # High margin means confident in the match
        if retrieval_margin > 0.3:
            return 10.0
        elif retrieval_margin > 0.15:
            return 5.0
        elif retrieval_margin > 0.05:
            return 0.0
        else:
            return -10.0

    def _check_plan_completeness(self, remediation_plan: Dict[str, Any]) -> float:
        """
        Check if the remediation plan is complete and well-structured.
        
        Args:
            remediation_plan: Planned remediation steps
            
        Returns:
            Adjustment factor (-10 to +10)
        """
        adjustments = 0

        # Check for steps
        steps = remediation_plan.get("steps", [])
        if len(steps) > 0:
            adjustments += 5

        # Check for parameters
        parameters = remediation_plan.get("parameters", {})
        if len(parameters) > 0:
            adjustments += 3

        # Check for validation steps
        validation = remediation_plan.get("validation", {})
        if validation:
            adjustments += 2

        # Check for rollback plan
        rollback = remediation_plan.get("rollback_plan")
        if rollback:
            adjustments += 5

        # Check for estimated duration
        estimated_duration = remediation_plan.get("estimated_duration_seconds")
        if estimated_duration is not None:
            adjustments += 2

        # Penalize if plan is too generic
        description = remediation_plan.get("description", "")
        if description and len(description) < 20:
            adjustments -= 5

        return min(10, max(-10, adjustments))
