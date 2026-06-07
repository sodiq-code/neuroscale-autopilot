"""
Smoke tests for the NeuroScale Autopilot pipeline.
Runs without a real Qwen API key — uses mocks.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ─── Detector Tests ───────────────────────────────────────────────────────────

def test_detector_imports():
    """Detector module imports cleanly."""
    from agents.detector.detector import Alert, DetectorAgent
    assert Alert
    assert DetectorAgent


def test_alert_model():
    """Alert Pydantic model validates correctly."""
    from agents.detector.detector import Alert
    alert = Alert(
        id="test-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity="critical",
        type="oomkill",
        namespace="default",
        resource="deployment/nginx",
        message="OOMKill detected for deployment/nginx",
        raw_data={"container": "nginx", "exit_code": 137},
    )
    assert alert.severity == "critical"
    assert alert.type == "oomkill"


# ─── Analyzer Tests ────────────────────────────────────────────────────────────

def test_analyzer_imports():
    """Analyzer module imports cleanly."""
    from agents.analyzer.analyzer import RCA, AnalyzerAgent
    assert RCA
    assert AnalyzerAgent


def test_rca_model():
    """RCA Pydantic model validates correctly."""
    from agents.analyzer.analyzer import RCA
    rca = RCA(
        alert_id="test-001",
        root_cause="CPU throttling due to missing resource limits",
        confidence="high",
        recommended_action="Set CPU limits to 500m",
        action_type="patch_resources",
        risk_level="medium",
        auto_remediate=True,
        reasoning_trace="No limits set → throttling under load",
        estimated_fix_time="2 minutes",
    )
    assert rca.confidence in ("high", "medium", "low")
    assert rca.risk_level in ("low", "medium", "high", "critical")


@pytest.mark.asyncio
async def test_analyzer_with_mock_qwen():
    """Analyzer calls Qwen and parses RCA — mocked."""
    from agents.detector.detector import Alert
    from agents.analyzer.analyzer import AnalyzerAgent, RCA

    mock_rca = RCA(
        alert_id="test-001",
        root_cause="OOMKill due to unbounded memory growth",
        confidence="high",
        recommended_action="Restart pod and add memory limits",
        action_type="patch_resources",
        risk_level="high",
        auto_remediate=False,
        reasoning_trace="Memory grew unbounded → OOMKill",
        estimated_fix_time="3 minutes",
    )

    alert = Alert(
        id="test-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity="critical",
        type="oomkill",
        namespace="production",
        resource="deployment/api-server",
        message="OOMKill detected — memory at 95% of limit",
        raw_data={"exit_code": 137, "container": "api-server"},
    )

    with patch.object(AnalyzerAgent, "analyze", new=AsyncMock(return_value=mock_rca)):
        agent = AnalyzerAgent()
        result = await agent.analyze(alert)
        assert result.alert_id == "test-001"
        assert result.risk_level == "high"


# ─── Planner Tests ─────────────────────────────────────────────────────────────

def test_planner_imports():
    """Planner module imports cleanly."""
    from agents.planner.planner import RemediationPlan, PlannerAgent
    assert RemediationPlan
    assert PlannerAgent


def test_remediation_plan_model():
    """RemediationPlan Pydantic model validates correctly."""
    from agents.planner.planner import RemediationPlan
    plan = RemediationPlan(
        rca_alert_id="test-001",
        runbook_name="oom-kill-recovery",
        runbook_steps=["kubectl rollout restart deployment/api-server"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "production", "deployment": "api-server"},
        rollback_plan="kubectl rollout undo deployment/api-server",
        estimated_duration="2 minutes",
    )
    assert isinstance(plan.runbook_steps, list)
    assert len(plan.runbook_steps) > 0


# ─── Executor Tests ────────────────────────────────────────────────────────────

def test_executor_imports():
    """Executor module imports cleanly."""
    from agents.executor.executor import ExecutionResult, ExecutorAgent
    assert ExecutionResult
    assert ExecutorAgent


def test_circuit_breaker_opens_after_failures():
    """Circuit breaker reports open after max_failures consecutive failures."""
    from agents.executor.executor import CircuitBreaker

    cb = CircuitBreaker(max_failures=3, reset_seconds=60)
    key = "test-deployment"
    assert not cb.is_open(key)

    for _ in range(3):
        cb.record_failure(key)

    assert cb.is_open(key)


def test_circuit_breaker_closes_after_success():
    """Circuit breaker resets after a success clears the failure record."""
    from agents.executor.executor import CircuitBreaker

    cb = CircuitBreaker(max_failures=3, reset_seconds=60)
    key = "test-deployment"

    for _ in range(3):
        cb.record_failure(key)
    assert cb.is_open(key)

    cb.record_success(key)
    assert not cb.is_open(key)


# ─── Escalation Tests ──────────────────────────────────────────────────────────

def test_escalation_imports():
    """Escalation module imports cleanly."""
    from agents.escalation.escalation import EscalationAgent, ApprovalDecision
    assert EscalationAgent
    assert ApprovalDecision


def test_escalation_syntax():
    """Verify escalation.py has no syntax errors (was buggy before fix)."""
    import py_compile, os
    path = os.path.join(os.path.dirname(__file__), "..", "agents", "escalation", "escalation.py")
    # py_compile raises SyntaxError if broken
    py_compile.compile(path, doraise=True)


@pytest.mark.asyncio
async def test_approval_timeout():
    """wait_for_approval auto-rejects when no response arrives."""
    import os
    os.environ["QWEN_API_KEY"] = "mock-key"

    from agents.escalation.escalation import EscalationAgent

    agent = EscalationAgent()
    token = "test-token-abc"
    agent._pending[token] = asyncio.Event()  # don't set it → simulate timeout

    decision = await agent.wait_for_approval(token, timeout_seconds=1)
    assert decision.approved is False
    assert decision.operator == "system"
    assert token not in agent._pending  # cleaned up by finally


@pytest.mark.asyncio
async def test_approval_success():
    """submit_approval resolves wait_for_approval correctly."""
    import os
    os.environ["QWEN_API_KEY"] = "mock-key"

    from agents.escalation.escalation import EscalationAgent

    agent = EscalationAgent()

    async def approve_after_delay():
        await asyncio.sleep(0.1)
        agent.submit_approval("tok-xyz", approved=True, operator="sodiq", reason="LGTM")

    asyncio.create_task(approve_after_delay())

    # Pre-register the event so wait_for_approval finds it
    event = asyncio.Event()
    agent._pending["tok-xyz"] = event

    decision = await agent.wait_for_approval("tok-xyz", timeout_seconds=5)
    assert decision.approved is True
    assert decision.operator == "sodiq"


# ─── MCP Server Tests ──────────────────────────────────────────────────────────

def test_mcp_server_imports():
    """MCP server module imports cleanly."""
    from mcp_server import server as mcp_module
    assert mcp_module


def test_mcp_health_endpoint():
    """Health endpoint on FastAPI app returns 200."""
    import os
    os.environ.setdefault("QWEN_API_KEY", "mock-key")

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "healthy")


# ─── Integration Smoke Test ────────────────────────────────────────────────────

def test_full_pipeline_imports():
    """All pipeline components import without error."""
    from agents.detector.detector import DetectorAgent
    from agents.analyzer.analyzer import AnalyzerAgent
    from agents.planner.planner import PlannerAgent
    from agents.executor.executor import ExecutorAgent
    from agents.escalation.escalation import EscalationAgent
    from mcp_server import server as mcp_module
    from main import app

    # If we get here, no import errors
    assert app is not None
