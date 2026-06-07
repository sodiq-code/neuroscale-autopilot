# NeuroScale Autopilot — Build Task Tracker

## Progress
- [x] GitHub repo created: https://github.com/sodiq-code/neuroscale-autopilot
- [x] Project structure created
- [x] LICENSE (MIT)
- [x] .gitignore, .env.example, requirements.txt, pyproject.toml
- [x] Detector Agent — full implementation
- [x] Analyzer Agent — Qwen-Max RCA
- [x] Planner Agent — RAG + human-in-loop
- [x] Executor Agent — kubectl/ArgoCD/Kyverno + circuit breaker

## In Progress
- [ ] Escalation Agent (Slack + approval workflow)
- [ ] MCP Server (Qwen MCP tools)
- [ ] Orchestrator (pipeline glue)
- [ ] FastAPI main app + WebSocket events
- [ ] Runbooks JSON files
- [ ] K8s scenarios YAML (inject faults)
- [ ] Alibaba Cloud ECS proof file
- [ ] React Dashboard
- [ ] README
- [ ] Architecture diagram

## Decisions
- Track 4: Autopilot Agent
- Qwen-Max for Analyzer+Executor, Qwen-Embedding for Planner RAG, Qwen-Turbo for Escalation
- MCP server is mandatory for Innovation criterion
- Circuit breaker on Executor prevents loops
- Demo mode fallback when kubectl not installed
