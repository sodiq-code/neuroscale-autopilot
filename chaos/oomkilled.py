"""
OOMKilled Chaos Scenario

Injects an OOMKill failure by applying a pod with insufficient memory limits.
The pod will be killed by the kernel when it exceeds its memory limit.

This scenario tests the system's ability to:
1. Detect OOMKill events
2. Diagnose memory pressure
3. Recommend scaling up memory or reducing load
4. Execute remediation (increase memory, scale down, etc.)
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class OOMKilledScenario:
    """OOMKilled pod chaos scenario."""

    def __init__(self, namespace: str = "default", pod_name: str = "oomkill-test"):
        """
        Initialize the OOMKilled scenario.
        
        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod to create
        """
        self.namespace = namespace
        self.pod_name = pod_name
        self.injection_id = str(uuid.uuid4())
        self.start_time = datetime.utcnow().isoformat() + "Z"

    async def inject(self) -> Dict[str, Any]:
        """
        Inject the OOMKilled scenario.
        
        Returns:
            Injection metadata
        """
        logger.info(
            "oomkilled_injection_start",
            injection_id=self.injection_id,
            namespace=self.namespace,
            pod_name=self.pod_name,
        )

        # Manifest for a pod that will OOMKill
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.pod_name,
                "namespace": self.namespace,
                "labels": {
                    "chaos-scenario": "oomkilled",
                    "injection-id": self.injection_id,
                },
            },
            "spec": {
                "containers": [
                    {
                        "name": "memory-hog",
                        "image": "progrium/stress",
                        "args": ["--vm", "1", "--vm-bytes", "256M", "--vm-hang", "3600"],
                        "resources": {
                            "limits": {
                                "memory": "128Mi",  # Limit is less than requested
                            },
                            "requests": {
                                "memory": "64Mi",
                            },
                        },
                    }
                ],
                "restartPolicy": "Never",
            },
        }

        # In a real implementation, this would apply the manifest via kubectl
        # For now, we simulate the injection
        logger.debug("oomkilled_manifest_created", manifest=manifest)

        # Simulate pod creation delay
        await asyncio.sleep(0.1)

        result = {
            "injection_id": self.injection_id,
            "scenario": "oomkilled",
            "namespace": self.namespace,
            "pod_name": self.pod_name,
            "status": "injected",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "manifest": manifest,
            "expected_alert": {
                "type": "oomkill",
                "severity": "critical",
                "message": f"Pod {self.pod_name} in {self.namespace} is in OOMKilled state",
            },
        }

        logger.info("oomkilled_injection_complete", injection_id=self.injection_id)
        return result

    async def cleanup(self) -> Dict[str, Any]:
        """
        Clean up the OOMKilled scenario.
        
        Returns:
            Cleanup metadata
        """
        logger.info(
            "oomkilled_cleanup_start",
            injection_id=self.injection_id,
            pod_name=self.pod_name,
        )

        # In a real implementation, this would delete the pod via kubectl
        # For now, we simulate the cleanup
        await asyncio.sleep(0.1)

        result = {
            "injection_id": self.injection_id,
            "scenario": "oomkilled",
            "status": "cleaned_up",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": (
                datetime.utcnow() - datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            ).total_seconds(),
        }

        logger.info("oomkilled_cleanup_complete", injection_id=self.injection_id)
        return result


async def inject_oomkilled(namespace: str = "default") -> Dict[str, Any]:
    """
    Convenience function to inject OOMKilled scenario.
    
    Args:
        namespace: Kubernetes namespace
        
    Returns:
        Injection metadata
    """
    scenario = OOMKilledScenario(namespace=namespace)
    return await scenario.inject()


async def cleanup_oomkilled(injection_id: str) -> Dict[str, Any]:
    """
    Convenience function to clean up OOMKilled scenario.
    
    Args:
        injection_id: Injection ID to clean up
        
    Returns:
        Cleanup metadata
    """
    # In a real implementation, this would look up the injection by ID
    # For now, we just return a cleanup result
    return {
        "injection_id": injection_id,
        "scenario": "oomkilled",
        "status": "cleaned_up",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
