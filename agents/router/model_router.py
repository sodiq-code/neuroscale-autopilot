"""
Model Router — Intelligent routing to appropriate Qwen models.

Routes requests to different Qwen models based on:
- Incident severity and complexity
- Cost considerations
- Model capabilities and thinking mode availability
- Historical performance on similar incidents

Routing policy:
- simple_alert → qwen-turbo (fast, cheap)
- standard_diagnosis → qwen-plus (balanced)
- critical_incident → qwen3-max with thinking mode (powerful, expensive)
- embedding → text-embedding-v3 (semantic search)
- escalation_summary → qwen-turbo (fast summary)
"""

import structlog
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a model."""
    name: str
    thinking_enabled: bool = False
    max_tokens: int = 2048
    cost_per_1k_tokens: float = 0.0
    estimated_tokens: int = 1000


class ModelRouter:
    """Routes requests to appropriate Qwen models."""

    # Model configurations
    MODELS = {
        "qwen3-max": ModelConfig(
            name="qwen3-max",
            thinking_enabled=True,
            max_tokens=16000,
            cost_per_1k_tokens=0.10,  # Approximate cost
            estimated_tokens=5000,
        ),
        "qwen-plus": ModelConfig(
            name="qwen-plus",
            thinking_enabled=False,
            max_tokens=8000,
            cost_per_1k_tokens=0.02,
            estimated_tokens=2000,
        ),
        "qwen-turbo": ModelConfig(
            name="qwen-turbo",
            thinking_enabled=False,
            max_tokens=4000,
            cost_per_1k_tokens=0.005,
            estimated_tokens=1000,
        ),
        "text-embedding-v3": ModelConfig(
            name="text-embedding-v3",
            thinking_enabled=False,
            max_tokens=2048,
            cost_per_1k_tokens=0.001,
            estimated_tokens=500,
        ),
    }

    def __init__(self):
        """Initialize the model router."""
        self.routing_stats = {
            "simple_alert": 0,
            "standard_diagnosis": 0,
            "critical_incident": 0,
            "embedding": 0,
            "escalation_summary": 0,
        }

    def route_analysis(
        self,
        alert_severity: Literal["info", "warning", "critical"],
        alert_complexity: float,
        enable_thinking: bool = True,
    ) -> ModelConfig:
        """
        Route an analysis request to an appropriate model.
        
        Args:
            alert_severity: Alert severity (info, warning, critical)
            alert_complexity: Complexity score (0-1)
            enable_thinking: Whether thinking mode is desired
            
        Returns:
            ModelConfig for the selected model
        """
        # Route based on severity and complexity
        if alert_severity == "critical" and alert_complexity > 0.7 and enable_thinking:
            route_type = "critical_incident"
            model = self.MODELS["qwen3-max"]
        elif alert_severity == "critical" or alert_complexity > 0.5:
            route_type = "standard_diagnosis"
            model = self.MODELS["qwen-plus"]
        else:
            route_type = "simple_alert"
            model = self.MODELS["qwen-turbo"]

        self.routing_stats[route_type] += 1

        logger.info(
            "model_routed",
            route_type=route_type,
            alert_severity=alert_severity,
            alert_complexity=alert_complexity,
            selected_model=model.name,
            thinking_enabled=model.thinking_enabled,
        )

        return model

    def route_embedding(self) -> ModelConfig:
        """
        Route an embedding request.
        
        Returns:
            ModelConfig for embedding model
        """
        self.routing_stats["embedding"] += 1
        return self.MODELS["text-embedding-v3"]

    def route_escalation_summary(self) -> ModelConfig:
        """
        Route an escalation summary request.
        
        Returns:
            ModelConfig for summary model
        """
        self.routing_stats["escalation_summary"] += 1
        return self.MODELS["qwen-turbo"]

    def estimate_cost(self, model_name: str, token_count: int) -> float:
        """
        Estimate the cost of a model call.
        
        Args:
            model_name: Name of the model
            token_count: Estimated token count
            
        Returns:
            Estimated cost in dollars
        """
        if model_name not in self.MODELS:
            return 0.0

        model = self.MODELS[model_name]
        cost = (token_count / 1000) * model.cost_per_1k_tokens
        return round(cost, 6)

    def get_routing_stats(self) -> Dict[str, int]:
        """Get routing statistics."""
        return self.routing_stats.copy()

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        for key in self.routing_stats:
            self.routing_stats[key] = 0
