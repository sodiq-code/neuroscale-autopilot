"""
TrustScore — Four-factor autonomous trust engine.
Gates every remediation action before the Executor runs.
"""

import json
import os
import structlog
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from agents.trust.reversibility import ReversibilityScorer
from agents.trust.blast_radius import BlastRadiusScorer
from agents.trust.runbook_confidence import RunbookConfidenceScorer
from agents.trust.history import HistoryScorer

logger = structlog.get_logger(__name__)

OUTCOMES_PATH = os.path.join(os.path.dirname(__file__), "../../outcomes.jsonl")


class TrustDecision(str, Enum):
    EXECUTE = "EXECUTE"
    DRYRUN_VERIFY = "DRYRUN_VERIFY"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class TrustReport:
    """Structured trust assessment result."""

    def __init__(
        self,
        alert_id: str,
        total_score: float,
        decision: TrustDecision,
        factors: dict,
        reasoning: list[str],
        timestamp: Optional[str] = None,
    ):
        self.alert_id = alert_id
        self.total_score = round(total_score, 2)
        self.decision = decision
        self.factors = factors
        self.reasoning = reasoning
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "total_score": self.total_score,
            "decision": self.decision.value,
            "factors": self.factors,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


class TrustScore:
    """
    Computes a weighted trust score from four independent factors.
    Weights:
      - reversibility:     30%
      - blast_radius:      25%
      - runbook_confidence: 25%
      - history:           20%

    Decision thresholds:
      - score >= 90: EXECUTE
      - score >= 70 and < 90: DRYRUN_VERIFY
      - score < 70: ESCALATE_HUMAN
      - Any failure/exception during computation: ESCALATE_HUMAN (fail-safe)
    """

    WEIGHTS = {
        "reversibility": 0.30,
        "blast_radius": 0.25,
        "runbook_confidence": 0.25,
        "history": 0.20,
    }

    EXECUTE_THRESHOLD = 90
    DRYRUN_THRESHOLD = 70

    def __init__(self):
        self.reversibility = ReversibilityScorer()
        self.blast_radius = BlastRadiusScorer()
        self.runbook_confidence = RunbookConfidenceScorer()
        self.history = HistoryScorer()

    def evaluate(
        self,
        alert_id: str,
        action_type: str,
        risk_level: str,
        parameters: dict,
        runbook_name: str = "",
        namespace: str = "",
    ) -> TrustReport:
        """
        Compute the trust score and return a TrustReport with the decision.

        Falls back to ESCALATE_HUMAN on any scoring failure (fail-safe).
        """
        reasoning: list[str] = []

        try:
            # Factor 1: Reversibility (30%)
            rev_score, rev_reason = self.reversibility.score(action_type, parameters)
            reasoning.append(f"Reversibility ({rev_score}/100): {rev_reason}")

            # Factor 2: Blast Radius (25%)
            blast_score, blast_reason = self.blast_radius.score(
                action_type, risk_level, parameters, namespace
            )
            reasoning.append(f"Blast Radius ({blast_score}/100): {blast_reason}")

            # Factor 3: Runbook Confidence (25%)
            runbook_score, runbook_reason = self.runbook_confidence.score(runbook_name, action_type)
            reasoning.append(f"Runbook Confidence ({runbook_score}/100): {runbook_reason}")

            # Factor 4: History (20%)
            history_score, history_reason = self.history.score(alert_id, action_type, runbook_name)
            reasoning.append(f"History ({history_score}/100): {history_reason}")

            factors = {
                "reversibility": rev_score,
                "blast_radius": blast_score,
                "runbook_confidence": runbook_score,
                "history": history_score,
            }

            # Weighted total
            total = sum(
                factors[key] * self.WEIGHTS[key] for key in self.WEIGHTS
            )

            decision = self._classify(total)

            logger.info(
                "trust_score_computed",
                alert_id=alert_id,
                total_score=round(total, 2),
                decision=decision.value,
            )

            return TrustReport(
                alert_id=alert_id,
                total_score=total,
                decision=decision,
                factors=factors,
                reasoning=reasoning,
            )

        except Exception as e:
            logger.error("trust_score_error", alert_id=alert_id, error=str(e))
            reasoning.append(f"ERROR: {str(e)} — falling back to ESCALATE_HUMAN")
            return TrustReport(
                alert_id=alert_id,
                total_score=0,
                decision=TrustDecision.ESCALATE_HUMAN,
                factors={
                    "reversibility": 0,
                    "blast_radius": 0,
                    "runbook_confidence": 0,
                    "history": 0,
                },
                reasoning=reasoning,
            )

    def _classify(self, score: float) -> TrustDecision:
        if score >= self.EXECUTE_THRESHOLD:
            return TrustDecision.EXECUTE
        if score >= self.DRYRUN_THRESHOLD:
            return TrustDecision.DRYRUN_VERIFY
        return TrustDecision.ESCALATE_HUMAN

    def record_outcome(
        self,
        alert_id: str,
        trust_report: TrustReport,
        success: bool,
        action_taken: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ):
        """Append an outcome record to outcomes.jsonl for history tracking."""
        record = {
            "alert_id": alert_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trust_score": trust_report.total_score,
            "decision": trust_report.decision.value,
            "factors": trust_report.factors,
            "success": success,
            "action_taken": action_taken,
            "duration_seconds": duration_seconds,
            "error": error,
        }
        try:
            os.makedirs(os.path.dirname(OUTCOMES_PATH), exist_ok=True)
            with open(OUTCOMES_PATH, "a") as f:
                f.write(json.dumps(record) + "\n")
            logger.info("outcome_recorded", alert_id=alert_id, success=success)
        except Exception as e:
            logger.error("outcome_write_error", alert_id=alert_id, error=str(e))
