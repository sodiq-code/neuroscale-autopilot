"""
NeuroScale v2 Trust Layer — Verifiable Trust Score Engine

This module implements the core trust scoring algorithm that gates all remediation
actions. Each action receives a composite trust score based on reversibility,
blast radius, runbook confidence, and historical success rate.

The trust score determines execution mode:
- score >= 90: EXECUTE (immediate remediation)
- 70 <= score < 90: DRYRUN_VERIFY (dry-run first, then live if successful)
- score < 70: ESCALATE_HUMAN (wait for human approval, timeout 300s)
"""

from .score import TrustScoreEngine
from .reversibility import ReversibilityAnalyzer
from .blast_radius import BlastRadiusAnalyzer
from .runbook_confidence import RunbookConfidenceAnalyzer
from .history import HistoryAnalyzer

__all__ = [
    "TrustScoreEngine",
    "ReversibilityAnalyzer",
    "BlastRadiusAnalyzer",
    "RunbookConfidenceAnalyzer",
    "HistoryAnalyzer",
]
