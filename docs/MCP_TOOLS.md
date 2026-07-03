# NeuroScale v2 MCP Tools — Complete Reference

## Overview

NeuroScale v2 exposes **18 Model Context Protocol (MCP) tools** that enable external AI clients (Claude, Qwen, etc.) to interact with the autonomous remediation system. These tools provide full visibility into cluster state, incident management, and remediation capabilities.

## Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| **Cluster Monitoring** | 1-4 | Real-time cluster state and alerts |
| **Remediation Control** | 5-8 | Trigger and manage remediations |
| **Trust & Safety** | 9-11 | Trust scoring and safety verification |
| **Knowledge & History** | 12-15 | Runbooks, incident history, topology |
| **Cost & Prediction** | 16-18 | Cost analysis and failure prediction |

## Existing Tools (1-8)

### 1. get_cluster_status

**Purpose:** Get current health summary of the cluster

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "namespace": {
      "type": "string",
      "description": "Kubernetes namespace (optional, default: all)"
    }
  }
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "cluster_name": {"type": "string"},
    "nodes_total": {"type": "integer"},
    "nodes_ready": {"type": "integer"},
    "pods_total": {"type": "integer"},
    "pods_running": {"type": "integer"},
    "pods_pending": {"type": "integer"},
    "pods_failed": {"type": "integer"},
    "active_alerts": {"type": "integer"},
    "timestamp": {"type": "string"}
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/mcp/tools/get_cluster_status \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default"}'
```

### 2. list_active_alerts

**Purpose:** Get all active alerts with severity and age

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "severity": {
      "type": "string",
      "enum": ["info", "warning", "critical"],
      "description": "Filter by severity (optional)"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of alerts (default: 50)"
    }
  }
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "alerts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "alert_id": {"type": "string"},
          "type": {"type": "string"},
          "severity": {"type": "string"},
          "message": {"type": "string"},
          "age_seconds": {"type": "integer"},
          "resource": {"type": "string"}
        }
      }
    },
    "total": {"type": "integer"}
  }
}
```

### 3. get_alert_detail

**Purpose:** Get full detail for a specific alert

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID"
    }
  },
  "required": ["alert_id"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {"type": "string"},
    "type": {"type": "string"},
    "severity": {"type": "string"},
    "message": {"type": "string"},
    "resource": {"type": "string"},
    "namespace": {"type": "string"},
    "timestamp": {"type": "string"},
    "metrics": {"type": "object"},
    "rca": {"type": "string"},
    "remediation_plan": {"type": "object"}
  }
}
```

### 4. trigger_remediation

**Purpose:** Manually trigger remediation for an alert

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID to remediate"
    },
    "force": {
      "type": "boolean",
      "description": "Force execution even if trust score is low (default: false)"
    }
  },
  "required": ["alert_id"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "remediation_id": {"type": "string"},
    "alert_id": {"type": "string"},
    "status": {"type": "string"},
    "execution_mode": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 5. get_remediation_status

**Purpose:** Get status of a running remediation job

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "remediation_id": {
      "type": "string",
      "description": "Remediation job ID"
    }
  },
  "required": ["remediation_id"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "remediation_id": {"type": "string"},
    "status": {"type": "string", "enum": ["pending", "running", "success", "failed"]},
    "progress": {"type": "number", "minimum": 0, "maximum": 100},
    "steps_completed": {"type": "integer"},
    "steps_total": {"type": "integer"},
    "duration_seconds": {"type": "number"},
    "error": {"type": "string"}
  }
}
```

### 6. approve_action

**Purpose:** Submit human approval for a pending remediation

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "token": {
      "type": "string",
      "description": "Approval token"
    },
    "approved": {
      "type": "boolean",
      "description": "Approval decision"
    },
    "operator": {
      "type": "string",
      "description": "Operator name"
    },
    "reason": {
      "type": "string",
      "description": "Reason for decision (optional)"
    }
  },
  "required": ["token", "approved", "operator"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "success": {"type": "boolean"},
    "approved": {"type": "boolean"},
    "token": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 7. get_runbook

**Purpose:** Retrieve runbook content by name

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "runbook_name": {
      "type": "string",
      "description": "Name of the runbook"
    }
  },
  "required": ["runbook_name"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "description": {"type": "string"},
    "steps": {"type": "array", "items": {"type": "string"}},
    "parameters": {"type": "object"},
    "validation": {"type": "object"},
    "rollback_plan": {"type": "string"}
  }
}
```

### 8. get_metrics_summary

**Purpose:** Get raw metric summary for a namespace

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "namespace": {
      "type": "string",
      "description": "Kubernetes namespace"
    },
    "metric": {
      "type": "string",
      "description": "Metric name (optional)"
    }
  },
  "required": ["namespace"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "namespace": {"type": "string"},
    "cpu_usage": {"type": "number"},
    "memory_usage": {"type": "number"},
    "disk_usage": {"type": "number"},
    "network_in": {"type": "number"},
    "network_out": {"type": "number"},
    "timestamp": {"type": "string"}
  }
}
```

## New Tools (9-18)

### 9. get_trust_score

**Purpose:** Get the trust score for a remediation action

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID"
    },
    "action_id": {
      "type": "string",
      "description": "Action ID"
    },
    "action_type": {
      "type": "string",
      "description": "Type of action (e.g., scale_down, rollback)"
    },
    "target_resource": {
      "type": "object",
      "description": "Resource being affected"
    },
    "remediation_plan": {
      "type": "object",
      "description": "Planned remediation"
    }
  },
  "required": ["alert_id", "action_id", "action_type", "target_resource", "remediation_plan"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "final_score": {"type": "number", "minimum": 0, "maximum": 100},
    "execution_mode": {"type": "string", "enum": ["execute", "dryrun_verify", "escalate_human"]},
    "reversibility_score": {"type": "number"},
    "blast_radius_score": {"type": "number"},
    "runbook_confidence_score": {"type": "number"},
    "history_score": {"type": "number"},
    "reasoning": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 10. explain_reasoning

**Purpose:** Get Qwen3-Max thinking chain for an incident

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID"
    },
    "include_thinking": {
      "type": "boolean",
      "description": "Include full thinking trace (default: true)"
    }
  },
  "required": ["alert_id"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {"type": "string"},
    "thinking": {"type": "string"},
    "rca": {"type": "string"},
    "confidence": {"type": "number"},
    "model": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 11. simulate_remediation

**Purpose:** Dry-run an action plan without executing

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID"
    },
    "action_id": {
      "type": "string",
      "description": "Action ID"
    },
    "remediation_plan": {
      "type": "object",
      "description": "Plan to simulate"
    }
  },
  "required": ["alert_id", "action_id", "remediation_plan"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "simulation_id": {"type": "string"},
    "status": {"type": "string", "enum": ["success", "failed"]},
    "output": {"type": "string"},
    "duration_seconds": {"type": "number"},
    "would_succeed": {"type": "boolean"}
  }
}
```

### 12. get_cluster_topology

**Purpose:** Get cluster graph JSON for analysis

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "format": {
      "type": "string",
      "enum": ["json", "dot", "mermaid"],
      "description": "Output format (default: json)"
    }
  }
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "type": {"type": "string"},
          "name": {"type": "string"},
          "status": {"type": "string"}
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "source": {"type": "string"},
          "target": {"type": "string"},
          "relationship": {"type": "string"}
        }
      }
    }
  }
}
```

### 13. query_cost_impact

**Purpose:** Predict cost impact of an action via OpenCost

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "action_type": {
      "type": "string",
      "description": "Type of action"
    },
    "target_resource": {
      "type": "object",
      "description": "Resource being affected"
    },
    "duration_hours": {
      "type": "number",
      "description": "Expected duration of impact (default: 1)"
    }
  },
  "required": ["action_type", "target_resource"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "action_type": {"type": "string"},
    "current_cost_per_hour": {"type": "number"},
    "projected_cost_per_hour": {"type": "number"},
    "cost_delta": {"type": "number"},
    "savings_percentage": {"type": "number"},
    "roi": {"type": "string"}
  }
}
```

### 14. search_runbooks

**Purpose:** Semantic search over RAG corpus

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (default: 5)"
    },
    "min_score": {
      "type": "number",
      "description": "Minimum similarity score (0-1, default: 0.5)"
    }
  },
  "required": ["query"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "runbook_name": {"type": "string"},
          "similarity_score": {"type": "number"},
          "description": {"type": "string"}
        }
      }
    },
    "total": {"type": "integer"}
  }
}
```

### 15. get_incident_history

**Purpose:** Query past incidents by pattern

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "pattern": {
      "type": "string",
      "description": "Incident pattern (e.g., oomkill, crashloop)"
    },
    "days": {
      "type": "integer",
      "description": "Number of days to look back (default: 7)"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results (default: 20)"
    }
  },
  "required": ["pattern"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "incidents": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "incident_id": {"type": "string"},
          "pattern": {"type": "string"},
          "timestamp": {"type": "string"},
          "resolution_time_seconds": {"type": "number"},
          "remediation_used": {"type": "string"},
          "success": {"type": "boolean"}
        }
      }
    },
    "total": {"type": "integer"},
    "success_rate": {"type": "number"}
  }
}
```

### 16. rollback_last_action

**Purpose:** Safety mechanism to rollback the last executed action

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "alert_id": {
      "type": "string",
      "description": "Alert ID"
    },
    "force": {
      "type": "boolean",
      "description": "Force rollback (default: false)"
    }
  },
  "required": ["alert_id"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "rollback_id": {"type": "string"},
    "status": {"type": "string", "enum": ["success", "failed"]},
    "original_action": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 17. predict_failure

**Purpose:** Proactive failure prediction using ML

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "namespace": {
      "type": "string",
      "description": "Kubernetes namespace"
    },
    "lookahead_hours": {
      "type": "number",
      "description": "Hours to look ahead (default: 1)"
    }
  },
  "required": ["namespace"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "predictions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "failure_type": {"type": "string"},
          "probability": {"type": "number"},
          "resource": {"type": "string"},
          "recommended_action": {"type": "string"}
        }
      }
    },
    "timestamp": {"type": "string"}
  }
}
```

### 18. approve_action

**Purpose:** Human-in-the-loop approval endpoint (enhanced version of tool 6)

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "token": {
      "type": "string",
      "description": "Approval token"
    },
    "approved": {
      "type": "boolean",
      "description": "Approval decision"
    },
    "operator": {
      "type": "string",
      "description": "Operator name"
    },
    "reason": {
      "type": "string",
      "description": "Reason for decision"
    },
    "conditions": {
      "type": "object",
      "description": "Approval conditions (optional)"
    }
  },
  "required": ["token", "approved", "operator"]
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "success": {"type": "boolean"},
    "approved": {"type": "boolean"},
    "token": {"type": "string"},
    "execution_started": {"type": "boolean"},
    "timestamp": {"type": "string"}
  }
}
```

## Usage Examples

### Example 1: Get Trust Score for Scale-Down

```bash
curl -X POST http://localhost:8000/mcp/tools/get_trust_score \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "alert-001",
    "action_id": "action-001",
    "action_type": "scale_down",
    "target_resource": {
      "kind": "Deployment",
      "name": "api-server",
      "namespace": "default"
    },
    "remediation_plan": {
      "runbook_found": true,
      "retrieval_score": 0.85,
      "steps": ["scale-down"],
      "rollback_plan": true
    }
  }'
```

**Response:**
```json
{
  "final_score": 78.5,
  "execution_mode": "dryrun_verify",
  "reversibility_score": 90.0,
  "blast_radius_score": 85.0,
  "runbook_confidence_score": 80.0,
  "history_score": 75.0,
  "reasoning": "Trust score 78.5 in range [70, 90). Dry-run first, then live if successful.",
  "timestamp": "2026-07-03T22:30:00Z"
}
```

### Example 2: Search Runbooks

```bash
curl -X POST http://localhost:8000/mcp/tools/search_runbooks \
  -H "Content-Type: application/json" \
  -d '{
    "query": "scale down deployment due to high memory",
    "limit": 5,
    "min_score": 0.7
  }'
```

### Example 3: Get Incident History

```bash
curl -X POST http://localhost:8000/mcp/tools/get_incident_history \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": "oomkill",
    "days": 7,
    "limit": 10
  }'
```

## Testing MCP Tools

### Test with Claude Desktop

1. Add NeuroScale to Claude Desktop config:

```json
{
  "mcpServers": {
    "neuroscale": {
      "command": "python",
      "args": ["/path/to/mcp_server/server.py"]
    }
  }
}
```

2. Restart Claude Desktop
3. Use tools in conversations

### Test with Qwen Code CLI

```bash
qwen-cli --mcp neuroscale --tool get_cluster_status
```

### Test with curl

```bash
curl -X POST http://localhost:8000/mcp/tools/{tool_name} \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Error Handling

All tools follow consistent error handling:

```json
{
  "error": "Tool execution failed",
  "error_code": "INVALID_PARAMETER",
  "message": "alert_id is required",
  "timestamp": "2026-07-03T22:30:00Z"
}
```

## Rate Limiting

- Default: 100 requests per minute per client
- Burst: 20 requests per second
- Configurable via environment variables

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [NeuroScale Architecture](./ARCHITECTURE.md)
- [Trust Layer](./TRUST_LAYER.md)
