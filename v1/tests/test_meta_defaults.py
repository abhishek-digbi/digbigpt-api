import pytest

from orchestrator.orchestrators.agent_models import Meta, InteractiveComponent


def make_component(label: str) -> InteractiveComponent:
    # Provide required optional fields explicitly to satisfy validation
    return InteractiveComponent(
        id=None,
        display_text=label,
        screen_name="Recipe",
        type="ROUTE",
        data=None,
    )


def test_meta_actions_is_independent_per_instance():
    m1 = Meta()
    m2 = Meta()

    # mutate only the first instance
    m1.actions.append(make_component("A"))

    # verify the second instance remains unaffected
    assert len(m1.actions) == 1
    assert len(m2.actions) == 0


def test_meta_actions_defaults_to_empty_list():
    m = Meta()
    assert isinstance(m.actions, list)
    assert m.actions == []
    # Ensure appending works without None checks
    m.actions.append(make_component("B"))
    assert len(m.actions) == 1
