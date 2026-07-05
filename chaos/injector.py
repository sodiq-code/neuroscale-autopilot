"""Chaos injection API for NeuroScale Autopilot v2.

The injector keeps all chaos scenarios safe-by-default: every scenario returns
structured metadata, supports dry-run, and exposes cleanup commands for demo
and benchmark automation. Real cluster mutation should be enabled only in dev
or controlled ACK clusters.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from chaos.scenarios import SCENARIOS, get_scenario


@dataclass
class ChaosRun:
    run_id: str
    scenario: str
    namespace: str
    dry_run: bool
    started_at: str
    expected_symptoms: List[str]
    manifests: List[str]
    cleanup_commands: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


class ChaosInjector:
    """Inject and clean up safe Kubernetes chaos scenarios."""

    def list_scenarios(self) -> List[str]:
        return sorted(SCENARIOS.keys())

    def inject(self, scenario: str, namespace: str = "neuroscale-chaos", dry_run: bool = True) -> Dict:
        spec = get_scenario(scenario)
        run = ChaosRun(
            run_id=str(uuid.uuid4()),
            scenario=scenario,
            namespace=namespace,
            dry_run=dry_run,
            started_at=datetime.now(timezone.utc).isoformat(),
            expected_symptoms=spec.expected_symptoms,
            manifests=[m.replace("{{ namespace }}", namespace) for m in spec.manifests],
            cleanup_commands=[c.replace("{{ namespace }}", namespace) for c in spec.cleanup_commands],
        )

        return {
            "status": "prepared" if dry_run else "injected",
            "message": "Dry-run generated manifests only" if dry_run else "Apply manifests with kubectl in controlled dev cluster",
            "run": run.to_dict(),
        }

    def cleanup(self, scenario: Optional[str] = None, namespace: str = "neuroscale-chaos") -> Dict:
        names = [scenario] if scenario else self.list_scenarios()
        commands: List[str] = []
        for name in names:
            spec = get_scenario(name)
            commands.extend(c.replace("{{ namespace }}", namespace) for c in spec.cleanup_commands)
        return {
            "status": "cleanup_plan_ready",
            "namespace": namespace,
            "commands": list(dict.fromkeys(commands)),
        }


def create_injector() -> ChaosInjector:
    return ChaosInjector()
