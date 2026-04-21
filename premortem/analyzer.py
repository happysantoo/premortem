"""LLM-driven analysis. One call per failure injection, returns structured AnalysisReport.

Design notes:
- We use tool use as a structured output mechanism: the LLM "calls" emit_analysis
  with a schema derived from AnalysisReport. This is more reliable than asking for JSON
  in free text.
- The prompt is deliberately demanding — we want the LLM to reason like a senior
  distributed-systems architect, not summarize failure modes from a textbook.
- No simulation engine in v0.1 — pure LLM reasoning. This is "qualitative only" from
  the earlier plan. Quantitative sim comes later.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from anthropic import Anthropic

from premortem.models import AnalysisReport, FailureInjection, Topology

MODEL = "claude-opus-4-5"  # Swap to a cheaper model for iteration if needed
MAX_TOKENS = 4096

PROMPT_PATH = Path(__file__).parent / "prompts" / "analyze.md"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text()


def _analysis_tool_schema() -> dict:
    """Schema matching AnalysisReport. Derived by hand to keep LLM-friendly field descriptions.

    If you change AnalysisReport, update this. Yes, duplication — but the LLM needs
    descriptions tuned for reasoning, not for Python typing.
    """
    return {
        "name": "emit_analysis",
        "description": "Emit a structured failure-mode analysis. Call this exactly once.",
        "input_schema": {
            "type": "object",
            "required": ["timeline", "risks", "mitigations", "summary"],
            "properties": {
                "timeline": {
                    "type": "array",
                    "description": "Ordered sequence of what happens during the failure. "
                    "Be specific about which component does what at each step. "
                    "Use realistic time deltas.",
                    "items": {
                        "type": "object",
                        "required": ["t_seconds", "component", "description"],
                        "properties": {
                            "t_seconds": {"type": "integer"},
                            "component": {
                                "type": "string",
                                "description": "Component id from the topology.",
                            },
                            "description": {"type": "string"},
                        },
                    },
                },
                "risks": {
                    "type": "array",
                    "description": "Concrete risks revealed by this failure mode. "
                    "Prefer specific, design-derived risks over generic platitudes.",
                    "items": {
                        "type": "object",
                        "required": ["title", "impact", "likelihood", "explanation"],
                        "properties": {
                            "title": {"type": "string"},
                            "impact": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                            },
                            "likelihood": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "explanation": {"type": "string"},
                        },
                    },
                },
                "mitigations": {
                    "type": "array",
                    "description": "Proposed redesigns addressing the risks above. "
                    "Each mitigation must reference the risk it addresses by title. "
                    "Name the pattern (outbox, DLQ, circuit breaker, saga, etc.).",
                    "items": {
                        "type": "object",
                        "required": [
                            "title",
                            "addresses_risk",
                            "pattern",
                            "description",
                            "tradeoffs",
                        ],
                        "properties": {
                            "title": {"type": "string"},
                            "addresses_risk": {"type": "string"},
                            "pattern": {"type": "string"},
                            "description": {"type": "string"},
                            "tradeoffs": {"type": "string"},
                        },
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "One paragraph for an architect. What's the worst-case "
                    "impact and what's the single most important thing to do about it?",
                },
            },
        },
    }


def analyze(topology: Topology, failure: FailureInjection) -> AnalysisReport:
    """Run one what-if analysis. LLM reasons qualitatively over the topology + failure."""
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system_prompt = _load_prompt()
    user_prompt = (
        f"# Topology\n\n{topology.model_dump_json(indent=2)}\n\n"
        f"# Failure injection\n\n{failure.model_dump_json(indent=2)}\n\n"
        "Analyze this failure against the topology. Call emit_analysis with your findings."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        tools=[_analysis_tool_schema()],
        tool_choice={"type": "tool", "name": "emit_analysis"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract the tool use block
    for block in response.content:
        if block.type == "tool_use" and block.name == "emit_analysis":
            data = block.input
            return AnalysisReport(
                failure=failure,
                timeline=data["timeline"],
                risks=data["risks"],
                mitigations=data["mitigations"],
                summary=data["summary"],
            )

    raise RuntimeError(
        "LLM did not emit structured analysis. Raw response: "
        + json.dumps([b.model_dump() for b in response.content], default=str)
    )
