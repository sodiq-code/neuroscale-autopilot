# NeuroScale Autopilot v2 Deployment Checklist

Use this before Devpost submission.

## Security

- [ ] Revoke old GitHub PAT and DashScope keys.
- [ ] Confirm `.env` is ignored.
- [ ] Confirm no secrets appear in README/docs/screenshots.
- [ ] Store Qwen key in Kubernetes Secret, not values.yaml.

## Local QA

```bash
pytest tests/ -v
python benchmarks/run_benchmarks.py --runs 1 --dry-run
docker-compose up --build
```

## ACK Deployment

```bash
kubectl create namespace neuroscale-autopilot
kubectl create secret generic neuroscale-qwen \
  --from-literal=api-key="$QWEN_API_KEY" \
  -n neuroscale-autopilot
helm install neuroscale charts/neuroscale -n neuroscale-autopilot
kubectl get pods -n neuroscale-autopilot
```

## Proof for Devpost

- [ ] ACK console screenshot.
- [ ] `kubectl get pods -n neuroscale-autopilot` screenshot.
- [ ] Dashboard screenshot.
- [ ] DashScope/Qwen API call visible in logs.
- [ ] Link to `alibaba_cloud/` and `charts/neuroscale/`.

## Demo

- [ ] Public YouTube URL.
- [ ] Under 3 minutes.
- [ ] Shows live chaos injection, Qwen thinking, Trust Score, remediation, MCP tools.
