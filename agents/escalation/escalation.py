"""
Escalation Agent — Handles human notification + approval workflows.
Uses Qwen-Turbo to generate concise incident summaries for Slack.
Implements operator approval flow with timeout.
"""

import os
import json
import asyncio
import httpx
import structlog
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
from openai import AsyncOpenAI
from agents.detector.detector import Alert
from agents.analyzer.analyzer import RCA
from agents.planner.planner import RemediationPlan

logger = structlog.get_logger(__name__)


class EscalationEvent(BaseModel):
    alert_id: str
    severity: str
    summary: str
    recommended_action: str
    requires_approval: bool
    approval_token: Optional[str]
    notified_at: str
    channel: str


class ApprovalDecision(BaseModel):
    token: str
    approved: bool
    operator: str
    reason: Optional[str]
    decided_at: str


class EscalationAgent:
    """
    Generates Qwen-Turbo summaries and sends Slack notifications.
    Manages approval tokens for human-in-the-loop decisions.
    """

    def __init__(self):
        api_key = os.getenv("QWEN_API_KEY")
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.turbo_model = os.getenv("QWEN_MODEL_TURBO", "qwen-turbo")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")

        # Pending approvals: token -> asyncio.Event
        self._pending: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, ApprovalDecision] = {}

    async def escalate(
        self,
        alert: Alert,
        rca: RCA,
        plan: RemediationPlan,
    ) -> EscalationEvent:
        """Send escalation notification and optionally wait for approval."""

        summary = await self._generate_summary(alert, rca, plan)
        token = self._make_token(alert.id)

        event = EscalationEvent(
            alert_id=alert.id,
            severity=alert.severity,
            summary=summary,
            recommended_action=rca.recommended_action,
            requires_approval=plan.requires_approval,
            approval_token=token if plan.requires_approval else None,
            notified_at=datetime.now(timezone.utc).isoformat(),
            channel="slack",
        )

        await self._send_slack(event, plan)
        logger.info("escalation_sent",
                    alert_id=alert.id,
                    requires_approval=plan.requires_approval)
        return event

    async def wait_for_approval(
        self,
        token: str,
        timeout_seconds: int = 300,
    ) -> ApprovalDecision:
        """
        Block until operator approves/rejects or timeout.
        Auto-rejects on timeout for safety.
        """
        event = asyncio.Event()
        self._pending[token] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            decision = self._decisions.get(token)
            if decision:
                logger.info("approval_received",
                            token=token,
                            approved=decision.approved,
                            operator=decision.operator)
                return decision
        except asyncio.TimeoutError:
            logger.warning("approval_timeout", token=token, timeout=timeout_seconds)
        finally:
            self._pending.pop(token, None)

        # Auto-reject on timeout (or missing decision)
        return ApprovalDecision(
            token=token,
            approved=False,
            operator="system",
            reason=f"Auto-rejected: no response within {timeout_seconds}s",
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

    def submit_approval(self, token: str, approved: bool, operator: str, reason: str = "") -> bool:
        """Called by API endpoint when operator approves/rejects."""
        if token not in self._pending:
            return False

        self._decisions[token] = ApprovalDecision(
            token=token,
            approved=approved,
            operator=operator,
            reason=reason,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        self._pending[token].set()
        return True

    async def _generate_summary(self, alert: Alert, rca: RCA, plan: RemediationPlan) -> str:
        """Use Qwen-Turbo to generate a concise incident summary for humans."""
        prompt = f"""Generate a concise Slack incident summary (max 3 sentences) for this K8s incident:

Alert: {alert.message}
Root Cause: {rca.root_cause}
Recommended Action: {rca.recommended_action}
Risk Level: {rca.risk_level}
Runbook: {plan.runbook_name}
Estimated Fix Time: {plan.estimated_duration}

Be direct and technical. No fluff."""

        try:
            resp = await self.client.chat.completions.create(
                model=self.turbo_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("summary_generation_failed", error=str(e))
            return f"[{alert.severity.upper()}] {alert.message} | Action: {rca.recommended_action}"

    async def _send_slack(self, event: EscalationEvent, plan: RemediationPlan):
        """Send Slack notification via webhook."""
        if not self.slack_webhook:
            logger.info("slack_webhook_not_configured_skipping")
            return

        color = {"critical": "#FF0000", "warning": "#FFA500", "info": "#36A64F"}.get(event.severity, "#888888")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:rotating_light: NeuroScale Autopilot — {event.severity.upper()} Incident*\n{event.summary}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Alert ID:*\n`{event.alert_id}`"},
                    {"type": "mrkdwn", "text": f"*Runbook:*\n`{plan.runbook_name}`"},
                    {"type": "mrkdwn", "text": f"*Recommended Action:*\n{event.recommended_action}"},
                    {"type": "mrkdwn", "text": f"*ETA:*\n{plan.estimated_duration}"},
                ]
            }
        ]

        if event.requires_approval:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Human approval required*\nApproval token: `{event.approval_token}`\nUse `/approve {event.approval_token}` or `/reject {event.approval_token}` in the dashboard."
                }
            })

        payload = {"attachments": [{"color": color, "blocks": blocks}]}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.slack_webhook, json=payload, timeout=10)
                logger.info("slack_notification_sent", status=resp.status_code)
        except Exception as e:
            logger.error("slack_send_failed", error=str(e))

    def _make_token(self, alert_id: str) -> str:
        import hashlib, time
        raw = f"{alert_id}-{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]
