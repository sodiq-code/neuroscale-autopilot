"""
Cost Governor — Track and optimize per-incident costs.

The cost governor tracks API calls, model usage, and estimated costs for each
incident. It provides cost transparency and can enforce cost budgets if needed.
"""

import structlog
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = structlog.get_logger(__name__)


@dataclass
class IncidentCost:
    """Cost tracking for a single incident."""
    incident_id: str
    alert_id: str
    start_time: str
    end_time: Optional[str] = None
    model_calls: Dict[str, int] = field(default_factory=dict)  # model -> count
    total_tokens: int = 0
    estimated_cost: float = 0.0
    cost_breakdown: Dict[str, float] = field(default_factory=dict)  # model -> cost


class CostGovernor:
    """Tracks and governs costs for remediation incidents."""

    def __init__(self, cost_budget: Optional[float] = None):
        """
        Initialize the cost governor.
        
        Args:
            cost_budget: Optional budget limit per incident in dollars
        """
        self.cost_budget = cost_budget
        self.incidents: Dict[str, IncidentCost] = {}
        self.total_cost = 0.0

    def start_incident(self, incident_id: str, alert_id: str) -> None:
        """
        Start tracking costs for an incident.
        
        Args:
            incident_id: Unique incident identifier
            alert_id: Associated alert identifier
        """
        self.incidents[incident_id] = IncidentCost(
            incident_id=incident_id,
            alert_id=alert_id,
            start_time=datetime.utcnow().isoformat() + "Z",
        )
        logger.info("cost_tracking_started", incident_id=incident_id, alert_id=alert_id)

    def record_model_call(
        self,
        incident_id: str,
        model_name: str,
        token_count: int,
        cost: float,
    ) -> None:
        """
        Record a model API call.
        
        Args:
            incident_id: Incident identifier
            model_name: Name of the model
            token_count: Number of tokens used
            cost: Cost of the call in dollars
        """
        if incident_id not in self.incidents:
            logger.warning("incident_not_found", incident_id=incident_id)
            return

        incident = self.incidents[incident_id]

        # Update model call count
        incident.model_calls[model_name] = incident.model_calls.get(model_name, 0) + 1

        # Update token count
        incident.total_tokens += token_count

        # Update cost
        incident.estimated_cost += cost
        incident.cost_breakdown[model_name] = (
            incident.cost_breakdown.get(model_name, 0.0) + cost
        )
        self.total_cost += cost

        # Check budget
        if self.cost_budget and incident.estimated_cost > self.cost_budget:
            logger.warning(
                "cost_budget_exceeded",
                incident_id=incident_id,
                budget=self.cost_budget,
                actual=incident.estimated_cost,
            )

        logger.debug(
            "model_call_recorded",
            incident_id=incident_id,
            model_name=model_name,
            token_count=token_count,
            cost=cost,
            incident_total_cost=incident.estimated_cost,
        )

    def end_incident(self, incident_id: str) -> Optional[IncidentCost]:
        """
        End tracking for an incident.
        
        Args:
            incident_id: Incident identifier
            
        Returns:
            IncidentCost with final cost data
        """
        if incident_id not in self.incidents:
            logger.warning("incident_not_found", incident_id=incident_id)
            return None

        incident = self.incidents[incident_id]
        incident.end_time = datetime.utcnow().isoformat() + "Z"

        logger.info(
            "cost_tracking_ended",
            incident_id=incident_id,
            total_cost=incident.estimated_cost,
            total_tokens=incident.total_tokens,
            model_calls=incident.model_calls,
        )

        return incident

    def get_incident_cost(self, incident_id: str) -> Optional[IncidentCost]:
        """
        Get cost data for an incident.
        
        Args:
            incident_id: Incident identifier
            
        Returns:
            IncidentCost or None if not found
        """
        return self.incidents.get(incident_id)

    def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all costs.
        
        Returns:
            Dictionary with cost summary
        """
        total_incidents = len(self.incidents)
        avg_cost = self.total_cost / total_incidents if total_incidents > 0 else 0.0

        return {
            "total_cost": round(self.total_cost, 6),
            "total_incidents": total_incidents,
            "average_cost_per_incident": round(avg_cost, 6),
            "cost_budget": self.cost_budget,
            "budget_remaining": (
                round(self.cost_budget - self.total_cost, 6)
                if self.cost_budget
                else None
            ),
        }

    def get_all_incidents(self) -> Dict[str, IncidentCost]:
        """Get all tracked incidents."""
        return self.incidents.copy()
