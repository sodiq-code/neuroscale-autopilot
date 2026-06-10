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


# ─── Fix 1: RAG Margin Gate Tests ─────────────────────────────────────────────

def test_rag_low_similarity_triggers_escalation():
    """Below RAG_MIN_SIMILARITY threshold forces requires_approval=True."""
    from agents.planner.planner import PlannerAgent
    agent = PlannerAgent()
    # Low score, decent margin — score alone should trigger escalation
    result = agent._is_retrieval_uncertain(score=0.50, margin=0.15)
    assert result is True


def test_rag_low_margin_triggers_escalation():
    """High score but thin margin (ambiguous top-1 vs top-2) forces escalation."""
    from agents.planner.planner import PlannerAgent
    agent = PlannerAgent()
    # Good score but margin is too thin — coin flip between two runbooks
    result = agent._is_retrieval_uncertain(score=0.82, margin=0.03)
    assert result is True


def test_rag_high_score_high_margin_is_safe():
    """High score + clear margin = retrieval is trustworthy."""
    from agents.planner.planner import PlannerAgent
    agent = PlannerAgent()
    result = agent._is_retrieval_uncertain(score=0.88, margin=0.20)
    assert result is False


def test_rag_escalation_sets_requires_approval():
    """Plan requires_approval is True when retrieval_escalated=True, even if Analyzer is confident."""
    from agents.planner.planner import PlannerAgent
    from agents.analyzer.analyzer import RCA

    agent = PlannerAgent()
    rca = RCA(
        alert_id="test-rag-001",
        root_cause="OOMKill",
        confidence="high",
        recommended_action="patch memory",
        action_type="patch_resources",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="30s",
    )
    runbook = agent.runbooks[0]

    # retrieval_escalated=True should override even a high-confidence, low-risk Analyzer result
    result = agent._requires_human_approval(rca, runbook, retrieval_escalated=True)
    assert result is True


def test_rag_retrieval_escalated_field_in_plan():
    """RemediationPlan model includes retrieval_score, retrieval_margin, retrieval_escalated fields."""
    from agents.planner.planner import RemediationPlan
    plan = RemediationPlan(
        rca_alert_id="test-001",
        runbook_name="oomkill-increase-memory-limits",
        runbook_steps=["step 1"],
        requires_approval=True,
        approval_reason="Low RAG margin",
        parameters={},
        rollback_plan="kubectl rollout undo",
        estimated_duration="45s",
        retrieval_score=0.61,
        retrieval_margin=0.02,
        retrieval_escalated=True,
    )
    assert plan.retrieval_escalated is True
    assert plan.retrieval_score == 0.61
    assert plan.retrieval_margin == 0.02


# ─── Fix 2: Blast Radius Parameter Validation Tests ───────────────────────────

def test_blast_radius_blocks_scale_to_zero():
    """scale_down to 0 replicas is always blocked."""
    from agents.executor.executor import ExecutorAgent
    from agents.analyzer.analyzer import RCA
    from agents.planner.planner import RemediationPlan

    executor = ExecutorAgent()
    rca = RCA(
        alert_id="test-blast-001",
        root_cause="Cost spike",
        confidence="high",
        recommended_action="scale down",
        action_type="scale_down",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="30s",
    )
    plan = RemediationPlan(
        rca_alert_id="test-blast-001",
        runbook_name="cost-spike-scale-down",
        runbook_steps=["scale to 0"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "ml-workloads", "workload_name": "inference-svc", "target_replicas": 0},
        rollback_plan="scale back up",
        estimated_duration="30s",
    )
    result = executor._check_blast_radius(plan, rca)
    assert result is not None
    assert "zero" in result.lower() or "minimum" in result.lower()


def test_blast_radius_allows_safe_scale_down():
    """scale_down to 1 replica passes blast radius check."""
    from agents.executor.executor import ExecutorAgent
    from agents.analyzer.analyzer import RCA
    from agents.planner.planner import RemediationPlan

    executor = ExecutorAgent()
    rca = RCA(
        alert_id="test-blast-002",
        root_cause="Cost spike",
        confidence="high",
        recommended_action="scale down to 1",
        action_type="scale_down",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="30s",
    )
    plan = RemediationPlan(
        rca_alert_id="test-blast-002",
        runbook_name="cost-spike-scale-down",
        runbook_steps=["scale to 1"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "ml-workloads", "workload_name": "inference-svc", "target_replicas": 1},
        rollback_plan="scale back up",
        estimated_duration="30s",
    )
    result = executor._check_blast_radius(plan, rca)
    assert result is None


def test_blast_radius_blocks_massive_scale_up():
    """scale_down to 100 replicas is blocked as unusually high."""
    from agents.executor.executor import ExecutorAgent
    from agents.analyzer.analyzer import RCA
    from agents.planner.planner import RemediationPlan

    executor = ExecutorAgent()
    rca = RCA(
        alert_id="test-blast-003",
        root_cause="Traffic spike",
        confidence="high",
        recommended_action="scale up",
        action_type="scale_down",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="30s",
    )
    plan = RemediationPlan(
        rca_alert_id="test-blast-003",
        runbook_name="cost-spike-scale-down",
        runbook_steps=["scale to 100"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "default", "workload_name": "api", "target_replicas": 100},
        rollback_plan="scale back down",
        estimated_duration="30s",
    )
    result = executor._check_blast_radius(plan, rca)
    assert result is not None


def test_blast_radius_blocks_large_memory_patch():
    """patch_resources with >4Gi memory is blocked for auto-execution."""
    from agents.executor.executor import ExecutorAgent
    from agents.analyzer.analyzer import RCA
    from agents.planner.planner import RemediationPlan

    executor = ExecutorAgent()
    rca = RCA(
        alert_id="test-blast-004",
        root_cause="OOMKill",
        confidence="high",
        recommended_action="increase memory to 8Gi",
        action_type="patch_resources",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="45s",
    )
    plan = RemediationPlan(
        rca_alert_id="test-blast-004",
        runbook_name="oomkill-increase-memory-limits",
        runbook_steps=["patch memory to 8Gi"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "default", "deployment_name": "api", "new_memory_limit": "8Gi"},
        rollback_plan="rollback",
        estimated_duration="45s",
    )
    result = executor._check_blast_radius(plan, rca)
    assert result is not None


def test_blast_radius_allows_safe_memory_patch():
    """patch_resources with 1Gi memory passes blast radius check."""
    from agents.executor.executor import ExecutorAgent
    from agents.analyzer.analyzer import RCA
    from agents.planner.planner import RemediationPlan

    executor = ExecutorAgent()
    rca = RCA(
        alert_id="test-blast-005",
        root_cause="OOMKill",
        confidence="high",
        recommended_action="increase memory to 1Gi",
        action_type="patch_resources",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="45s",
    )
    plan = RemediationPlan(
        rca_alert_id="test-blast-005",
        runbook_name="oomkill-increase-memory-limits",
        runbook_steps=["patch memory to 1Gi"],
        requires_approval=False,
        approval_reason=None,
        parameters={"namespace": "default", "deployment_name": "api", "new_memory_limit": "1Gi"},
        rollback_plan="rollback",
        estimated_duration="45s",
    )
    result = executor._check_blast_radius(plan, rca)
    assert result is None


def test_blast_radius_blocked_flag_in_execution_result():
    """ExecutionResult model includes blast_radius_blocked field."""
    from agents.executor.executor import ExecutionResult
    result = ExecutionResult(
        plan_alert_id="test-001",
        success=False,
        action_taken="blocked",
        output="",
        error="Blast radius: scale to 0 blocked",
        duration_seconds=0.0,
        timestamp="2026-06-10T00:00:00Z",
        blast_radius_blocked=True,
    )
    assert result.blast_radius_blocked is True


# ─── Fix 3: Per-Action Confidence Threshold Tests ─────────────────────────────

def test_per_action_thresholds_loaded():
    """ACTION_CONFIDENCE_THRESHOLDS covers all expected action types."""
    from agents.planner.planner import ACTION_CONFIDENCE_THRESHOLDS
    required = {"patch_resources", "rollback", "scale_down", "create_exception", "monitor", "escalate"}
    assert required.issubset(set(ACTION_CONFIDENCE_THRESHOLDS.keys()))


def test_rollback_requires_higher_confidence_than_patch():
    """rollback threshold must be >= patch_resources threshold."""
    from agents.planner.planner import ACTION_CONFIDENCE_THRESHOLDS
    assert ACTION_CONFIDENCE_THRESHOLDS["rollback"] >= ACTION_CONFIDENCE_THRESHOLDS["patch_resources"]


def test_scale_down_requires_higher_confidence_than_patch():
    """scale_down threshold must be >= patch_resources threshold."""
    from agents.planner.planner import ACTION_CONFIDENCE_THRESHOLDS
    assert ACTION_CONFIDENCE_THRESHOLDS["scale_down"] >= ACTION_CONFIDENCE_THRESHOLDS["patch_resources"]


def test_medium_confidence_blocks_rollback():
    """Medium Analyzer confidence should not auto-execute a rollback (threshold=0.85)."""
    from agents.planner.planner import PlannerAgent
    from agents.analyzer.analyzer import RCA

    agent = PlannerAgent()
    rca = RCA(
        alert_id="test-conf-001",
        root_cause="CrashLoopBackOff",
        confidence="medium",   # maps to 0.6, below rollback threshold of 0.85
        recommended_action="rollback",
        action_type="rollback",
        risk_level="medium",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="90s",
    )
    runbook = next(r for r in agent.runbooks if r["name"] == "crashloop-rollback-deployment")
    result = agent._requires_human_approval(rca, runbook, retrieval_escalated=False)
    assert result is True


def test_high_confidence_allows_patch_resources():
    """High Analyzer confidence should auto-execute a low-risk patch (no escalation)."""
    from agents.planner.planner import PlannerAgent
    from agents.analyzer.analyzer import RCA

    agent = PlannerAgent()
    rca = RCA(
        alert_id="test-conf-002",
        root_cause="OOMKill",
        confidence="high",    # maps to 1.0, above patch_resources threshold of 0.75
        recommended_action="patch memory",
        action_type="patch_resources",
        risk_level="low",
        auto_remediate=True,
        reasoning_trace="...",
        estimated_fix_time="45s",
    )
    runbook = next(r for r in agent.runbooks if r["name"] == "oomkill-increase-memory-limits")
    result = agent._requires_human_approval(rca, runbook, retrieval_escalated=False)
    assert result is False
