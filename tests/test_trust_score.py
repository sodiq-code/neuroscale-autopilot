"""
Tests for the Verifiable Trust Layer (TrustScore).
Covers EXECUTE, DRYRUN_VERIFY, ESCALATE_HUMAN decisions, failure fallback, and history scoring.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import patch


# ─── Setup ────────────────────────────────────────────────────────────────────

def setup_module():
    os.environ.setdefault("QWEN_API_KEY", "mock-trust-key")


# ─── TrustScore Decision Tests ─────────────────────────────────────────────────

def test_trust_score_execute_decision():
    """TrustScore >= 90 yields EXECUTE."""
    from agents.trust.score import TrustScore, TrustDecision
    ts = TrustScore()

    # Mock all factors to return high scores
    with patch.object(ts.reversibility, 'score', return_value=(100.0, "fully reversible")):
        with patch.object(ts.blast_radius, 'score', return_value=(100.0, "no blast")):
            with patch.object(ts.runbook_confidence, 'score', return_value=(90.0, "proven")):
                with patch.object(ts.history, 'score', return_value=(100.0, "all successful")):
                    report = ts.evaluate(
                        alert_id="test-exec-001",
                        action_type="monitor",
                        risk_level="low",
                        parameters={},
                        runbook_name="monitor-only",
                        namespace="default",
                    )

    expected = 100 * 0.30 + 100 * 0.25 + 90 * 0.25 + 100 * 0.20  # = 97.5
    assert round(report.total_score, 1) == round(expected, 1)
    assert report.decision == TrustDecision.EXECUTE


def test_trust_score_dryrun_verify_decision():
    """TrustScore >= 70 but < 90 yields DRYRUN_VERIFY."""
    from agents.trust.score import TrustScore, TrustDecision
    ts = TrustScore()

    with patch.object(ts.reversibility, 'score', return_value=(80.0, "mostly reversible")):
        with patch.object(ts.blast_radius, 'score', return_value=(80.0, "moderate blast")):
            with patch.object(ts.runbook_confidence, 'score', return_value=(70.0, "average")):
                with patch.object(ts.history, 'score', return_value=(70.0, "mixed")):
                    report = ts.evaluate(
                        alert_id="test-dryrun-001",
                        action_type="scale_down",
                        risk_level="medium",
                        parameters={"target_replicas": 2},
                        runbook_name="cost-spike-scale-down",
                        namespace="staging",
                    )

    assert 70 <= report.total_score < 90
    assert report.decision == TrustDecision.DRYRUN_VERIFY


def test_trust_score_escalate_human_decision():
    """TrustScore < 70 yields ESCALATE_HUMAN."""
    from agents.trust.score import TrustScore, TrustDecision
    ts = TrustScore()

    with patch.object(ts.reversibility, 'score', return_value=(30.0, "dangerous")):
        with patch.object(ts.blast_radius, 'score', return_value=(40.0, "wide blast")):
            with patch.object(ts.runbook_confidence, 'score', return_value=(30.0, "untested")):
                with patch.object(ts.history, 'score', return_value=(20.0, "mostly failures")):
                    report = ts.evaluate(
                        alert_id="test-esc-001",
                        action_type="delete_resource",
                        risk_level="critical",
                        parameters={},
                        runbook_name="dangerous-runbook",
                        namespace="production",
                    )

    assert report.total_score < 70
    assert report.decision == TrustDecision.ESCALATE_HUMAN


def test_trust_score_failure_fallback():
    """Any exception during scoring falls back to ESCALATE_HUMAN (fail-safe)."""
    from agents.trust.score import TrustScore, TrustDecision
    ts = TrustScore()

    with patch.object(ts.reversibility, 'score', side_effect=RuntimeError("scorer crashed")):
        report = ts.evaluate(
            alert_id="test-fail-001",
            action_type="patch_resources",
            risk_level="low",
            parameters={},
            runbook_name="safe-runbook",
            namespace="default",
        )

    assert report.total_score == 0
    assert report.decision == TrustDecision.ESCALATE_HUMAN
    assert any("ERROR" in r for r in report.reasoning)


def test_trust_score_report_fields():
    """TrustReport contains all required fields."""
    from agents.trust.score import TrustScore, TrustReport, TrustDecision

    report = TrustReport(
        alert_id="test-fields-001",
        total_score=85.5,
        decision=TrustDecision.DRYRUN_VERIFY,
        factors={"reversibility": 80, "blast_radius": 85, "runbook_confidence": 90, "history": 85},
        reasoning=["reason 1", "reason 2"],
    )

    d = report.to_dict()
    assert d["alert_id"] == "test-fields-001"
    assert d["total_score"] == 85.5
    assert d["decision"] == "DRYRUN_VERIFY"
    assert len(d["factors"]) == 4
    assert len(d["reasoning"]) == 2
    assert "timestamp" in d


def test_history_scoring_with_past_successes():
    """History scorer returns high score when past outcomes were successful."""
    from agents.trust.history import HistoryScorer

    # Create temp outcomes file
    tmpdir = tempfile.mkdtemp()
    outcomes_path = os.path.join(tmpdir, "outcomes.jsonl")

    with open(outcomes_path, "w") as f:
        for _ in range(5):
            f.write(json.dumps({"success": True, "action_taken": "scale_down"}) + "\n")

    with patch("agents.trust.history.OUTCOMES_PATH", outcomes_path):
        scorer = HistoryScorer()
        score, reason = scorer.score("test-hist-001", "scale_down", "cost-spike-scale-down")

    assert score >= 70   # all successes = high score
    assert "5/5" in reason

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_history_scoring_with_past_failures():
    """History scorer returns low score when past outcomes were mostly failures."""
    from agents.trust.history import HistoryScorer

    tmpdir = tempfile.mkdtemp()
    outcomes_path = os.path.join(tmpdir, "outcomes.jsonl")

    with open(outcomes_path, "w") as f:
        f.write(json.dumps({"success": False, "action_taken": "rollback"}) + "\n")
        f.write(json.dumps({"success": False, "action_taken": "rollback"}) + "\n")
        f.write(json.dumps({"success": True, "action_taken": "rollback"}) + "\n")

    with patch("agents.trust.history.OUTCOMES_PATH", outcomes_path):
        scorer = HistoryScorer()
        score, reason = scorer.score("test-hist-002", "rollback", "crashloop-rollback")

    assert score <= 30  # 1/3 success = low
    assert "1/3" in reason

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_trust_score_full_pipeline_with_all_factors():
    """Full TrustScore evaluation exercises all 4 factors + decision classification."""
    from agents.trust.score import TrustScore, TrustDecision
    ts = TrustScore()

    # Use real scorers (no mocks) to verify integration
    report = ts.evaluate(
        alert_id="test-full-001",
        action_type="patch_resources",
        risk_level="medium",
        parameters={"namespace": "production", "deployment_name": "api-server", "new_memory_limit": "1Gi"},
        runbook_name="oomkill-increase-memory",
        namespace="production",
    )

    assert isinstance(report.total_score, float)
    assert 0 <= report.total_score <= 100
    assert report.decision in (TrustDecision.EXECUTE, TrustDecision.DRYRUN_VERIFY, TrustDecision.ESCALATE_HUMAN)
    assert "reversibility" in report.factors
    assert "blast_radius" in report.factors
    assert "runbook_confidence" in report.factors
    assert "history" in report.factors
    assert len(report.reasoning) >= 4


def test_outcome_recording():
    """outcomes.jsonl is appended after action completion."""
    from agents.trust.score import TrustScore, TrustReport, TrustDecision
    tmpdir = tempfile.mkdtemp()
    outcomes_path = os.path.join(tmpdir, "outcomes.jsonl")

    ts = TrustScore()
    report = TrustReport(
        alert_id="test-record-001",
        total_score=95.0,
        decision=TrustDecision.EXECUTE,
        factors={"reversibility": 100, "blast_radius": 100, "runbook_confidence": 90, "history": 85},
        reasoning=["test"],
    )

    with patch("agents.trust.score.OUTCOMES_PATH", outcomes_path):
        ts.record_outcome(
            alert_id="test-record-001",
            trust_report=report,
            success=True,
            action_taken="monitor",
            duration_seconds=5.0,
        )

    assert os.path.exists(outcomes_path)
    with open(outcomes_path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    assert len(records) == 1
    assert records[0]["success"] is True
    assert records[0]["decision"] == "EXECUTE"

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
