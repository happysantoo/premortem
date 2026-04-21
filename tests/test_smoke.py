"""Smoke tests. Don't hit the LLM; just validate the topology YAML parses."""

from pathlib import Path

import yaml

from premortem.models import Topology

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_payment_contingency_loads() -> None:
    with (EXAMPLES / "payment_contingency.yaml").open() as f:
        data = yaml.safe_load(f)
    topology = Topology.model_validate(data)

    assert topology.name == "payment-contingency-decisioning"
    assert len(topology.components) >= 8
    assert any(c.id == "contingency-engine" for c in topology.components)


def test_all_edge_endpoints_exist() -> None:
    """Every edge source/target must be a valid component id."""
    with (EXAMPLES / "payment_contingency.yaml").open() as f:
        topology = Topology.model_validate(yaml.safe_load(f))

    ids = {c.id for c in topology.components}
    for edge in topology.edges:
        assert edge.source in ids, f"Edge source '{edge.source}' not in components"
        assert edge.target in ids, f"Edge target '{edge.target}' not in components"
