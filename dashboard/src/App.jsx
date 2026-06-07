import React, { useState, useEffect, useCallback } from 'react'
import { Activity, AlertTriangle, CheckCircle, Clock, Zap, Shield, DollarSign, RefreshCw, Play, XCircle, ChevronDown, ChevronUp, Cpu, Server } from 'lucide-react'

const API = window.location.origin

const severityColor = {
  critical: '#ef4444',
  warning: '#f59e0b',
  info: '#22c55e',
}

const statusColor = {
  resolved: '#22c55e',
  failed: '#ef4444',
  awaiting_approval: '#f59e0b',
  executing: '#3b82f6',
  analyzing: '#8b5cf6',
  planning: '#06b6d4',
  detecting: '#64748b',
  error: '#ef4444',
}

const typeIcon = {
  oomkill: '💥',
  crashloop: '🔄',
  policy_violation: '🛡️',
  cost_spike: '💰',
  deployment_failure: '⚠️',
}

function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #1e2a3a 0%, #162032 100%)',
      border: `1px solid ${color}33`,
      borderRadius: 12,
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: `${color}22`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={22} color={color} />
      </div>
      <div>
        <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
        {sub && <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}

function IncidentCard({ incident, onApprove }) {
  const [expanded, setExpanded] = useState(false)
  const [approving, setApproving] = useState(false)
  const alert = incident.alert || {}
  const rca = incident.rca || {}
  const plan = incident.plan || {}
  const exec = incident.execution || {}
  const status = incident.status || 'detecting'

  const handleApprove = async (approved) => {
    if (!incident.escalation?.approval_token) return
    setApproving(true)
    try {
      await fetch(`${API}/api/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: incident.escalation.approval_token,
          approved,
          operator: 'dashboard-user',
          reason: approved ? 'Approved via dashboard' : 'Rejected via dashboard',
        })
      })
    } finally {
      setApproving(false)
    }
  }

  return (
    <div style={{
      background: '#111827',
      border: `1px solid ${severityColor[alert.severity] || '#374151'}44`,
      borderLeft: `3px solid ${severityColor[alert.severity] || '#374151'}`,
      borderRadius: 10,
      marginBottom: 12,
      overflow: 'hidden',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ padding: '14px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}
      >
        <span style={{ fontSize: 20 }}>{typeIcon[alert.type] || '⚡'}</span>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{
              fontSize: 12, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
              background: `${statusColor[status]}22`, color: statusColor[status],
              textTransform: 'uppercase', letterSpacing: '0.05em',
            }}>{status.replace('_', ' ')}</span>
            <span style={{
              fontSize: 12, padding: '2px 8px', borderRadius: 4,
              background: `${severityColor[alert.severity]}22`,
              color: severityColor[alert.severity],
            }}>{alert.severity}</span>
            <span style={{ color: '#64748b', fontSize: 12 }}>{alert.namespace} / {alert.resource}</span>
          </div>
          <div style={{ color: '#cbd5e1', fontSize: 14 }}>{alert.message}</div>
        </div>
        <div style={{ color: '#64748b', fontSize: 12, whiteSpace: 'nowrap' }}>
          {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : ''}
        </div>
        {expanded ? <ChevronUp size={16} color="#64748b" /> : <ChevronDown size={16} color="#64748b" />}
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid #1f2937', padding: '16px 18px' }}>
          {rca.root_cause && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: '#8b5cf6', fontSize: 12, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase' }}>
                🧠 Qwen Analysis
              </div>
              <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 12, fontSize: 13, color: '#cbd5e1' }}>
                <strong>Root Cause:</strong> {rca.root_cause}<br />
                <strong>Confidence:</strong> {rca.confidence} | <strong>Risk:</strong> {rca.risk_level} | <strong>Auto-remediate:</strong> {rca.auto_remediate ? 'Yes' : 'No'}
              </div>
              {rca.reasoning_trace && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{ color: '#64748b', fontSize: 12, cursor: 'pointer' }}>Qwen reasoning trace</summary>
                  <div style={{ background: '#0f172a', borderRadius: 6, padding: 10, marginTop: 6, fontSize: 12, color: '#94a3b8', whiteSpace: 'pre-wrap' }}>
                    {rca.reasoning_trace}
                  </div>
                </details>
              )}
            </div>
          )}

          {plan.runbook_name && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: '#06b6d4', fontSize: 12, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase' }}>
                📋 Remediation Plan
              </div>
              <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 12, fontSize: 13, color: '#cbd5e1' }}>
                <strong>Runbook:</strong> {plan.runbook_name}<br />
                <strong>ETA:</strong> {plan.estimated_duration}<br />
                <strong>Rollback:</strong> {plan.rollback_plan}
              </div>
            </div>
          )}

          {exec.action_taken && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: exec.success ? '#22c55e' : '#ef4444', fontSize: 12, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase' }}>
                {exec.success ? '✅ Execution Result' : '❌ Execution Failed'}
              </div>
              <div style={{ background: '#1a1f2e', borderRadius: 8, padding: 12, fontSize: 12, color: '#94a3b8', fontFamily: 'monospace' }}>
                {exec.output || exec.error || 'No output'}
                {exec.duration_seconds && <div style={{ marginTop: 6, color: '#64748b' }}>Duration: {exec.duration_seconds.toFixed(2)}s</div>}
              </div>
            </div>
          )}

          {status === 'awaiting_approval' && incident.escalation?.approval_token && (
            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              <button
                onClick={() => handleApprove(true)}
                disabled={approving}
                style={{
                  background: '#22c55e', color: 'white', border: 'none', borderRadius: 8,
                  padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 14,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <CheckCircle size={16} /> Approve Remediation
              </button>
              <button
                onClick={() => handleApprove(false)}
                disabled={approving}
                style={{
                  background: '#ef4444', color: 'white', border: 'none', borderRadius: 8,
                  padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 14,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <XCircle size={16} /> Reject
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [stats, setStats] = useState({})
  const [simulating, setSimulating] = useState(false)
  const [selectedScenario, setSelectedScenario] = useState('oomkill')
  const [connected, setConnected] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [incRes, statsRes] = await Promise.all([
        fetch(`${API}/api/incidents`),
        fetch(`${API}/api/stats`),
      ])
      const incData = await incRes.json()
      const statsData = await statsRes.json()
      setIncidents(incData.incidents || [])
      setStats(statsData)
    } catch (e) {
      console.error('Fetch error:', e)
    }
  }, [])

  useEffect(() => {
    fetchData()

    // WebSocket for live updates
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
    let ws
    const connect = () => {
      ws = new WebSocket(wsUrl)
      ws.onopen = () => setConnected(true)
      ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.incidents) setIncidents(data.incidents)
      }
    }
    connect()
    const interval = setInterval(fetchData, 10000)
    return () => { ws?.close(); clearInterval(interval) }
  }, [fetchData])

  const simulate = async () => {
    setSimulating(true)
    try {
      await fetch(`${API}/api/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: selectedScenario }),
      })
      await fetchData()
    } finally {
      setSimulating(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e1a' }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%)',
        borderBottom: '1px solid #1e2a3a',
        padding: '16px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Zap size={20} color="white" />
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>NeuroScale Autopilot</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>Self-healing K8s • Powered by Qwen AI</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
            boxShadow: `0 0 6px ${connected ? '#22c55e' : '#ef4444'}`,
          }} />
          <span style={{ color: '#64748b', fontSize: 13 }}>{connected ? 'Live' : 'Reconnecting'}</span>
          <button onClick={fetchData} style={{
            background: 'transparent', border: '1px solid #374151',
            color: '#94a3b8', padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
          }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '28px 32px' }}>
        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
          <StatCard icon={Activity} label="Total Incidents" value={stats.total || 0} color="#3b82f6" />
          <StatCard icon={CheckCircle} label="Auto-Resolved" value={stats.resolved || 0} color="#22c55e" sub={`${stats.auto_remediation_rate || 0}% auto rate`} />
          <StatCard icon={Clock} label="Avg Resolution" value={`${stats.avg_resolution_seconds || 0}s`} color="#8b5cf6" />
          <StatCard icon={AlertTriangle} label="Pending Approval" value={stats.pending_approval || 0} color="#f59e0b" />
          <StatCard icon={XCircle} label="Failed" value={stats.failed || 0} color="#ef4444" />
        </div>

        {/* Simulate Panel */}
        <div style={{
          background: 'linear-gradient(135deg, #1e1b4b 0%, #1a2744 100%)',
          border: '1px solid #3730a3',
          borderRadius: 12, padding: '20px 24px', marginBottom: 28,
          display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>
              🎮 Demo Simulator
            </div>
            <div style={{ fontSize: 13, color: '#94a3b8' }}>
              Inject a scenario to see the 5-agent pipeline in action
            </div>
          </div>
          <select
            value={selectedScenario}
            onChange={e => setSelectedScenario(e.target.value)}
            style={{
              background: '#0f172a', border: '1px solid #374151', color: '#e2e8f0',
              padding: '10px 14px', borderRadius: 8, fontSize: 14, cursor: 'pointer',
            }}
          >
            <option value="oomkill">💥 OOMKill — Pod memory exceeded</option>
            <option value="crashloop">🔄 CrashLoop — Container crashing</option>
            <option value="policy_violation">🛡️ Policy Violation — Kyverno block</option>
            <option value="cost_spike">💰 Cost Spike — Budget exceeded</option>
          </select>
          <button
            onClick={simulate}
            disabled={simulating}
            style={{
              background: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
              color: 'white', border: 'none', borderRadius: 8,
              padding: '10px 24px', cursor: simulating ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8,
              opacity: simulating ? 0.7 : 1,
            }}
          >
            <Play size={16} /> {simulating ? 'Running...' : 'Simulate Incident'}
          </button>
        </div>

        {/* Agent Pipeline Status */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ color: '#94a3b8', fontSize: 14, fontWeight: 600, marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            5-Agent Pipeline
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap' }}>
            {[
              { name: 'Detector', icon: Server, color: '#64748b', desc: 'K8s Monitor' },
              { name: 'Analyzer', icon: Cpu, color: '#8b5cf6', desc: 'Qwen-Max RCA' },
              { name: 'Planner', icon: Activity, color: '#06b6d4', desc: 'RAG Runbook' },
              { name: 'Executor', icon: Zap, color: '#3b82f6', desc: 'kubectl/ArgoCD' },
              { name: 'Escalation', icon: Shield, color: '#22c55e', desc: 'Human-in-Loop' },
            ].map((agent, i) => (
              <React.Fragment key={agent.name}>
                <div style={{
                  background: '#111827', border: `1px solid ${agent.color}44`,
                  borderRadius: 10, padding: '12px 16px', textAlign: 'center', minWidth: 110,
                }}>
                  <agent.icon size={20} color={agent.color} style={{ marginBottom: 6 }} />
                  <div style={{ color: agent.color, fontSize: 13, fontWeight: 600 }}>{agent.name}</div>
                  <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{agent.desc}</div>
                </div>
                {i < 4 && (
                  <div style={{ padding: '0 6px', color: '#374151', fontSize: 20, fontWeight: 300 }}>→</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Incidents List */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ color: '#94a3b8', fontSize: 14, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Incident Log
            </div>
            <div style={{ color: '#64748b', fontSize: 13 }}>{incidents.length} incidents</div>
          </div>

          {incidents.length === 0 ? (
            <div style={{
              background: '#111827', border: '1px solid #1f2937', borderRadius: 10,
              padding: '48px', textAlign: 'center', color: '#4b5563',
            }}>
              <Activity size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
              <div style={{ fontSize: 16, marginBottom: 8 }}>No incidents yet</div>
              <div style={{ fontSize: 14 }}>Use the simulator above to trigger a demo incident</div>
            </div>
          ) : (
            incidents.map((inc, i) => (
              <IncidentCard key={inc.alert?.id || i} incident={inc} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
