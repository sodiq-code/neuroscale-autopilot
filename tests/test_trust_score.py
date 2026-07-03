"""
Test suite for NeuroScale v2 Trust Score Engine.

Tests cover:
- Trust score computation
- Sub-score calculations (reversibility, blast radius, runbook confidence, history)
- Execution mode determination
- Decision path validation
- Edge cases and boundary conditions
"""

import pytest
import json
from datetime import datetime
from agents.trust import (
    TrustScoreEngine,
    ReversibilityAnalyzer,
    BlastRadiusAnalyzer,
    RunbookConfidenceAnalyzer,
    HistoryAnalyzer,
)
from agents.trust.score import ExecutionMode


class TestTrustScoreEngine:
    """Tests for the main trust score engine."""

    @pytest.fixture
    def engine(self):
        """Create a trust score engine instance."""
        return TrustScoreEngine(
            execute_threshold=90.0,
            dryrun_threshold=70.0,
            escalation_timeout_seconds=300,
        )

    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.execute_threshold == 90.0
        assert engine.dryrun_threshold == 70.0
        assert engine.escalation_timeout_seconds == 300
        assert engine.weights["reversibility"] == 0.30
        assert engine.weights["blast_radius"] == 0.25
        assert engine.weights["runbook_confidence"] == 0.25
        assert engine.weights["history"] == 0.20

    def test_high_trust_score_execute_mode(self, engine):
        """Test that high trust scores result in EXECUTE mode."""
        result = engine.compute_score(
            alert_id="alert-001",
            action_id="action-001",
            action_type="scale_up",
            target_resource={"kind": "Deployment", "name": "test-app"},
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.95,
                "retrieval_margin": 0.5,
                "steps": ["scale-up"],
                "rollback_plan": True,
            },
        )

        assert result.final_score >= 90.0
        assert result.execution_mode == ExecutionMode.EXECUTE
        assert "immediately" in result.reasoning.lower()

    def test_medium_trust_score_dryrun_mode(self, engine):
        """Test that medium trust scores result in DRYRUN_VERIFY mode."""
        result = engine.compute_score(
            alert_id="alert-002",
            action_id="action-002",
            action_type="patch_resource",
            target_resource={"kind": "ConfigMap", "name": "config"},
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.70,
                "retrieval_margin": 0.2,
                "steps": ["patch"],
            },
        )

        assert 70.0 <= result.final_score < 90.0
        assert result.execution_mode == ExecutionMode.DRYRUN_VERIFY
        assert "dry-run" in result.reasoning.lower()

    def test_low_trust_score_escalate_mode(self, engine):
        """Test that low trust scores result in ESCALATE_HUMAN mode."""
        result = engine.compute_score(
            alert_id="alert-003",
            action_id="action-003",
            action_type="delete_resource",
            target_resource={"kind": "Pod", "name": "test-pod"},
            remediation_plan={
                "runbook_found": False,
                "retrieval_score": 0.3,
                "retrieval_margin": 0.0,
            },
        )

        assert result.final_score < 70.0
        assert result.execution_mode == ExecutionMode.ESCALATE_HUMAN
        assert "escalat" in result.reasoning.lower()

    def test_score_result_structure(self, engine):
        """Test that score result has all required fields."""
        result = engine.compute_score(
            alert_id="alert-004",
            action_id="action-004",
            action_type="scale_down",
            target_resource={"kind": "Deployment"},
            remediation_plan={"runbook_found": True, "retrieval_score": 0.8},
        )

        assert result.final_score is not None
        assert result.execution_mode is not None
        assert result.reversibility_score is not None
        assert result.blast_radius_score is not None
        assert result.runbook_confidence_score is not None
        assert result.history_score is not None
        assert result.reasoning is not None
        assert result.timestamp is not None
        assert result.action_id == "action-004"
        assert result.alert_id == "alert-004"

    def test_score_is_normalized(self, engine):
        """Test that all scores are normalized to 0-100."""
        result = engine.compute_score(
            alert_id="alert-005",
            action_id="action-005",
            action_type="scale_up",
            target_resource={"kind": "Deployment"},
            remediation_plan={"runbook_found": True, "retrieval_score": 0.9},
        )

        assert 0 <= result.final_score <= 100
        assert 0 <= result.reversibility_score <= 100
        assert 0 <= result.blast_radius_score <= 100
        assert 0 <= result.runbook_confidence_score <= 100
        assert 0 <= result.history_score <= 100


class TestReversibilityAnalyzer:
    """Tests for the reversibility analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a reversibility analyzer."""
        return ReversibilityAnalyzer()

    def test_scale_up_is_highly_reversible(self, analyzer):
        """Test that scale-up is highly reversible."""
        score = analyzer.analyze(
            action_type="scale_up",
            target_resource={"kind": "Deployment"},
            remediation_plan={},
        )
        assert score >= 90

    def test_delete_is_low_reversibility(self, analyzer):
        """Test that delete has low reversibility."""
        score = analyzer.analyze(
            action_type="delete_resource",
            target_resource={"kind": "Pod"},
            remediation_plan={},
        )
        assert score <= 30

    def test_rollback_with_backup_is_reversible(self, analyzer):
        """Test that rollback with backup is highly reversible."""
        score = analyzer.analyze(
            action_type="rollback_deployment",
            target_resource={"kind": "Deployment"},
            remediation_plan={"has_backup": True, "rollback_plan": True},
        )
        assert score >= 85

    def test_resource_adjustment_applied(self, analyzer):
        """Test that resource type adjustment is applied."""
        pv_score = analyzer.analyze(
            action_type="patch_resource",
            target_resource={"kind": "PersistentVolume"},
            remediation_plan={},
        )
        pod_score = analyzer.analyze(
            action_type="patch_resource",
            target_resource={"kind": "Pod"},
            remediation_plan={},
        )
        # PV should have lower score than Pod
        assert pv_score < pod_score


class TestBlastRadiusAnalyzer:
    """Tests for the blast radius analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a blast radius analyzer."""
        return BlastRadiusAnalyzer()

    def test_single_pod_low_blast_radius(self, analyzer):
        """Test that single pod has low blast radius."""
        score = analyzer.analyze(
            action_type="delete_pod",
            target_resource={"kind": "Pod", "name": "test-pod"},
        )
        assert score >= 90

    def test_deployment_with_replicas_higher_blast_radius(self, analyzer):
        """Test that deployment with replicas has higher blast radius."""
        score = analyzer.analyze(
            action_type="scale_down",
            target_resource={
                "kind": "Deployment",
                "spec": {"replicas": 10},
            },
        )
        assert score < 90

    def test_node_drain_high_blast_radius(self, analyzer):
        """Test that node drain has high blast radius."""
        score = analyzer.analyze(
            action_type="drain_node",
            target_resource={"kind": "Node", "name": "node-1"},
            cluster_state={"pods_on_node": {"node-1": 50}},
        )
        assert score < 50


class TestRunbookConfidenceAnalyzer:
    """Tests for the runbook confidence analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a runbook confidence analyzer."""
        return RunbookConfidenceAnalyzer()

    def test_no_runbook_low_confidence(self, analyzer):
        """Test that missing runbook results in low confidence."""
        score = analyzer.analyze(
            remediation_plan={"runbook_found": False},
            action_type="scale_down",
        )
        assert score == 20.0

    def test_high_retrieval_score_high_confidence(self, analyzer):
        """Test that high retrieval score results in high confidence."""
        score = analyzer.analyze(
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.95,
                "retrieval_margin": 0.5,
                "steps": ["step1", "step2"],
                "rollback_plan": True,
            },
            action_type="scale_down",
        )
        assert score >= 80

    def test_low_retrieval_score_low_confidence(self, analyzer):
        """Test that low retrieval score results in low confidence."""
        score = analyzer.analyze(
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.3,
                "retrieval_margin": 0.0,
            },
            action_type="scale_down",
        )
        assert score < 50

    def test_escalated_runbook_penalized(self, analyzer):
        """Test that escalated runbooks are penalized."""
        normal_score = analyzer.analyze(
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.7,
                "retrieval_escalated": False,
            },
            action_type="scale_down",
        )
        escalated_score = analyzer.analyze(
            remediation_plan={
                "runbook_found": True,
                "retrieval_score": 0.7,
                "retrieval_escalated": True,
            },
            action_type="scale_down",
        )
        assert escalated_score < normal_score


class TestHistoryAnalyzer:
    """Tests for the history analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a history analyzer."""
        return HistoryAnalyzer(history_file="/tmp/test_outcomes.jsonl")

    def test_no_history_neutral_score(self, analyzer):
        """Test that no history results in neutral score."""
        score = analyzer.analyze(
            action_type="unknown_action",
            alert_id="alert-001",
        )
        assert score == 50.0

    def test_success_rate_to_score_conversion(self, analyzer):
        """Test conversion of success rate to score."""
        # High success rate should give high score
        high_score = analyzer._success_rate_to_score(0.95, total_attempts=10)
        assert high_score > 80

        # Low success rate should give low score
        low_score = analyzer._success_rate_to_score(0.3, total_attempts=10)
        assert low_score < 50

    def test_confidence_adjustment_applied(self, analyzer):
        """Test that confidence adjustment is applied."""
        # More attempts = higher confidence
        confident_score = analyzer._success_rate_to_score(0.7, total_attempts=20)
        uncertain_score = analyzer._success_rate_to_score(0.7, total_attempts=1)
        assert confident_score > uncertain_score


class TestExecutionModeDescription:
    """Tests for execution mode descriptions."""

    @pytest.fixture
    def engine(self):
        """Create a trust score engine."""
        return TrustScoreEngine()

    def test_execute_mode_description(self, engine):
        """Test EXECUTE mode description."""
        desc = engine.get_execution_mode_description(ExecutionMode.EXECUTE)
        assert "immediately" in desc.lower()

    def test_dryrun_mode_description(self, engine):
        """Test DRYRUN_VERIFY mode description."""
        desc = engine.get_execution_mode_description(ExecutionMode.DRYRUN_VERIFY)
        assert "dry-run" in desc.lower()

    def test_escalate_mode_description(self, engine):
        """Test ESCALATE_HUMAN mode description."""
        desc = engine.get_execution_mode_description(ExecutionMode.ESCALATE_HUMAN)
        assert "human" in desc.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
