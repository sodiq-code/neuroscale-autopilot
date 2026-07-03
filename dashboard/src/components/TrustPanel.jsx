/**
 * NeuroScale v2 Trust Layer Panel
 * 
 * React component for visualizing the trust score and execution mode decision.
 * Displays:
 * - Final trust score (0-100)
 * - Execution mode (EXECUTE, DRYRUN_VERIFY, ESCALATE_HUMAN)
 * - Sub-scores breakdown (reversibility, blast radius, runbook confidence, history)
 * - Decision reasoning
 * - Audit trail link
 */

import React, { useState, useEffect } from 'react';
import './TrustPanel.css';

const TrustPanel = ({ 
  finalScore, 
  executionMode, 
  subScores, 
  reasoning,
  actionId,
  alertId,
  timestamp 
}) => {
  const [expanded, setExpanded] = useState(false);

  // Determine color based on score
  const getScoreColor = (score) => {
    if (score >= 90) return '#10b981'; // green (EXECUTE)
    if (score >= 70) return '#f59e0b'; // amber (DRYRUN_VERIFY)
    return '#ef4444'; // red (ESCALATE_HUMAN)
  };

  // Determine execution mode label
  const getModeLabel = (mode) => {
    switch (mode) {
      case 'execute':
        return '⚡ EXECUTE';
      case 'dryrun_verify':
        return '🔍 DRYRUN_VERIFY';
      case 'escalate_human':
        return '👤 ESCALATE_HUMAN';
      default:
        return 'UNKNOWN';
    }
  };

  // Determine mode description
  const getModeDescription = (mode) => {
    switch (mode) {
      case 'execute':
        return 'Execute remediation immediately without dry-run';
      case 'dryrun_verify':
        return 'Perform dry-run first, then execute if successful';
      case 'escalate_human':
        return 'Wait for human approval (timeout 300s)';
      default:
        return 'Unknown execution mode';
    }
  };

  // Render sub-score bar
  const renderScoreBar = (label, score) => (
    <div key={label} className="score-bar-container">
      <div className="score-label">{label}</div>
      <div className="score-bar">
        <div
          className="score-fill"
          style={{
            width: `${score}%`,
            backgroundColor: getScoreColor(score),
          }}
        />
      </div>
      <div className="score-value">{score.toFixed(1)}</div>
    </div>
  );

  return (
    <div className="trust-panel">
      {/* Header */}
      <div className="trust-header">
        <h2>Trust Layer Analysis</h2>
        <button
          className="expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '▼' : '▶'}
        </button>
      </div>

      {/* Main Score Display */}
      <div className="score-display">
        <div className="score-circle" style={{ borderColor: getScoreColor(finalScore) }}>
          <div className="score-number">{finalScore.toFixed(1)}</div>
          <div className="score-label-small">Trust Score</div>
        </div>

        <div className="mode-info">
          <div className="mode-label" style={{ color: getScoreColor(finalScore) }}>
            {getModeLabel(executionMode)}
          </div>
          <div className="mode-description">
            {getModeDescription(executionMode)}
          </div>
        </div>
      </div>

      {/* Reasoning */}
      <div className="reasoning-box">
        <strong>Reasoning:</strong>
        <p>{reasoning}</p>
      </div>

      {/* Expandable Details */}
      {expanded && (
        <div className="trust-details">
          {/* Sub-Scores */}
          <div className="sub-scores-section">
            <h3>Sub-Score Breakdown</h3>
            <div className="sub-scores">
              {subScores && (
                <>
                  {renderScoreBar('Reversibility (30%)', subScores.reversibility_score)}
                  {renderScoreBar('Blast Radius (25%)', subScores.blast_radius_score)}
                  {renderScoreBar('Runbook Confidence (25%)', subScores.runbook_confidence_score)}
                  {renderScoreBar('History (20%)', subScores.history_score)}
                </>
              )}
            </div>
          </div>

          {/* Metadata */}
          <div className="metadata-section">
            <h3>Metadata</h3>
            <table className="metadata-table">
              <tbody>
                <tr>
                  <td><strong>Action ID:</strong></td>
                  <td><code>{actionId}</code></td>
                </tr>
                <tr>
                  <td><strong>Alert ID:</strong></td>
                  <td><code>{alertId}</code></td>
                </tr>
                <tr>
                  <td><strong>Timestamp:</strong></td>
                  <td>{new Date(timestamp).toLocaleString()}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Audit Trail Link */}
          <div className="audit-section">
            <a href={`/audit/${actionId}`} className="audit-link">
              📋 View Audit Trail
            </a>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="trust-footer">
        <div className="threshold-info">
          <span className="threshold">≥90: EXECUTE</span>
          <span className="threshold">70-89: DRYRUN_VERIFY</span>
          <span className="threshold">&lt;70: ESCALATE_HUMAN</span>
        </div>
      </div>
    </div>
  );
};

export default TrustPanel;
