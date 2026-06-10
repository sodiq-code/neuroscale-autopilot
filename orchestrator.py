"""
NeuroScale Autopilot — Main Orchestrator
Wires all 5 agents together into the self-healing pipeline:
Detector → Analyzer → Planner → Executor → Escalation
"""

import asyncio
import structlog
from typing import Optional
from agents.detector.detector import DetectorAgent, Alert
from agents.analyzer.analyzer import AnalyzerAgent, RCA
from agents.planner.planner import PlannerAgent, RemediationPlan
from agents.executor.executor import ExecutorAgent, ExecutionResult
from agents.escalation.escalation import EscalationAgent

logger = structlog.get_logger(__name__)

# Global in-memory incident log (replace with DB in production)
incident_log: list[dict] = []


class Orchestrator:
    """
    Central pipeline that connects all 5 agents.
    On each alert: Detect → Analyze → Plan → [Approve?] → Execute → Escalate
    """

    def __init__(self, approval_timeout: int = 300):
        self.analyzer = AnalyzerAgent()
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.escalation = EscalationAgent()
        self.approval_timeout = approval_timeout

        self.detector = DetectorAgent(on_alert=self._handle_alert)
        self._processed_alerts: set[str] = set()

    async def start(self):
        """Start the full autopilot pipeline."""
        logger.info("neuroscale_autopilot_starting")
        await self.detector.start()

    async def stop(self):
        """Stop all agents."""
        await self.detector.stop()
        logger.info("neuroscale_autopilot_stopped")

    async def _handle_alert(self, alert: Alert):
        """Process a single alert through the full pipeline."""
        # Deduplicate
        if alert.id in self._processed_alerts:
            return
        self._processed_alerts.add(alert.id)

        incident = {
            "alert": alert.model_dump(),
            "rca": None,
            "plan": None,
            "execution": None,
            "status": "detecting",
        }
        incident_log.append(incident)

        logger.info("pipeline_start", alert_id=alert.id, type=alert.type)

        try:
            # Step 1: Analyze with Qwen-Max
            incident["status"] = "analyzing"
            rca = await self.analyzer.analyze(alert)
            incident["rca"] = rca.model_dump()

            # Step 2: Plan remediation with RAG
            incident["status"] = "planning"
            plan = await self.planner.plan(rca)
            incident["plan"] = plan.model_dump()

            # Step 3: Escalate if needed (notify humans)
            escalation_event = await self.escalation.escalate(alert, rca, plan)
            incident["escalation"] = escalation_event.model_dump()

            # Step 4: Human-in-the-loop checkpoint
            if plan.requires_approval:
                incident["status"] = "awaiting_approval"
                logger.info("awaiting_human_approval",
                            alert_id=alert.id,
                            token=escalation_event.approval_token,
                            timeout=self.approval_timeout)

                decision = await self.escalation.wait_for_approval(
                    token=escalation_event.approval_token,
                    timeout_seconds=self.approval_timeout,
                )
                incident["approval"] = decision.model_dump()

                if not decision.approved:
                    incident["status"] = "rejected"
                    logger.info("remediation_rejected",
                                alert_id=alert.id,
                                reason=decision.reason)
                    return

            # Step 5: Execute remediation
            incident["status"] = "executing"
            result = await self.executor.execute(plan, rca)
            incident["execution"] = result.model_dump()

            if result.blast_radius_blocked:
                # Blast radius check caught a dangerous parameter — escalate to human
                incident["status"] = "escalated_blast_radius"
                logger.warning("blast_radius_escalation",
                               alert_id=alert.id,
                               reason=result.error)
            elif result.success:
                incident["status"] = "resolved"
                logger.info("incident_resolved",
                            alert_id=alert.id,
                            duration=result.duration_seconds,
                            action=result.action_taken)
            else:
                incident["status"] = "failed"
                logger.error("incident_resolution_failed",
                             alert_id=alert.id,
                             error=result.error)

        except Exception as e:
            incident["status"] = "error"
            incident["error"] = str(e)
            logger.error("pipeline_error", alert_id=alert.id, error=str(e))

    def get_incidents(self) -> list[dict]:
        return list(reversed(incident_log))

    def get_incident(self, alert_id: str) -> Optional[dict]:
        for inc in incident_log:
            if inc["alert"]["id"] == alert_id:
                return inc
        return None

    async def simulate(self, scenario: str = "oomkill") -> dict:
        """Trigger a demo scenario for testing/demo purposes."""
        logger.info("simulation_triggered", scenario=scenario)
        alert = await self.detector.simulate_alert(scenario)
        # Wait briefly for pipeline to process
        await asyncio.sleep(2)
        return self.get_incident(alert.id) or {"alert_id": alert.id, "status": "processing"}
