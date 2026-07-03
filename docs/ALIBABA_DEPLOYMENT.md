# NeuroScale Autopilot v2 — Alibaba Cloud ACK Deployment Guide

## Overview

This guide walks through deploying NeuroScale Autopilot v2 to Alibaba Cloud Container Service for Kubernetes (ACK).

**Deployment Target:**
- **Region:** ap-southeast-1 (Singapore)
- **Cluster Type:** Managed Kubernetes (ACK)
- **Networking:** VPC with NAT Gateway
- **Storage:** Alibaba Cloud NAS
- **Monitoring:** ACK Monitoring + Prometheus

## Prerequisites

### Alibaba Cloud Account

1. Create Alibaba Cloud account at https://www.alibabacloud.com
2. Enable Container Service for Kubernetes (ACK)
3. Create API credentials (AccessKey + SecretKey)

### Local Tools

```bash
# Install Alibaba Cloud CLI
brew install aliyun-cli  # macOS
# or
apt-get install aliyun-cli  # Linux

# Configure credentials
aliyun configure

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## Step 1: Create ACK Cluster (10 minutes)

### Via Alibaba Cloud Console

1. Go to https://cs.console.aliyun.com
2. Click **Create Kubernetes Cluster**
3. Configure:
   - **Cluster Name:** neuroscale-autopilot
   - **Region:** ap-southeast-1 (Singapore)
   - **Kubernetes Version:** 1.28+
   - **Node Type:** ECS (Elastic Compute Service)
   - **Node Count:** 3 nodes
   - **Node Spec:** 2 vCPU, 4 GB RAM (ecs.t6-c1m2.large)
   - **Network:** VPC (create new or use existing)
   - **NAT Gateway:** Enable

4. Click **Create**
5. Wait for cluster to be ready (5-10 minutes)

### Via Alibaba CLI

```bash
aliyun cs CreateCluster \
  --ClusterName neuroscale-autopilot \
  --RegionId ap-southeast-1 \
  --ZoneId ap-southeast-1a \
  --NodeType ecs.t6-c1m2.large \
  --NumOfNodes 3 \
  --MasterSystemDiskSize 40 \
  --MasterSystemDiskCategory cloud_ssd
```

## Step 2: Download Kubeconfig

### Via Console

1. Go to https://cs.console.aliyun.com
2. Click your cluster name
3. Click **Connection Information**
4. Copy **Public Kubeconfig**
5. Save to `~/.kube/config-ack`

### Via CLI

```bash
aliyun cs DescribeClusterUserKubeconfig \
  --ClusterId <cluster-id> \
  > ~/.kube/config-ack

# Set as active config
export KUBECONFIG=~/.kube/config-ack
```

## Step 3: Verify Cluster Connection

```bash
# Test connection
kubectl cluster-info

# List nodes
kubectl get nodes

# Expected output:
# NAME                        STATUS   ROLES    AGE   VERSION
# cn-singapore.192.168.1.1    Ready    master   5m    v1.28.0
# cn-singapore.192.168.1.2    Ready    <none>   5m    v1.28.0
# cn-singapore.192.168.1.3    Ready    <none>   5m    v1.28.0
```

## Step 4: Create Namespace & Storage

### Create Namespace

```bash
kubectl create namespace neuroscale-autopilot
kubectl label namespace neuroscale-autopilot app=neuroscale
```

### Create Storage Class (NAS)

```bash
# Create Alibaba Cloud NAS
aliyun nas CreateFileSystem \
  --RegionId ap-southeast-1 \
  --ProtocolType NFS \
  --StorageType Capacity

# Create mount target
aliyun nas CreateMountTarget \
  --FileSystemId <fs-id> \
  --NetworkType Vpc \
  --VpcId <vpc-id> \
  --VSwitchId <vswitch-id>

# Create PersistentVolume
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: neuroscale-nas
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: <nas-mount-target>
    path: /neuroscale
EOF

# Create PersistentVolumeClaim
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: neuroscale-pvc
  namespace: neuroscale-autopilot
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  volumeName: neuroscale-nas
EOF
```

## Step 5: Configure Secrets

### Create Qwen API Secret

```bash
kubectl create secret generic qwen-credentials \
  --from-literal=api-key=$QWEN_API_KEY \
  --from-literal=base-url=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
  -n neuroscale-autopilot
```

### Create Alibaba Cloud Credentials Secret

```bash
kubectl create secret generic alibaba-credentials \
  --from-literal=access-key=$ALIBABA_ACCESS_KEY \
  --from-literal=secret-key=$ALIBABA_SECRET_KEY \
  --from-literal=region=ap-southeast-1 \
  -n neuroscale-autopilot
```

## Step 6: Deploy NeuroScale via Helm

### Add Helm Repository (Optional)

```bash
# If hosting chart in Alibaba Cloud Container Registry
helm repo add neuroscale https://registry.cn-singapore.aliyuncs.com/neuroscale/charts
helm repo update
```

### Deploy Chart

```bash
# From local chart
helm install neuroscale ./charts/neuroscale/ \
  --namespace neuroscale-autopilot \
  --set qwen.apiKey=$QWEN_API_KEY \
  --set alibaba.region=ap-southeast-1 \
  --set storage.enabled=true \
  --set storage.size=50Gi \
  --set ingress.enabled=true \
  --set ingress.className=aliyun-slb \
  --set ingress.host=neuroscale.example.com

# Verify deployment
kubectl get pods -n neuroscale-autopilot
kubectl get svc -n neuroscale-autopilot
```

## Step 7: Configure Ingress (Load Balancer)

### Create Ingress with SLB

```bash
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: neuroscale-ingress
  namespace: neuroscale-autopilot
  annotations:
    kubernetes.io/ingress.class: "aliyun-slb"
    aliyun.ingress.kubernetes.io/slb-id: "slb-xxx"
spec:
  rules:
  - host: neuroscale.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: neuroscale-dashboard
            port:
              number: 3000
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: neuroscale-api
            port:
              number: 8000
      - path: /mcp
        pathType: Prefix
        backend:
          service:
            name: neuroscale-mcp
            port:
              number: 8001
EOF

# Get SLB IP
kubectl get ingress -n neuroscale-autopilot
```

### Configure DNS

1. Go to Alibaba Cloud DNS console
2. Add A record:
   - **Domain:** neuroscale.example.com
   - **Type:** A
   - **Value:** <SLB-IP>
   - **TTL:** 600

## Step 8: Verify Deployment

### Check Pod Status

```bash
# All pods should be Running
kubectl get pods -n neuroscale-autopilot

# Expected output:
# NAME                                    READY   STATUS    RESTARTS   AGE
# neuroscale-analyzer-abc123              1/1     Running   0          2m
# neuroscale-planner-def456               1/1     Running   0          2m
# neuroscale-executor-ghi789              1/1     Running   0          2m
# neuroscale-mcp-server-jkl012            1/1     Running   0          2m
# neuroscale-dashboard-mno345             1/1     Running   0          2m
```

### Check Services

```bash
kubectl get svc -n neuroscale-autopilot

# Expected output:
# NAME                    TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
# neuroscale-api          ClusterIP      10.0.1.100      <none>        8000/TCP
# neuroscale-mcp          ClusterIP      10.0.1.101      <none>        8001/TCP
# neuroscale-dashboard    LoadBalancer   10.0.1.102      <SLB-IP>      3000:30000/TCP
```

### Test API Endpoint

```bash
# Get SLB IP
SLB_IP=$(kubectl get svc neuroscale-dashboard -n neuroscale-autopilot -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test health endpoint
curl http://$SLB_IP:8000/health

# Expected response:
# {"status": "healthy", "version": "v2.0.0"}
```

### Access Dashboard

```bash
# Via browser
open http://neuroscale.example.com

# Or use port-forward for testing
kubectl port-forward -n neuroscale-autopilot svc/neuroscale-dashboard 3000:3000
# Then open http://localhost:3000
```

## Step 9: Configure Monitoring

### Enable ACK Monitoring

1. Go to ACK cluster details
2. Click **Monitoring**
3. Enable **Prometheus**
4. Enable **Grafana**

### Deploy Prometheus ServiceMonitor

```bash
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: neuroscale
  namespace: neuroscale-autopilot
spec:
  selector:
    matchLabels:
      app: neuroscale
  endpoints:
  - port: metrics
    interval: 30s
EOF
```

### Create Grafana Dashboard

1. Go to Grafana (via ACK console)
2. Add Prometheus data source
3. Import dashboard from `charts/neuroscale/grafana-dashboard.json`

## Step 10: Verify Live Deployment

### Run Chaos Injection

```bash
# Get API endpoint
API_ENDPOINT=$(kubectl get svc neuroscale-api -n neuroscale-autopilot -o jsonpath='{.status.loadBalancer.ingress[0].ip}'):8000

# Inject OOMKilled scenario
curl -X POST http://$API_ENDPOINT/chaos/inject/oomkilled \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "pod_name": "test-pod"}'

# Watch remediation in dashboard
open http://neuroscale.example.com
```

### Check Outcomes Log

```bash
# Access NAS and view outcomes
kubectl exec -it -n neuroscale-autopilot <pod-name> -- bash
tail -f /mnt/nas/outcomes.jsonl
```

## Production Checklist

- [ ] Cluster created in ap-southeast-1
- [ ] 3+ nodes provisioned
- [ ] NAS storage configured
- [ ] Qwen API credentials set
- [ ] Helm chart deployed
- [ ] Ingress configured with SLB
- [ ] DNS records updated
- [ ] Monitoring enabled
- [ ] Dashboard accessible
- [ ] Chaos injection tested
- [ ] Outcomes logging verified
- [ ] Backup strategy in place
- [ ] Security policies applied

## Scaling & Performance

### Horizontal Scaling

```bash
# Scale analyzer pods
kubectl scale deployment neuroscale-analyzer \
  --replicas=3 \
  -n neuroscale-autopilot

# Scale executor pods
kubectl scale deployment neuroscale-executor \
  --replicas=5 \
  -n neuroscale-autopilot
```

### Resource Limits

```bash
# Update resource requests/limits
kubectl set resources deployment neuroscale-analyzer \
  --requests=cpu=500m,memory=512Mi \
  --limits=cpu=1000m,memory=1Gi \
  -n neuroscale-autopilot
```

## Troubleshooting

### Pods not starting

```bash
# Check pod logs
kubectl logs -n neuroscale-autopilot <pod-name>

# Check events
kubectl describe pod -n neuroscale-autopilot <pod-name>

# Check resource availability
kubectl top nodes
kubectl top pods -n neuroscale-autopilot
```

### API not responding

```bash
# Check service endpoints
kubectl get endpoints -n neuroscale-autopilot

# Test connectivity
kubectl exec -it -n neuroscale-autopilot <pod-name> -- \
  curl http://neuroscale-api:8000/health
```

### NAS mount issues

```bash
# Check PVC status
kubectl get pvc -n neuroscale-autopilot

# Check PV status
kubectl get pv

# Verify mount in pod
kubectl exec -it -n neuroscale-autopilot <pod-name> -- \
  df -h /mnt/nas
```

## Cost Optimization

| Component | Monthly Cost |
|-----------|--------------|
| ACK Cluster (3 nodes) | ~$150 |
| NAS Storage (100GB) | ~$20 |
| SLB (Load Balancer) | ~$15 |
| Qwen API (1000 incidents) | ~$50 |
| **Total** | **~$235** |

**Savings vs manual SRE:** $500-2000/month

## Next Steps

1. **Integrate with Prometheus** — Connect your existing AlertManager
2. **Configure Runbooks** — Add your custom remediation procedures
3. **Tune Trust Weights** — Customize for your SLOs
4. **Monitor Costs** — Track API usage and optimize
5. **Plan Upgrades** — Schedule regular updates

---

**Deployment Guide Version:** v2.0.0  
**Last Updated:** 2026-07-04  
**Region:** ap-southeast-1 (Singapore)  
**Status:** Production Ready

**Your NeuroScale Autopilot v2 is now live on Alibaba Cloud ACK! 🚀**
