"""
Executor Agent — Executes approved remediation actions against the K8s cluster.
Supports: kubectl patch, ArgoCD rollback, Kyverno exceptions, scaling.
Circuit breaker prevents runaway remediation loops.

Safety improvements:
- Blast radius parameter validation: dangerous parameter values (e.g. scale to 0)
  are caught before execution and force escalation regardless of action whitelist
- Min-replicas floor enforced on all scale operations
"""

import os
import asyncio
import subprocess
import structlog
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
from agents.analyzer.analyzer import RCA
from agents.planner.planner import RemediationPlan

logger = structlog.get_logger(__name__)

# Blast radius: minimum replicas allowed for any auto-executed scale operation.
# Scaling to 0 is a high-blast action and must always require human approval.
MIN_SAFE_REPLICAS = 1

# Memory patch cap — don't auto-apply anything above this without human review
MAX_AUTO_MEMORY_GB = 4


class ExecutionResult(BaseModel):
    plan_alert_id: str
    success: bool
    action_taken: str
    output: str
    error: Optional[str]
    duration_seconds: float
    timestamp: str
    rolled_back: bool = False
    blast_radius_blocked: bool = False  # True if execution was blocked by blast radius check


class CircuitBreaker:
    """Prevents cascading remediation failures."""

    def __init__(self, max_failures: int = 3, reset_seconds: int = 300):
        self.max_failures = max_failures
        self.reset_seconds = reset_seconds
        self._failures: dict[str, list] = {}

    def is_open(self, key: str) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        failures = [t for t in self._failures.get(key, []) if now - t < self.reset_seconds]
        self._failures[key] = failures
        return len(failures) >= self.max_failures

    def record_failure(self, key: str):
        now = datetime.now(timezone.utc).timestamp()
        self._failures.setdefault(key, []).append(now)

    def record_success(self, key: str):
        self._failures.pop(key, None)


class ExecutorAgent:
    """
    Executes K8s remediation actions safely with circuit breaker protection
    and blast radius parameter validation.
    """

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.argocd_server = os.getenv("ARGOCD_SERVER", "localhost:8080")

    async def execute(self, plan: RemediationPlan, rca: RCA) -> ExecutionResult:
        """Execute the remediation plan."""
        start = datetime.now(timezone.utc)
        key = f"{plan.runbook_name}-{plan.rca_alert_id.split('-')[0]}"

        # Circuit breaker check
        if self.circuit_breaker.is_open(key):
            logger.warning("circuit_breaker_open", key=key)
            return ExecutionResult(
                plan_alert_id=plan.rca_alert_id,
                success=False,
                action_taken="blocked",
                output="",
                error=f"Circuit breaker open for {key}. Too many recent failures. Manual intervention required.",
                duration_seconds=0,
                timestamp=start.isoformat(),
            )

        # Blast radius parameter check — runs before any execution
        blast_radius_violation = self._check_blast_radius(plan, rca)
        if blast_radius_violation:
            logger.warning("blast_radius_blocked",
                           runbook=plan.runbook_name,
                           reason=blast_radius_violation)
            return ExecutionResult(
                plan_alert_id=plan.rca_alert_id,
                success=False,
                action_taken="blocked",
                output="",
                error=f"Blast radius check failed: {blast_radius_violation}. Escalate to human review.",
                duration_seconds=0,
                timestamp=start.isoformat(),
                blast_radius_blocked=True,
            )

        logger.info("executing_remediation",
                    runbook=plan.runbook_name,
                    action_type=rca.action_type)

        try:
            result = await self._dispatch(plan, rca)
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            if result["success"]:
                self.circuit_breaker.record_success(key)
                logger.info("remediation_success",
                            runbook=plan.runbook_name,
                            duration=duration)
            else:
                self.circuit_breaker.record_failure(key)
                logger.error("remediation_failed",
                             runbook=plan.runbook_name,
                             error=result.get("error"))

            return ExecutionResult(
                plan_alert_id=plan.rca_alert_id,
                success=result["success"],
                action_taken=plan.runbook_name,
                output=result.get("output", ""),
                error=result.get("error"),
                duration_seconds=duration,
                timestamp=start.isoformat(),
            )

        except Exception as e:
            self.circuit_breaker.record_failure(key)
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            logger.error("executor_exception", error=str(e))
            return ExecutionResult(
                plan_alert_id=plan.rca_alert_id,
                success=False,
                action_taken=plan.runbook_name,
                output="",
                error=str(e),
                duration_seconds=duration,
                timestamp=start.isoformat(),
            )

    def _check_blast_radius(self, plan: RemediationPlan, rca: RCA) -> Optional[str]:
        """
        Validate action parameters for blast radius before execution.
        The whitelist blocks dangerous action *types*, but this checks dangerous *parameters*.
        Returns an error string if blocked, None if safe to proceed.

        Key cases caught here:
        - scale_down to 0 replicas (complete outage)
        - scale_down to a very large number (resource exhaustion)
        - patch_resources with unreasonably large memory values
        """
        action = rca.action_type
        params = plan.parameters

        if action == "scale_down":
            replicas = params.get("target_replicas", 1)
            try:
                replicas = int(replicas)
            except (TypeError, ValueError):
                return f"target_replicas value '{replicas}' is not a valid integer"

            if replicas < MIN_SAFE_REPLICAS:
                return (
                    f"target_replicas={replicas} would take the workload to zero. "
                    f"Minimum safe replicas for auto-execution is {MIN_SAFE_REPLICAS}. "
                    "Scale-to-zero requires explicit human approval."
                )

            if replicas > 50:
                return (
                    f"target_replicas={replicas} is unusually high. "
                    "Large scale-up requires human review to prevent resource exhaustion."
                )

        if action == "patch_resources":
            # Check if memory value is within auto-execute safe range
            memory_str = params.get("new_memory_limit", "")
            if memory_str:
                memory_gb = self._parse_memory_to_gb(str(memory_str))
                if memory_gb is not None and memory_gb > MAX_AUTO_MEMORY_GB:
                    return (
                        f"Requested memory limit {memory_str} exceeds auto-execute cap of {MAX_AUTO_MEMORY_GB}Gi. "
                        "Large memory changes require human approval."
                    )

        return None

    def _parse_memory_to_gb(self, mem_str: str) -> Optional[float]:
        """Parse a K8s memory string (e.g. '512Mi', '2Gi', '4096M') to GB."""
        try:
            mem_str = mem_str.strip()
            if mem_str.endswith("Gi"):
                return float(mem_str[:-2])
            if mem_str.endswith("Mi"):
                return float(mem_str[:-2]) / 1024
            if mem_str.endswith("G"):
                return float(mem_str[:-1])
            if mem_str.endswith("M"):
                return float(mem_str[:-1]) / 1024
        except ValueError:
            pass
        return None

    async def _dispatch(self, plan: RemediationPlan, rca: RCA) -> dict:
        """Route to the correct executor based on action type."""
        action = rca.action_type

        handlers = {
            "patch_resources": self._patch_resources,
            "rollback": self._rollback_deployment,
            "scale_down": self._scale_down,
            "create_exception": self._create_kyverno_exception,
            "monitor": self._monitor_only,
            "escalate": self._escalate_only,
        }

        handler = handlers.get(action, self._monitor_only)
        return await handler(plan, rca)

    async def _patch_resources(self, plan: RemediationPlan, rca: RCA) -> dict:
        """Patch deployment resource limits (e.g. increase memory)."""
        params = plan.parameters
        namespace = params.get("namespace", "default")
        deployment = params.get("deployment_name", "")

        if not deployment:
            resource = rca.alert_id.split("-")[1] if "-" in rca.alert_id else "unknown"
            deployment = resource

        patch_cmd = [
            "kubectl", "patch", "deployment", deployment,
            "-n", namespace,
            "--patch", '{"spec":{"template":{"spec":{"containers":[{"name":"app","resources":{"limits":{"memory":"1Gi"},"requests":{"memory":"512Mi"}}}]}}}}',
        ]

        output, error, success = await self._run_kubectl(patch_cmd)

        if success:
            rollout_cmd = ["kubectl", "rollout", "status", f"deployment/{deployment}", "-n", namespace, "--timeout=60s"]
            ro_out, ro_err, ro_ok = await self._run_kubectl(rollout_cmd)
            output += f"\n{ro_out}"

        return {"success": success, "output": output, "error": error if not success else None}

    async def _rollback_deployment(self, plan: RemediationPlan, rca: RCA) -> dict:
        """Trigger ArgoCD rollback."""
        params = plan.parameters
        app_name = params.get("argocd_app_name", "neuroscale-app")
        namespace = params.get("namespace", "default")

        argo_cmd = ["argocd", "app", "rollback", app_name, "--insecure"]
        output, error, success = await self._run_cmd(argo_cmd)

        if not success:
            kubectl_cmd = ["kubectl", "rollout", "undo", f"deployment/{app_name}", "-n", namespace]
            output, error, success = await self._run_kubectl(kubectl_cmd)

        return {"success": success, "output": output, "error": error if not success else None}

    async def _scale_down(self, plan: RemediationPlan, rca: RCA) -> dict:
        """
        Scale down a deployment or KServe InferenceService.
        Blast radius check already validated replicas >= MIN_SAFE_REPLICAS before reaching here.
        """
        params = plan.parameters
        namespace = params.get("namespace", "ml-workloads")
        workload = params.get("workload_name", "")
        replicas = params.get("target_replicas", 1)

        logger.info("scale_down_executing",
                    workload=workload,
                    namespace=namespace,
                    target_replicas=replicas)

        cmd = ["kubectl", "scale", "deployment", workload, f"--replicas={replicas}", "-n", namespace]
        output, error, success = await self._run_kubectl(cmd)

        return {"success": success, "output": output, "error": error if not success else None}

    async def _create_kyverno_exception(self, plan: RemediationPlan, rca: RCA) -> dict:
        """Create a Kyverno PolicyException for an approved workload."""
        params = plan.parameters
        namespace = params.get("namespace", "default")
        policy = params.get("policy_name", "unknown-policy")
        workload = params.get("workload_name", "")

        exception_yaml = f"""apiVersion: kyverno.io/v2
kind: PolicyException
metadata:
  name: {workload}-exception
  namespace: {namespace}
spec:
  exceptions:
  - policyName: {policy}
    ruleNames:
    - check-privileged
  match:
    any:
    - resources:
        kinds:
        - Pod
        namespaces:
        - {namespace}
        names:
        - {workload}*
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(exception_yaml)
            tmpfile = f.name

        cmd = ["kubectl", "apply", "-f", tmpfile]
        output, error, success = await self._run_kubectl(cmd)

        try:
            os.unlink(tmpfile)
        except Exception:
            pass

        return {"success": success, "output": output, "error": error if not success else None}

    async def _monitor_only(self, plan: RemediationPlan, rca: RCA) -> dict:
        """No action — just monitor and log."""
        return {
            "success": True,
            "output": f"Monitoring mode: No automated action taken for {rca.action_type}. Incident logged.",
            "error": None,
        }

    async def _escalate_only(self, plan: RemediationPlan, rca: RCA) -> dict:
        """Flag for escalation — execution handled by Escalation Agent."""
        return {
            "success": True,
            "output": f"Escalation triggered for alert {rca.alert_id}. Escalation Agent notified.",
            "error": None,
        }

    async def _run_kubectl(self, cmd: list[str]) -> tuple[str, str, bool]:
        return await self._run_cmd(cmd)

    async def _run_cmd(self, cmd: list[str]) -> tuple[str, str, bool]:
        """Run a shell command asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            success = proc.returncode == 0
            return stdout.decode(), stderr.decode(), success
        except asyncio.TimeoutError:
            return "", "Command timed out after 120 seconds", False
        except FileNotFoundError:
            logger.warning("command_not_found_demo_mode", cmd=cmd[0])
            return f"[DEMO] Would execute: {' '.join(cmd)}", "", True
        except Exception as e:
            return "", str(e), False
