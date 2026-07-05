from agents.router.models import get_model, MODELS
from chaos.injector import create_injector


def test_qwen_model_registry_has_required_models():
    assert MODELS["critical_rca"]["name"] == "qwen3-max"
    assert MODELS["critical_rca"]["thinking"] is True
    assert MODELS["embedding"]["name"] == "text-embedding-v3"


def test_model_route_critical_incident_uses_qwen3_max():
    model = get_model("critical_incident")
    assert model["name"] == "qwen3-max"
    assert model["thinking"] is True


def test_chaos_injector_lists_twelve_scenarios():
    injector = create_injector()
    scenarios = injector.list_scenarios()
    assert len(scenarios) >= 12
    assert "oomkilled" in scenarios
    assert "cost_anomaly" in scenarios


def test_chaos_injector_dry_run_returns_cleanup_plan():
    injector = create_injector()
    result = injector.inject("oomkilled", dry_run=True)
    assert result["status"] == "prepared"
    assert result["run"]["cleanup_commands"]
