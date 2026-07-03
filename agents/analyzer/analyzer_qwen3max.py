"""
NeuroScale v2 Analyzer — Qwen3-Max Thinking Mode Integration

Upgrades the analyzer to use Qwen3-Max with thinking mode enabled for deep RCA.
Streams reasoning chain to dashboard for live "Watch Qwen think" experience.
Generates concrete kubectl YAML patches directly.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator
import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)


class Qwen3MaxAnalyzer:
    """Analyzer using Qwen3-Max thinking mode for incident analysis."""

    def __init__(self):
        """Initialize the Qwen3-Max analyzer."""
        self.client = AsyncOpenAI(
            api_key="sk-placeholder",  # Set via environment
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        self.model = "qwen3-max"

    async def analyze_incident(
        self,
        alert_id: str,
        alert_type: str,
        cluster_state: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze an incident using Qwen3-Max thinking mode.

        Args:
            alert_id: Alert identifier
            alert_type: Type of alert (oomkill, crashloop, etc.)
            cluster_state: Current cluster state (pods, nodes, etc.)
            metrics: Prometheus metrics

        Returns:
            Analysis with thinking chain, RCA, and YAML patch
        """
        logger.info("qwen3max_analysis_start", alert_id=alert_id, alert_type=alert_type)

        # Build the system prompt
        system_prompt = """You are an expert Kubernetes SRE agent. Your task is to:
1. Analyze the incident deeply using your thinking capability
2. Provide root cause analysis (RCA)
3. Generate a concrete kubectl YAML patch to fix the issue
4. Explain your reasoning clearly

Output format:
{
  "thinking": "Your step-by-step reasoning...",
  "rca": "Root cause analysis...",
  "action_type": "scale|patch|restart|rollback",
  "yaml_patch": "kubectl patch YAML...",
  "confidence": 0.0-1.0,
  "reasoning": "Why this fix works..."
}"""

        # Build the user prompt
        user_prompt = f"""Analyze this Kubernetes incident:

Alert ID: {alert_id}
Alert Type: {alert_type}
Cluster State: {json.dumps(cluster_state, indent=2)}
Metrics: {json.dumps(metrics, indent=2)}

Provide deep analysis with thinking mode enabled."""

        try:
            # Call Qwen3-Max with thinking mode enabled
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_body={"enable_thinking": True},
                stream=True,
                temperature=0.7,
                max_tokens=4000,
            )

            # Stream and collect response
            thinking_chain = ""
            analysis_text = ""

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content

                    # Separate thinking from analysis
                    if "<thinking>" in content or thinking_chain:
                        thinking_chain += content
                    else:
                        analysis_text += content

                    # Stream to dashboard
                    logger.info("qwen3max_stream", alert_id=alert_id, content_length=len(content))

            # Parse the analysis
            try:
                analysis = json.loads(analysis_text)
            except json.JSONDecodeError:
                analysis = {
                    "thinking": thinking_chain,
                    "rca": analysis_text,
                    "action_type": "monitor",
                    "yaml_patch": "",
                    "confidence": 0.5,
                    "reasoning": "Failed to parse structured response",
                }

            result = {
                "alert_id": alert_id,
                "alert_type": alert_type,
                "thinking_chain": thinking_chain,
                "analysis": analysis,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            logger.info("qwen3max_analysis_complete", alert_id=alert_id)
            return result

        except Exception as e:
            logger.error("qwen3max_analysis_failed", alert_id=alert_id, error=str(e))
            raise

    async def stream_thinking(
        self, alert_id: str, alert_type: str, cluster_state: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Stream the thinking chain in real-time to dashboard.

        Args:
            alert_id: Alert identifier
            alert_type: Type of alert
            cluster_state: Current cluster state

        Yields:
            Thinking chain chunks
        """
        logger.info("streaming_thinking_start", alert_id=alert_id)

        system_prompt = "You are an expert Kubernetes SRE. Analyze this incident deeply."
        user_prompt = f"Alert: {alert_type}\nCluster State: {json.dumps(cluster_state)}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_body={"enable_thinking": True},
                stream=True,
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("streaming_thinking_failed", alert_id=alert_id, error=str(e))
            raise

    def generate_yaml_patch(self, action_type: str, target: Dict[str, Any]) -> str:
        """
        Generate a concrete kubectl YAML patch.

        Args:
            action_type: Type of action (scale, patch, etc.)
            target: Target resource details

        Returns:
            kubectl patch command or YAML
        """
        if action_type == "scale":
            namespace = target.get("namespace", "default")
            deployment = target.get("name", "unknown")
            replicas = target.get("replicas", 3)
            return f'kubectl scale deployment {deployment} --replicas={replicas} -n {namespace}'

        elif action_type == "patch":
            namespace = target.get("namespace", "default")
            deployment = target.get("name", "unknown")
            memory = target.get("memory", "512Mi")
            cpu = target.get("cpu", "250m")
            return f"""kubectl patch deployment {deployment} -n {namespace} --patch '{{"spec":{{"template":{{"spec":{{"containers":[{{"name":"app","resources":{{"limits":{{"memory":"{memory}","cpu":"{cpu}"}}}}}}]}}}}}}}}}'"""

        elif action_type == "restart":
            namespace = target.get("namespace", "default")
            deployment = target.get("name", "unknown")
            return f"kubectl rollout restart deployment/{deployment} -n {namespace}"

        elif action_type == "rollback":
            namespace = target.get("namespace", "default")
            deployment = target.get("name", "unknown")
            return f"kubectl rollout undo deployment/{deployment} -n {namespace}"

        else:
            return "# No action"


class FallbackAnalyzer:
    """Fallback analyzer for simple alerts using Qwen-Turbo."""

    def __init__(self):
        """Initialize the fallback analyzer."""
        self.client = AsyncOpenAI(
            api_key="sk-placeholder",  # Set via environment
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        self.model = "qwen-turbo"

    async def analyze_simple_alert(
        self, alert_id: str, alert_type: str, metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Quick analysis for simple alerts using Qwen-Turbo.

        Args:
            alert_id: Alert identifier
            alert_type: Type of alert
            metrics: Prometheus metrics

        Returns:
            Quick analysis
        """
        logger.info("qwen_turbo_analysis_start", alert_id=alert_id, alert_type=alert_type)

        prompt = f"""Quick analysis for Kubernetes alert:
Alert Type: {alert_type}
Metrics: {json.dumps(metrics)}

Provide a brief recommendation."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500,
            )

            analysis_text = response.choices[0].message.content

            result = {
                "alert_id": alert_id,
                "alert_type": alert_type,
                "analysis": analysis_text,
                "model": "qwen-turbo",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            logger.info("qwen_turbo_analysis_complete", alert_id=alert_id)
            return result

        except Exception as e:
            logger.error("qwen_turbo_analysis_failed", alert_id=alert_id, error=str(e))
            raise


class ModelRouter:
    """Routes incidents to appropriate analyzer based on severity."""

    def __init__(self):
        """Initialize the model router."""
        self.qwen3max = Qwen3MaxAnalyzer()
        self.fallback = FallbackAnalyzer()

    async def analyze(
        self,
        alert_id: str,
        alert_type: str,
        severity: str,
        cluster_state: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Route to appropriate analyzer based on severity.

        Args:
            alert_id: Alert identifier
            alert_type: Type of alert
            severity: Alert severity (critical, warning, info)
            cluster_state: Current cluster state
            metrics: Prometheus metrics

        Returns:
            Analysis result
        """
        logger.info(
            "model_routing",
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
        )

        if severity == "critical":
            # Use Qwen3-Max for critical incidents
            logger.info("routing_to_qwen3max", alert_id=alert_id)
            return await self.qwen3max.analyze_incident(
                alert_id, alert_type, cluster_state, metrics
            )
        else:
            # Use Qwen-Turbo for simple alerts
            logger.info("routing_to_qwen_turbo", alert_id=alert_id)
            return await self.fallback.analyze_simple_alert(alert_id, alert_type, metrics)
