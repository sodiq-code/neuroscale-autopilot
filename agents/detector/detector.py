"""
Detector Agent — Continuously monitors Kubernetes cluster for anomalies.
Watches: Pod health, OOMKills, CrashLoops, Kyverno policy violations, OpenCost budget alerts.
Fires structured alerts to the Analyzer Agent.
"""

import asyncio
import time
import structlog
from datetime import datetime, timezone
from typing import Callable, Optional
from kubernetes import client, config as k8s_config, watch
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# How long to suppress a repeat alert for the same underlying issue before
# re-emitting it. Without this, a persistent CrashLoopBackOff or a watch
# reconnect that replays recent Kubernetes events would re-fire (and
# re-trigger a full analyze->plan->escalate pipeline run, including real
# Qwen API calls) for an issue that was already reported seconds ago.
ALERT_SUPPRESSION_WINDOW_SECONDS = 300


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
        # Tracks the last-seen Kubernetes event resourceVersion so that when
        # the events watch reconnects (on its 60s timeout or after a
        # transient error) it resumes from where it left off instead of
        # re-listing and replaying recent events from scratch.
        self._events_resource_version: Optional[str] = None
        # De-duplication cache: alert dedup key -> epoch timestamp last emitted.
        # Prevents the same ongoing issue (e.g. a pod stuck in
        # ImagePullBackOff, or a replayed watch event) from re-triggering a
        # brand-new pipeline run every time the underlying condition is
        # observed again within the suppression window.
        self._recent_alerts: dict[str, float] = {}

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
        """Watch for pod-level warning events (OOMKill, BackOff, Failed).

        Resumes from the last-seen resourceVersion on reconnect instead of
        re-listing from scratch, so a 60s timeout or transient error doesn't
        cause recently-handled events to be replayed and re-processed as if
        they were brand new (see ALERT_SUPPRESSION_WINDOW_SECONDS for the
        second, independent safeguard against that).
        """
        logger.info("watching_pod_events")
        w = watch.Watch()

        while self._running:
            try:
                stream_kwargs = {"timeout_seconds": 60}
                if self._events_resource_version:
                    stream_kwargs["resource_version"] = self._events_resource_version

                for event in w.stream(
                    self.core_v1.list_event_for_all_namespaces,
                    **stream_kwargs
                ):
                    obj = event["object"]
                    if obj.metadata and obj.metadata.resource_version:
                        self._events_resource_version = obj.metadata.resource_version

                    reason = obj.reason or ""
                    message = obj.message or ""
                    namespace = obj.metadata.namespace or "default"
                    involved = obj.involved_object
                    resource_name = involved.name or "unknown"

                    if reason in ("OOMKilling", "OOMKilled"):
                        await self._emit_alert(Alert(
                            id=f"oom-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="critical",
                            type="oomkill",
                            namespace=namespace,
                            resource=resource_name,
                            message=f"OOMKill detected: {message}",
                            raw_data={
                                "reason": reason,
                                "kind": involved.kind,
                                "count": obj.count,
                            }
                        ), dedup_key=f"oomkill:{namespace}:{resource_name}")

                    elif reason in ("BackOff", "CrashLoopBackOff"):
                        await self._emit_alert(Alert(
                            id=f"crash-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="critical",
                            type="crashloop",
                            namespace=namespace,
                            resource=resource_name,
                            message=f"CrashLoop detected: {message}",
                            raw_data={
                                "reason": reason,
                                "kind": involved.kind,
                                "count": obj.count,
                            }
                        ), dedup_key=f"crashloop:{namespace}:{resource_name}")

                    elif reason in ("Failed", "FailedCreate", "FailedScheduling"):
                        await self._emit_alert(Alert(
                            id=f"fail-{obj.metadata.uid or datetime.now().timestamp()}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            severity="warning",
                            type="deployment_failure",
                            namespace=namespace,
                            resource=resource_name,
                            message=f"Resource failure: {message}",
                            raw_data={"reason": reason, "kind": involved.kind}
                        ), dedup_key=f"deployment_failure:{namespace}:{resource_name}")

                    await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # A stale/expired resourceVersion (410 Gone) means Kubernetes
                # has compacted past it — fall back to a fresh list on the
                # next iteration rather than looping on the same error.
                if "410" in str(e) or "Expired" in str(e):
                    logger.warning("events_resource_version_expired_resetting")
                    self._events_resource_version = None
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
                                ), dedup_key=f"oomkill:{pod.metadata.namespace}:{pod.metadata.name}:{cs.name}")
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
                                ), dedup_key=f"crashloop-scan:{pod.metadata.namespace}:{pod.metadata.name}:{cs.name}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("crashloop_scan_error", error=str(e))

            await asyncio.sleep(20)

    async def _emit_alert(self, alert: Alert, dedup_key: Optional[str] = None):
        """Fire alert to handler.

        If `dedup_key` is provided, suppress this alert when the same key
        was already emitted within ALERT_SUPPRESSION_WINDOW_SECONDS. This is
        what stops a persistent issue (e.g. a pod stuck in
        ImagePullBackOff for minutes) — or a watch reconnect replaying an
        event that was already handled — from re-triggering a brand new
        analyze -> plan -> escalate pipeline run (including real Qwen API
        calls) every few seconds for the exact same underlying problem.
        Alerts without a dedup_key (e.g. manual demo triggers) always fire.
        """
        if dedup_key:
            now = time.monotonic()
            last_emitted = self._recent_alerts.get(dedup_key)
            if last_emitted is not None and (now - last_emitted) < ALERT_SUPPRESSION_WINDOW_SECONDS:
                logger.debug("alert_suppressed_duplicate",
                             dedup_key=dedup_key,
                             seconds_since_last=round(now - last_emitted, 1))
                return
            self._recent_alerts[dedup_key] = now
            # Bound the cache so long-running deployments don't leak memory.
            if len(self._recent_alerts) > 500:
                oldest_keys = sorted(self._recent_alerts, key=self._recent_alerts.get)[:100]
                for k in oldest_keys:
                    del self._recent_alerts[k]

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
