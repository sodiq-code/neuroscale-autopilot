"""History Scorer — has this action/runbook succeeded before for similar alerts?"""

import json
import os
import structlog

logger = structlog.get_logger(__name__)

OUTCOMES_PATH = os.path.join(os.path.dirname(__file__), "../../outcomes.jsonl")


class HistoryScorer:
    """Score based on past outcomes for similar actions."""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history

    def score(self, alert_id: str, action_type: str, runbook_name: str) -> tuple[float, str]:
        outcomes = self._load_outcomes()

        # Filter to matching action type
        matching = [
            o for o in outcomes
            if o.get("action_taken", "") == runbook_name
            or o.get("action_taken", "") == action_type
        ]

        if not matching:
            return 50.0, "No history for this action — neutral (50)"

        # Weight recent outcomes more heavily
        total_weight = 0
        weighted_success = 0
        for i, outcome in enumerate(matching):
            weight = 1.0 / (len(matching) - i + 1)  # more recent = higher weight
            total_weight += weight
            if outcome.get("success"):
                weighted_success += weight

        score = (weighted_success / total_weight * 100) if total_weight > 0 else 50

        success_count = sum(1 for o in matching if o.get("success"))
        reason = f"{success_count}/{len(matching)} past successes for {action_type}"
        return round(score, 2), reason

    def _load_outcomes(self) -> list[dict]:
        """Load outcome records from outcomes.jsonl."""
        outcomes = []
        try:
            if os.path.exists(OUTCOMES_PATH):
                with open(OUTCOMES_PATH) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            outcomes.append(json.loads(line))
        except Exception as e:
            logger.warning("history_load_error", error=str(e))
        return outcomes[-self.max_history:]
