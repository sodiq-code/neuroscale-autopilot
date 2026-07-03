"""
NeuroScale v2 Trust Score Engine

Implements the composite trust scoring algorithm that gates all remediation
actions. The trust score is a weighted combination of four sub-scores:

- Reversibility (0.30): Can the action be undone?
- Blast Radius (0.25): How many resources could be affected?
- Runbook Confidence (0.25): How confident is the remediation plan?
- History (0.20): What is the historical success rate for this action type?

Final decision:
- score >= 90: EXECUTE (immediate)
- 70 <= score < 90: DRYRUN_VERIFY (dry-run first)
- score < 70: ESCALATE_HUMAN (wait for approval)
"""

import json
import os
import structlog
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from .reversibility import ReversibilityAnalyzer
from .blast_radius import BlastRadiusAnalyzer
from .runbook_confidence import RunbookConfidenceAnalyzer
from .history import HistoryAnalyzer

logger = structlog.get_logger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode determined by trust score."""
    EXECUTE = "execute"
    DRYRUN_VERIFY = "dryrun_verify"
    ESCALATE_HUMAN = "escalate_human"


@dataclass
class TrustScoreResult:
    """Result of trust score computation."""
    final_score: float
    execution_mode: ExecutionMode
    reversibility_score: float
    blast_radius_score: float
    runbook_confidence_score: float
    history_score: float
    reasoning: str
    timestamp: str
    action_id: str
    alert_id: str


class TrustScoreEngine:
    """
    Main trust scoring engine.
    
    Computes a composite trust score for remediation actions and determines
    the appropriate execution mode.
    """

    def __init__(
        self,
        execute_threshold: float = 90.0,
        dryrun_threshold: float = 70.0,
        escalation_timeout_seconds: int = 300,
    ):
        """
        Initialize the trust score engine.
        
        Args:
            execute_threshold: Score threshold for immediate execution (default 90)
            dryrun_threshold: Score threshold for dry-run verification (default 70)
            escalation_timeout_seconds: Timeout for human escalation (default 300s)
        """
        self.execute_threshold = execute_threshold
        self.dryrun_threshold = dryrun_threshold
        self.escalation_timeout_seconds = escalation_timeout_seconds

        # Initialize sub-analyzers
        self.reversibility = ReversibilityAnalyzer()
        self.blast_radius = BlastRadiusAnalyzer()
        self.runbook_confidence = RunbookConfidenceAnalyzer()
        self.history = HistoryAnalyzer()

        # Weights for composite score
        self.weights = {
            "reversibility": 0.30,
            "blast_radius": 0.25,
            "runbook_confidence": 0.25,
            "history": 0.20,
        }

        # Outcomes log for audit trail
        self.outcomes_file = "outcomes.jsonl"

    def compute_score(
        self,
        alert_id: str,
        action_id: str,
        action_type: str,
        target_resource: Dict[str, Any],
        remediation_plan: Dict[str, Any],
        cluster_state: Optional[Dict[str, Any]] = None,
    ) -> TrustScoreResult:
        """
        Compute the trust score for a remediation action.
        
        Args:
            alert_id: Unique identifier for the alert
            action_id: Unique identifier for the action
            action_type: Type of action (e.g., 'scale_down', 'rollback', 'patch')
            target_resource: Resource being remediated (e.g., deployment, pod)
            remediation_plan: Planned remediation steps
            cluster_state: Current cluster state (optional)
            
        Returns:
            TrustScoreResult with final score and execution mode
        """
        logger.info(
            "trust_score_compute_start",
            alert_id=alert_id,
            action_id=action_id,
            action_type=action_type,
        )

        # Compute sub-scores
        reversibility_score = self.reversibility.analyze(
            action_type=action_type,
            target_resource=target_resource,
            remediation_plan=remediation_plan,
        )

        blast_radius_score = self.blast_radius.analyze(
            action_type=action_type,
            target_resource=target_resource,
            cluster_state=cluster_state,
        )

        runbook_confidence_score = self.runbook_confidence.analyze(
            remediation_plan=remediation_plan,
            action_type=action_type,
        )

        history_score = self.history.analyze(
            action_type=action_type,
            alert_id=alert_id,
        )

        # Compute weighted final score
        final_score = (
            self.weights["reversibility"] * reversibility_score
            + self.weights["blast_radius"] * blast_radius_score
            + self.weights["runbook_confidence"] * runbook_confidence_score
            + self.weights["history"] * history_score
        )

        # Determine execution mode
        if final_score >= self.execute_threshold:
            execution_mode = ExecutionMode.EXECUTE
            reasoning = f"Trust score {final_score:.1f} >= {self.execute_threshold} threshold. Executing immediately."
        elif final_score >= self.dryrun_threshold:
            execution_mode = ExecutionMode.DRYRUN_VERIFY
            reasoning = f"Trust score {final_score:.1f} in range [{self.dryrun_threshold}, {self.execute_threshold}). Dry-run first, then live if successful."
        else:
            execution_mode = ExecutionMode.ESCALATE_HUMAN
            reasoning = f"Trust score {final_score:.1f} < {self.dryrun_threshold} threshold. Escalating to human for approval."

        result = TrustScoreResult(
            final_score=round(final_score, 2),
            execution_mode=execution_mode,
            reversibility_score=round(reversibility_score, 2),
            blast_radius_score=round(blast_radius_score, 2),
            runbook_confidence_score=round(runbook_confidence_score, 2),
            history_score=round(history_score, 2),
            reasoning=reasoning,
            timestamp=datetime.utcnow().isoformat() + "Z",
            action_id=action_id,
            alert_id=alert_id,
        )

        logger.info(
            "trust_score_computed",
            alert_id=alert_id,
            action_id=action_id,
            final_score=result.final_score,
            execution_mode=result.execution_mode.value,
            reversibility=result.reversibility_score,
            blast_radius=result.blast_radius_score,
            runbook_confidence=result.runbook_confidence_score,
            history=result.history_score,
        )

        # Log outcome
        self._log_outcome(result)

        return result

    def _log_outcome(self, result: TrustScoreResult) -> None:
        """
        Log the trust score outcome to outcomes.jsonl for audit trail.
        
        Args:
            result: TrustScoreResult to log
        """
        try:
            with open(self.outcomes_file, "a") as f:
                f.write(json.dumps(asdict(result), default=str) + "\n")
        except Exception as e:
            logger.warning("failed_to_log_outcome", error=str(e))

    def get_execution_mode_description(self, mode: ExecutionMode) -> str:
        """Get human-readable description of execution mode."""
        descriptions = {
            ExecutionMode.EXECUTE: "Execute immediately without dry-run",
            ExecutionMode.DRYRUN_VERIFY: "Perform dry-run first, then execute if successful",
            ExecutionMode.ESCALATE_HUMAN: "Escalate to human for approval",
        }
        return descriptions.get(mode, "Unknown mode")
