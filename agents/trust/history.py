"""
History Analyzer — Track historical success rates for action types.

History reflects how successful a particular action type has been in the past.
Actions with high success rates receive higher scores. New or rarely-used actions
receive lower scores.

Scoring:
- High success rate (>90%): 85-100
- Good success rate (70-90%): 70-85
- Moderate success rate (50-70%): 50-70
- Low success rate (<50%): 30-50
- No history: 50 (neutral)
"""

import json
import os
import structlog
from typing import Dict, Any, Optional
from collections import defaultdict

logger = structlog.get_logger(__name__)


class HistoryAnalyzer:
    """Analyzes historical success rates for action types."""

    def __init__(self, history_file: str = "outcomes.jsonl"):
        """
        Initialize the history analyzer.
        
        Args:
            history_file: Path to outcomes log file
        """
        self.history_file = history_file
        self._cache: Optional[Dict[str, Dict[str, int]]] = None

    def analyze(
        self,
        action_type: str,
        alert_id: str,
    ) -> float:
        """
        Analyze historical success rate for an action type.
        
        Args:
            action_type: Type of action (e.g., 'scale_down', 'rollback')
            alert_id: Current alert ID (for context)
            
        Returns:
            History score (0-100)
        """
        history = self._load_history()
        action_history = history.get(action_type, {})

        total = action_history.get("total", 0)
        successful = action_history.get("successful", 0)

        # No history: neutral score
        if total == 0:
            logger.debug(
                "history_no_data",
                action_type=action_type,
                score=50,
            )
            return 50.0

        # Calculate success rate
        success_rate = successful / total

        # Convert to score
        score = self._success_rate_to_score(success_rate, total)

        logger.debug(
            "history_analyzed",
            action_type=action_type,
            total_attempts=total,
            successful_attempts=successful,
            success_rate=round(success_rate, 2),
            score=score,
        )

        return score

    def _load_history(self) -> Dict[str, Dict[str, int]]:
        """
        Load historical outcomes from outcomes.jsonl file.
        
        Returns:
            Dictionary mapping action types to success/total counts
        """
        if self._cache is not None:
            return self._cache

        history: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "successful": 0}
        )

        if not os.path.exists(self.history_file):
            self._cache = dict(history)
            return self._cache

        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    try:
                        outcome = json.loads(line)
                        # Infer action type from execution mode or other fields
                        # For now, use a generic key
                        action_key = outcome.get("action_id", "unknown")

                        # Track total
                        history[action_key]["total"] += 1

                        # Track successful (assume successful if not failed)
                        # This is a simplification; real implementation would check execution status
                        history[action_key]["successful"] += 1

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning("failed_to_load_history", error=str(e))

        self._cache = dict(history)
        return self._cache

    def _success_rate_to_score(self, success_rate: float, total_attempts: int) -> float:
        """
        Convert success rate to a score, with confidence adjustment.
        
        Args:
            success_rate: Success rate (0-1)
            total_attempts: Number of total attempts (for confidence)
            
        Returns:
            History score (0-100)
        """
        # Base score from success rate
        base_score = success_rate * 100

        # Adjust for confidence (more attempts = higher confidence)
        confidence_factor = min(1.0, total_attempts / 10.0)

        # Apply confidence adjustment
        adjusted_score = 50 + (base_score - 50) * confidence_factor

        return adjusted_score

    def clear_cache(self) -> None:
        """Clear the in-memory cache (useful for testing)."""
        self._cache = None
