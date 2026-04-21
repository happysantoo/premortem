"""Topology schema. This is the contract between elicitation, simulation, and redesign layers.

Keep this stable — every other module imports from here.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ComponentKind(str, Enum):
    """What a node in the topology represents."""

    SERVICE = "service"
    MESSAGE_BROKER = "message_broker"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    QUEUE = "queue"
    SCHEDULER = "scheduler"
    LOAD_BALANCER = "load_balancer"


class DeliverySemantics(str, Enum):
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class Component(BaseModel):
    """A node in the architecture. Add fields sparingly; breadth beats depth for v0.1."""

    id: str = Field(..., description="Stable identifier, kebab-case.")
    kind: ComponentKind
    description: str = Field(..., description="One sentence. Used as LLM context.")
    sla_p99_ms: int | None = Field(None, description="Target p99 latency in ms, if applicable.")
    notes: str | None = Field(None, description="Freeform context: replication, acks, config, invariants.")


class Edge(BaseModel):
    """A directed interaction between two components."""

    source: str = Field(..., description="Component id.")
    target: str = Field(..., description="Component id.")
    pattern: Literal["sync_request", "async_produce", "async_consume", "polling", "webhook"]
    delivery: DeliverySemantics | None = None
    notes: str | None = None


class Topology(BaseModel):
    """Complete architecture description. This is what the LLM reasons over."""

    name: str
    summary: str = Field(..., description="2-3 sentences describing the system's purpose.")
    constraints: list[str] = Field(
        default_factory=list,
        description="Non-functional requirements: SLAs, regulatory, durability guarantees.",
    )
    components: list[Component]
    edges: list[Edge]

    def component(self, cid: str) -> Component:
        for c in self.components:
            if c.id == cid:
                return c
        raise KeyError(f"Unknown component: {cid}")


class FailureInjection(BaseModel):
    """What to simulate going wrong."""

    target: str = Field(..., description="Component id that is failing.")
    mode: str = Field(
        ...,
        description="Natural-language failure mode, e.g. 'broker is slow', "
        "'returns 500 for 30% of requests', 'partition loses leader'.",
    )
    duration_seconds: int | None = None


class TimelineEvent(BaseModel):
    """One step in the simulated failure narrative."""

    t_seconds: int
    component: str
    description: str


class Risk(BaseModel):
    """A finding from the simulation."""

    title: str
    impact: Literal["low", "medium", "high", "critical"]
    likelihood: Literal["low", "medium", "high"]
    explanation: str


class Mitigation(BaseModel):
    """A proposed fix."""

    title: str
    addresses_risk: str = Field(..., description="Title of the risk this addresses.")
    pattern: str = Field(..., description="E.g. 'circuit breaker', 'outbox', 'DLQ', 'bulkhead'.")
    description: str
    tradeoffs: str


class AnalysisReport(BaseModel):
    """The full output of one what-if run."""

    failure: FailureInjection
    timeline: list[TimelineEvent]
    risks: list[Risk]
    mitigations: list[Mitigation]
    summary: str = Field(..., description="One-paragraph executive summary.")
