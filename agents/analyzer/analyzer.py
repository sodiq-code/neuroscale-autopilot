"""
Analyzer Agent — Uses Qwen-Max to reason about root cause of K8s incidents.
Takes a raw alert, enriches it with cluster context, then calls Qwen for analysis.
Returns structured RCA (Root Cause Analysis) + recommended action.
"""

import os
import json
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Optional
from agents.detector.detector import Alert

logger = structlog.get_logger(__name__)


class RCA(BaseModel):
    alert_id: str
    root_cause: str
    confidence: str        # high | medium | low
    recommended_action: str
    action_type: str       # patch_resources | rollback | scale_down | create_exception | escalate | monitor
    risk_level: str        # low | medium | high | critical
    auto_remediate: bool   # whether executor should proceed automatically
    reasoning_trace: str   # Qwen's full reasoning
    estimated_fix_time: str


SYSTEM_PROMPT = """You are NeuroScale Autopilot's Analyzer Agent — an expert Kubernetes SRE with deep knowledge of:
- Kubernetes pod lifecycle, resource management, OOMKills, CrashLoops
- ArgoCD GitOps deployments and rollbacks
- Kyverno admission policies and policy violations
- OpenCost budget tracking and cost optimization
- KServe ML model serving

Your job: Given a K8s incident alert, perform root cause analysis and recommend the exact remediation action.

Always respond in valid JSON with this exact structure:
{
  "root_cause": "precise technical explanation",
  "confidence": "high|medium|low",
  "recommended_action": "specific action to take",
  "action_type": "patch_resources|rollback|scale_down|create_exception|escalate|monitor",
  "risk_level": "low|medium|high|critical",
  "auto_remediate": true|false,
  "reasoning_trace": "your step-by-step reasoning",
  "estimated_fix_time": "e.g. 30 seconds"
}

Rules:
- auto_remediate=true only for low/medium risk actions you are highly confident about
- auto_remediate=false for critical risk, low confidence, or anything touching production data
- Be concise but precise in root_cause
- reasoning_trace should show your thinking chain
"""


class AnalyzerAgent:
    """
    Uses Qwen-Max to perform intelligent root cause analysis on K8s alerts.
    """

    def __init__(self):
        api_key = os.getenv("QWEN_API_KEY")
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        if not api_key:
            raise ValueError("QWEN_API_KEY environment variable is required")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = os.getenv("QWEN_MODEL_MAX", "qwen-max")

    async def analyze(self, alert: Alert, cluster_context: Optional[dict] = None) -> RCA:
        """
        Perform root cause analysis on an alert using Qwen-Max.
        """
        logger.info("analyzing_alert", alert_id=alert.id, type=alert.type)

        user_prompt = self._build_prompt(alert, cluster_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content
            logger.info("qwen_response_received", alert_id=alert.id, tokens=response.usage.total_tokens)

            data = json.loads(raw)
            rca = RCA(
                alert_id=alert.id,
                root_cause=data.get("root_cause", "Unknown"),
                confidence=data.get("confidence", "low"),
                recommended_action=data.get("recommended_action", "Monitor"),
                action_type=data.get("action_type", "monitor"),
                risk_level=data.get("risk_level", "medium"),
                auto_remediate=data.get("auto_remediate", False),
                reasoning_trace=data.get("reasoning_trace", ""),
                estimated_fix_time=data.get("estimated_fix_time", "unknown"),
            )

            logger.info("rca_complete",
                        alert_id=alert.id,
                        action_type=rca.action_type,
                        risk=rca.risk_level,
                        auto=rca.auto_remediate)
            return rca

        except json.JSONDecodeError as e:
            logger.error("qwen_json_parse_error", error=str(e))
            return self._fallback_rca(alert, "JSON parse error from Qwen")
        except Exception as e:
            logger.error("analyzer_error", error=str(e))
            return self._fallback_rca(alert, str(e))

    def _build_prompt(self, alert: Alert, cluster_context: Optional[dict]) -> str:
        ctx = json.dumps(cluster_context or {}, indent=2)
        raw = json.dumps(alert.raw_data, indent=2)

        return f"""## Kubernetes Incident Alert

**Alert ID:** {alert.id}
**Timestamp:** {alert.timestamp}
**Severity:** {alert.severity}
**Type:** {alert.type}
**Namespace:** {alert.namespace}
**Affected Resource:** {alert.resource}
**Message:** {alert.message}

**Raw Event Data:**
```json
{raw}
```

**Additional Cluster Context:**
```json
{ctx}
```

Analyze this incident. Identify the root cause and recommend the exact remediation action.
Respond only in the JSON format specified."""

    def _fallback_rca(self, alert: Alert, error: str) -> RCA:
        """Fallback RCA when Qwen is unavailable."""
        return RCA(
            alert_id=alert.id,
            root_cause=f"Analysis failed: {error}. Manual investigation required.",
            confidence="low",
            recommended_action="Escalate to on-call engineer for manual review",
            action_type="escalate",
            risk_level="high",
            auto_remediate=False,
            reasoning_trace=f"Qwen API call failed: {error}",
            estimated_fix_time="Manual",
        )
