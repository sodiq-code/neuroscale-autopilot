"""
Detector Agent — Continuously monitors Kubernetes cluster for anomalies.
Watches: Pod health, OOMKills, CrashLoops, Kyverno policy violations, OpenCost budget alerts.
Fires structured alerts to the Analyzer Agent.
"""

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Callable, Optional
from kubernetes import client, config as k8s_config, watch
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class Alert(BaseModel):
    id: str
    timestamp: str
    severity: str  # critical | warning | info
    type: str      # oomkill | crashloop | policy_violation | cost_spike | deployment_failure
    namespace: str
    resource: str
    message: str
    raw_data: dict


class DetectorAgent:
    """
    Continuously monitors the K8s cluster and emits structured alerts.
    Runs as an async background task.
    """

    def __init__(self, on_alert: Callable[[Alert], None], kubeconfig: Optional[str] = None):
        self.on_alert = on_alert
        self.kubeconfig = kubeconfig
        self._running = False
        self._tasks = []

        try:
            if kubeconfig:
                k8s_config.load_kube_config(config_file=kubeconfig)
            else:
                k8s_config.load_incluster_config()
        except Exception:
            try:
                k8s_config.load_kube_config()
            except Exception as e:
                logger.warning("k8s_config_load_failed", error=str(e))

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    async def start(self):
        """Start all monitoring tasks."""
        self._running = True
        logger.info("detector_agent_started")

        self._tasks = [
            asyncio.create_task(self._watch_pod_events()),
            asyncio.create_task(self._watch_oomkills()),
            asyncio.create_task(self._watch_crashloops()),
        ]

        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self):
        """Stop all monitoring tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info("detector_agent_stopped")

    async def _watch_pod_events(self):
        """Watch for pod-level warning events (OOMKill, BackOff, Failed)."""
        logger.info("watching_pod_events")
        w = watch.Watch()

        while self._running:
            try:
                for event in w.stream(
                    self.core_v1.list_event_for_all_namespaces,
                    timeout_seconds=60
                ):
                    obj = event["object"]
                    reason = obj.reason or ""
                    message = obj.message or ""
                    namespace = obj.metadata.namespace or "default"
                    involved = obj.involved_object

                    if reason in ("OOMKilling", "OOMKilled"):
                        await self._emit_alert(Alert(
                            id=f"oom-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="critical",
                            type="oomkill",
                            namespace=namespace,
                            resource=involved.name or "unknown",
                            message=f"OOMKill detected: {message}",
                            raw_data={
                                "reason": reason,
                                "kind": involved.kind,
                                "count": obj.count,
                            }
                        ))

                    elif reason in ("BackOff", "CrashLoopBackOff"):
                        await self._emit_alert(Alert(
                            id=f"crash-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="critical",
                            type="crashloop",
                            namespace=namespace,
                            resource=involved.name or "unknown",
                            message=f"CrashLoop detected: {message}",
                            raw_data={
                                "reason": reason,
                                "kind": involved.kind,
                                "count": obj.count,
                            }
                        ))

                    elif reason in ("Failed", "FailedCreate", "FailedScheduling"):
                        await self._emit_alert(Alert(
                            id=f"fail-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="warning",
                            type="deployment_failure",
                            namespace=namespace,
                            resource=involved.name or "unknown",
                            message=f"Resource failure: {message}",
                            raw_data={"reason": reason, "kind": involved.kind}
                        ))

                    await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("pod_events_watch_error", error=str(e))
                await asyncio.sleep(5)

    async def _watch_oomkills(self):
        """Scan all pods for OOMKilled container states."""
        while self._running:
            try:
                pods = self.core_v1.list_pod_for_all_namespaces(watch=False)
                for pod in pods.items:
                    for cs in (pod.status.container_statuses or []):
                        if cs.last_state and cs.last_state.terminated:
                            term = cs.last_state.terminated
                            if term.reason == "OOMKilled":
                                await self._emit_alert(Alert(
                                    id=f"oom-scan-{pod.metadata.uid}-{cs.name}",
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    severity="critical",
                                    type="oomkill",
                                    namespace=pod.metadata.namespace,
                                    resource=pod.metadata.name,
                                    message=f"Container '{cs.name}' was OOMKilled. Restart count: {cs.restart_count}",
                                    raw_data={
                                        "container": cs.name,
                                        "restart_count": cs.restart_count,
                                        "exit_code": term.exit_code,
                                        "finished_at": str(term.finished_at),
                                    }
                                ))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("oomkill_scan_error", error=str(e))

            await asyncio.sleep(30)

    async def _watch_crashloops(self):
        """Scan for CrashLoopBackOff pods."""
        while self._running:
            try:
                pods = self.core_v1.list_pod_for_all_namespaces(
                    watch=False, field_selector="status.phase=Running"
                )
                for pod in pods.items:
                    for cs in (pod.status.container_statuses or []):
                        if cs.state and cs.state.waiting:
                            if cs.state.waiting.reason == "CrashLoopBackOff":
                                await self._emit_alert(Alert(
                                    id=f"crash-scan-{pod.metadata.uid}-{cs.name}",
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    severity="critical",
                                    type="crashloop",
                                    namespace=pod.metadata.namespace,
                                    resource=pod.metadata.name,
                                    message=f"Container '{cs.name}' in CrashLoopBackOff. Restarts: {cs.restart_count}",
                                    raw_data={
                                        "container": cs.name,
                                        "restart_count": cs.restart_count,
                                        "waiting_reason": cs.state.waiting.reason,
                                    }
                                ))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("crashloop_scan_error", error=str(e))

            await asyncio.sleep(20)

    async def _emit_alert(self, alert: Alert):
        """Fire alert to handler."""
        logger.info("alert_fired",
                    type=alert.type,
                    severity=alert.severity,
                    resource=alert.resource,
                    namespace=alert.namespace)
        try:
            if asyncio.iscoroutinefunction(self.on_alert):
                await self.on_alert(alert)
            else:
                self.on_alert(alert)
        except Exception as e:
            logger.error("alert_handler_error", error=str(e))

    async def simulate_alert(self, alert_type: str = "oomkill") -> Alert:
        """Simulate an alert for demo/testing purposes."""
        scenarios = {
            "oomkill": Alert(
                id="demo-oom-001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="critical",
                type="oomkill",
                namespace="default",
                resource="ml-inference-pod-7d9f8b",
                message="Container 'inference-server' OOMKilled. Memory limit 512Mi exceeded. Restart count: 3",
                raw_data={
                    "container": "inference-server",
                    "restart_count": 3,
                    "exit_code": 137,
                    "memory_limit": "512Mi",
                    "memory_request": "256Mi",
                }
            ),
            "crashloop": Alert(
                id="demo-crash-001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="critical",
                type="crashloop",
                namespace="production",
                resource="api-gateway-6c4d9f",
                message="Container 'api-gateway' in CrashLoopBackOff. Restarts: 5",
                raw_data={
                    "container": "api-gateway",
                    "restart_count": 5,
                    "waiting_reason": "CrashLoopBackOff",
                }
            ),
            "policy_violation": Alert(
                id="demo-policy-001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="warning",
                type="policy_violation",
                namespace="staging",
                resource="nginx-privileged-deploy",
                message="Kyverno policy 'disallow-root-containers' violated. Deployment uses privileged container.",
                raw_data={
                    "policy": "disallow-root-containers",
                    "rule": "check-privileged",
                    "action": "block",
                }
            ),
            "cost_spike": Alert(
                id="demo-cost-001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                severity="warning",
                type="cost_spike",
                namespace="ml-workloads",
                resource="namespace-budget",
                message="OpenCost: namespace 'ml-workloads' spend +42% above monthly budget threshold.",
                raw_data={
                    "current_spend_usd": 847.50,
                    "budget_usd": 600.00,
                    "overage_pct": 41.25,
                    "top_consumer": "kserve-iris-model",
                }
            ),
        }
        alert = scenarios.get(alert_type, scenarios["oomkill"])
        await self._emit_alert(alert)
        return alert
