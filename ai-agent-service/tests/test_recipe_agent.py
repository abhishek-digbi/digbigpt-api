import types
import sys

from utils.recipe_agent_utils import build_exclusion_set


def setup_dummy_app_modules():
    dummy_app = types.ModuleType("app")
    dummy_metrics = types.ModuleType("app.metrics")
    dummy_metrics.meter = types.SimpleNamespace(
        create_counter=lambda *a, **k: None,
        create_histogram=lambda *a, **k: None,
    )

    def dummy_track_execution(*args, **kwargs):
        def wrapper(func):
            return func

        return wrapper

    dummy_metrics.track_execution = dummy_track_execution
    dummy_agent_metrics = types.ModuleType("app.agent_metrics")

    def dummy_decorator(*args, **kwargs):
        def wrapper(func):
            return func
        return wrapper

    dummy_agent_metrics.track_agent_metrics = dummy_decorator
    dummy_app.metrics = dummy_metrics
    dummy_app.agent_metrics = dummy_agent_metrics
    sys.modules.setdefault("app", dummy_app)
    sys.modules.setdefault("app.metrics", dummy_metrics)
    sys.modules.setdefault("app.agent_metrics", dummy_agent_metrics)


setup_dummy_app_modules()

from orchestrator.orchestrators.recipe_agent import RecipeAgent


def test_build_exclusion_set_string():
    profile = {"coach_added_exclusions": "cheese, milk, eggs"}
    exclusions = build_exclusion_set(profile)
    assert {"cheese", "milk", "eggs", "alcohol"}.issubset(exclusions)
